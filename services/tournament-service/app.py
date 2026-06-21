"""
Tournament Service
-------------------
Owns: tournament creation, participant registration, bracket generation,
match scheduling and scoring.

This is Danial's core domain (Tournament Engine) inside the GYM IT System
microservices architecture.
"""
import os
import math
import time
import uuid
import logging
from datetime import datetime
from functools import wraps

import jwt
import requests
from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy

from bracket import bracket_size, total_rounds, first_round_pairings
from event_publisher import publish_event

app = Flask(__name__)

# DATABASE_URL is injected by docker-compose / k8s. Falls back to local sqlite
# so the service also runs standalone with zero setup.
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///tournament.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-insecure-jwt-secret-change-me")
JWT_ALGORITHM = "HS256"
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://auth-service:8001")
SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "dev-service-token")
LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JWT / RBAC helpers
# ---------------------------------------------------------------------------
def _decode_bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, ("missing or malformed Authorization header", 401)

    token = header.split(" ", 1)[1].strip()
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM]), None
    except jwt.ExpiredSignatureError:
        return None, ("token has expired", 401)
    except jwt.InvalidTokenError:
        return None, ("invalid token", 401)


def auth_required(*allowed_roles):
    """Validate the shared auth-service JWT and optionally enforce roles."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            payload, error = _decode_bearer_token()
            if error:
                message, status = error
                return jsonify({"error": message}), status

            g.current_user_id = payload.get("sub")
            g.current_user_role = payload.get("role", "member")

            if allowed_roles and g.current_user_role not in allowed_roles:
                return jsonify({"error": "forbidden: insufficient role"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Tournament(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    sport = db.Column(db.String(60), default="general")
    status = db.Column(db.String(20), default="draft")  # draft -> active -> finished
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "sport": self.sport,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class Participant(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tournament_id = db.Column(db.String(36), db.ForeignKey("tournament.id"), nullable=False)
    user_id = db.Column(db.String(36), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    seed = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "tournament_id": self.tournament_id,
            "user_id": self.user_id,
            "name": self.name,
            "seed": self.seed,
        }


class Match(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tournament_id = db.Column(db.String(36), db.ForeignKey("tournament.id"), nullable=False)
    round_number = db.Column(db.Integer, nullable=False)
    slot = db.Column(db.Integer, nullable=False)  # position within the round
    participant_a_id = db.Column(db.String(36), nullable=True)
    participant_b_id = db.Column(db.String(36), nullable=True)
    score_a = db.Column(db.Integer, nullable=True)
    score_b = db.Column(db.Integer, nullable=True)
    winner_id = db.Column(db.String(36), nullable=True)
    status = db.Column(db.String(20), default="pending")  # pending -> scheduled -> finished
    scheduled_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "tournament_id": self.tournament_id,
            "round": self.round_number,
            "slot": self.slot,
            "participant_a_id": self.participant_a_id,
            "participant_b_id": self.participant_b_id,
            "score_a": self.score_a,
            "score_b": self.score_b,
            "winner_id": self.winner_id,
            "status": self.status,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
        }


# ---------------------------------------------------------------------------
# Bracket generation (single elimination)
# ---------------------------------------------------------------------------
def generate_single_elimination(tournament_id, participant_ids):
    """
    Builds a single-elimination bracket tree.
    Pads the field to the next power of two with byes (None) so every
    round divides evenly.
    """
    size = bracket_size(len(participant_ids))
    padded = list(participant_ids) + [None] * (size - len(participant_ids))
    rounds = total_rounds(len(participant_ids))
    matches = []

    # Round 1 from the padded participant list
    round1 = []
    for slot in range(size // 2):
        a = padded[slot * 2]
        b = padded[slot * 2 + 1]
        m = Match(
            tournament_id=tournament_id,
            round_number=1,
            slot=slot,
            participant_a_id=a,
            participant_b_id=b,
            status="finished" if (a is None or b is None) else "pending",
            # auto-advance byes
            winner_id=(a or b) if (a is None or b is None) else None,
        )
        round1.append(m)
    matches.extend(round1)

    # Empty placeholder matches for subsequent rounds; filled in as winners advance
    matches_per_round = size // 2
    for r in range(2, rounds + 1):
        matches_per_round //= 2
        for slot in range(matches_per_round):
            matches.append(Match(tournament_id=tournament_id, round_number=r, slot=slot, status="pending"))

    return matches


def advance_winner(tournament_id, finished_match):
    """After a match finishes, push the winner into the next round's slot."""
    next_round = finished_match.round_number + 1
    next_slot = finished_match.slot // 2

    next_match = Match.query.filter_by(
        tournament_id=tournament_id, round_number=next_round, slot=next_slot
    ).with_for_update().first()
    if next_match is None:
        return  # this was the final

    if finished_match.slot % 2 == 0:
        next_match.participant_a_id = finished_match.winner_id
    else:
        next_match.participant_b_id = finished_match.winner_id

    # If the next match already has both sides (one might have been a bye), keep pending
    db.session.add(next_match)


def maybe_finish_tournament(tournament_id):
    """If the final match is finished, move the tournament to finished."""
    last = (
        Match.query.filter_by(tournament_id=tournament_id)
        .order_by(Match.round_number.desc(), Match.slot.desc())
        .first()
    )
    if last and last.status == "finished":
        t = Tournament.query.get(tournament_id)
        if t and t.status != "finished":
            t.status = "finished"
            db.session.add(t)


def _participant_user_id(participant_id):
    participant = Participant.query.get(participant_id)
    return participant.user_id if participant else None


def _patch_user_stats(user_id, payload):
    if not user_id:
        return
    try:
        requests.patch(
            f"{AUTH_SERVICE_URL.rstrip('/')}/users/{user_id}/tournament-stats",
            json=payload,
            headers={"X-Service-Token": SERVICE_TOKEN},
            timeout=5,
        ).raise_for_status()
    except requests.RequestException as exc:
        LOGGER.warning("Failed to update tournament stats for user %s: %s", user_id, exc)


def update_user_stats_for_match(match, loser_participant_id, tournament_completed=False):
    winner_user_id = _participant_user_id(match.winner_id)
    loser_user_id = _participant_user_id(loser_participant_id)
    _patch_user_stats(
        winner_user_id,
        {
            "played": True,
            "win": True,
            "points_delta": 8 if tournament_completed else 3,
            "champion": tournament_completed,
        },
    )
    _patch_user_stats(
        loser_user_id,
        {
            "played": True,
            "loss": True,
            "points_delta": 1,
        },
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "service": "tournament-service"}), 200


@app.route("/tournaments", methods=["POST"])
@auth_required("admin", "trainer")
def create_tournament():
    data = request.get_json(force=True) or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400

    def parse_date(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            raise ValueError(f"Invalid date format: {value} (expected YYYY-MM-DD)")

    try:
        start_date = parse_date(data.get("start_date"))
        end_date = parse_date(data.get("end_date"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if start_date and end_date and end_date < start_date:
        return jsonify({"error": "end_date cannot be before start_date"}), 400

    t = Tournament(
        name=name,
        sport=data.get("sport", "general"),
        start_date=start_date,
        end_date=end_date,
    )
    db.session.add(t)
    db.session.commit()
    publish_event(
        "tournament.created",
        {
            "tournament_id": t.id,
            "name": t.name,
            "sport": t.sport,
            "status": t.status,
            "created_by": getattr(g, "current_user_id", None),
        },
    )
    return jsonify(t.to_dict()), 201


@app.route("/tournaments", methods=["GET"])
@auth_required()
def list_tournaments():
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))
    tournaments = (
        Tournament.query.order_by(Tournament.created_at.desc())
        .limit(limit).offset(offset).all()
    )
    return jsonify([t.to_dict() for t in tournaments]), 200


@app.route("/tournaments/<tournament_id>", methods=["GET"])
@auth_required()
def get_tournament(tournament_id):
    t = Tournament.query.get_or_404(tournament_id)
    return jsonify(t.to_dict()), 200


@app.route("/tournaments/<tournament_id>/participants", methods=["POST"])
@auth_required("admin", "trainer")
def add_participant(tournament_id):
    Tournament.query.get_or_404(tournament_id)
    data = request.get_json(force=True) or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400

    p = Participant(
        tournament_id=tournament_id,
        user_id=data.get("user_id"),
        name=name,
        seed=data.get("seed"),
    )
    db.session.add(p)
    db.session.commit()
    publish_event(
        "tournament.participant_added",
        {
            "tournament_id": tournament_id,
            "participant_id": p.id,
            "user_id": p.user_id,
            "name": p.name,
            "added_by": getattr(g, "current_user_id", None),
        },
    )
    return jsonify(p.to_dict()), 201


@app.route("/tournaments/<tournament_id>/participants", methods=["GET"])
@auth_required()
def list_participants(tournament_id):
    Tournament.query.get_or_404(tournament_id)
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))
    participants = (
        Participant.query.filter_by(tournament_id=tournament_id)
        .limit(limit).offset(offset).all()
    )
    return jsonify([p.to_dict() for p in participants]), 200


@app.route("/tournaments/<tournament_id>/generate-bracket", methods=["POST"])
@auth_required("admin", "trainer")
def generate_bracket(tournament_id):
    t = Tournament.query.get_or_404(tournament_id)

    # Wipe any previous bracket for this tournament (regeneration support)
    force = request.args.get("force", "").lower() in ("1", "true", "yes")
    has_results = (
        Match.query.filter_by(tournament_id=tournament_id, status="finished")
        .filter(Match.winner_id.isnot(None))
        .filter(Match.participant_a_id.isnot(None))
        .first()
        is not None
    )
    if has_results and not force:
        return jsonify({"error": "bracket already has played matches; pass ?force=true to wipe"}), 409

    Match.query.filter_by(tournament_id=tournament_id).delete()

    participants = Participant.query.filter_by(tournament_id=tournament_id).order_by(
        Participant.seed.is_(None), Participant.seed
    ).all()
    participant_ids = [p.id for p in participants]

    try:
        matches = generate_single_elimination(tournament_id, participant_ids)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    for m in matches:
        db.session.add(m)
    db.session.commit()

    # Push bye winners into the next round immediately, since byes never
    # go through the /score endpoint that normally triggers this.
    byes = [m for m in matches if m.status == "finished" and m.winner_id]
    for bye in byes:
        advance_winner(tournament_id, bye)
    db.session.commit()

    t.status = "active"
    db.session.commit()

    all_matches = Match.query.filter_by(tournament_id=tournament_id).order_by(
        Match.round_number, Match.slot
    ).all()
    publish_event(
        "tournament.bracket_generated",
        {
            "tournament_id": tournament_id,
            "rounds": total_rounds(len(participant_ids)),
            "match_count": len(all_matches),
            "generated_by": getattr(g, "current_user_id", None),
        },
    )
    return jsonify([m.to_dict() for m in all_matches]), 201


@app.route("/tournaments/<tournament_id>/bracket", methods=["GET"])
@auth_required()
def get_bracket(tournament_id):
    Tournament.query.get_or_404(tournament_id)
    matches = Match.query.filter_by(tournament_id=tournament_id).order_by(
        Match.round_number, Match.slot
    ).all()
    return jsonify([m.to_dict() for m in matches]), 200


@app.route("/matches/<match_id>/schedule", methods=["POST"])
@auth_required("admin", "trainer")
def schedule_match(match_id):
    m = Match.query.get_or_404(match_id)
    data = request.get_json(force=True) or {}
    scheduled_at = data.get("scheduled_at")
    if not scheduled_at:
        return jsonify({"error": "scheduled_at is required (ISO 8601)"}), 400

    m.scheduled_at = datetime.fromisoformat(scheduled_at)
    m.status = "scheduled"
    db.session.commit()
    publish_event(
        "tournament.match_scheduled",
        {
            "tournament_id": m.tournament_id,
            "match_id": m.id,
            "round": m.round_number,
            "slot": m.slot,
            "scheduled_at": m.scheduled_at.isoformat() if m.scheduled_at else None,
            "scheduled_by": getattr(g, "current_user_id", None),
        },
    )
    return jsonify(m.to_dict()), 200


@app.route("/matches/<match_id>/score", methods=["POST"])
@auth_required("admin", "trainer")
def submit_score(match_id):
    m = Match.query.get_or_404(match_id)

    if m.status == "finished":
        return jsonify({"error": "match already has a final score"}), 409

    data = request.get_json(force=True) or {}

    if m.participant_a_id is None or m.participant_b_id is None:
        return jsonify({"error": "match is missing a participant (still waiting on a previous round)"}), 400

    score_a = data.get("score_a")
    score_b = data.get("score_b")
    if score_a is None or score_b is None:
        return jsonify({"error": "score_a and score_b are required"}), 400
    if score_a == score_b:
        return jsonify({"error": "ties are not supported in single elimination"}), 400

    try:
        m.score_a = score_a
        m.score_b = score_b
        m.winner_id = m.participant_a_id if score_a > score_b else m.participant_b_id
        loser_id = m.participant_b_id if m.winner_id == m.participant_a_id else m.participant_a_id
        m.status = "finished"
        db.session.add(m)
        advance_winner(m.tournament_id, m)
        maybe_finish_tournament(m.tournament_id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    tournament = Tournament.query.get(m.tournament_id)
    tournament_completed = bool(tournament and tournament.status == "finished")
    update_user_stats_for_match(m, loser_id, tournament_completed=tournament_completed)

    publish_event(
        "tournament.match_result_recorded",
        {
            "tournament_id": m.tournament_id,
            "match_id": m.id,
            "round": m.round_number,
            "slot": m.slot,
            "winner_id": m.winner_id,
            "loser_id": loser_id,
            "score_a": m.score_a,
            "score_b": m.score_b,
            "recorded_by": getattr(g, "current_user_id", None),
        },
    )
    if tournament_completed:
        publish_event(
            "tournament.completed",
            {
                "tournament_id": tournament.id,
                "name": tournament.name,
                "champion_participant_id": m.winner_id,
                "completed_by": getattr(g, "current_user_id", None),
            },
        )

    return jsonify(m.to_dict()), 200


def _init_db_with_retry(max_attempts=10, delay_seconds=2):
    """
    Postgres can take a few seconds to finish starting up, even after its
    container is technically running. Retrying here avoids a crash-on-boot
    race condition when this service starts before the database is ready
    to accept connections (a very common issue in Docker Compose).
    """
    for attempt in range(1, max_attempts + 1):
        try:
            with app.app_context():
                db.create_all()
            return
        except Exception as e:
            if attempt == max_attempts:
                raise
            print(f"Database not ready yet (attempt {attempt}/{max_attempts}): {e}")
            time.sleep(delay_seconds)


_init_db_with_retry()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8003))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
