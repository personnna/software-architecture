"""
Auth Service
-------------
Owns: user registration, login, JWT issuing/verification, role-based access
control (RBAC), user profiles, and staff management.

This is Yazan's core domain (User Management) inside the GYM IT System
microservices architecture. It is also responsible for the **Security**
quality attribute: JWT authentication, AES-256 encryption of sensitive
profile fields at rest, and RBAC middleware that other services rely on.
"""
import os
import time
import uuid
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt  # PyJWT
from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

app = Flask(__name__)

# DATABASE_URL is injected by docker-compose / k8s. Falls back to local sqlite
# so the service also runs standalone with zero setup.
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///auth.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Secrets are injected via environment (k8s Secret / .env). The fallbacks here
# exist ONLY so the service boots in local dev; in production these MUST be set.
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-insecure-jwt-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "12"))
SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "dev-service-token")

db = SQLAlchemy(app)

# Valid roles in the system. RBAC decisions are checked against these.
ROLES = {"admin", "trainer", "member"}


# ---------------------------------------------------------------------------
# AES-256 encryption helper (for sensitive profile fields "at rest")
# ---------------------------------------------------------------------------
def _get_aes_key():
    """
    Derive a 32-byte (256-bit) AES key from the ENCRYPTION_KEY env var.
    Using SHA-256 of the secret guarantees exactly 32 bytes regardless of the
    raw secret's length. In production ENCRYPTION_KEY must be set to a strong,
    random value and stored in a k8s Secret — never committed to git.
    """
    secret = os.environ.get("ENCRYPTION_KEY", "dev-insecure-encryption-key-change-me")
    return hashlib.sha256(secret.encode()).digest()


def encrypt_field(plaintext):
    """
    Encrypt a string using AES-256-GCM. Returns a base64 string that bundles
    the random nonce + ciphertext + auth tag, so it can be stored in a single
    text column. GCM also authenticates the data (tamper detection).
    """
    if plaintext is None:
        return None
    aesgcm = AESGCM(_get_aes_key())
    nonce = os.urandom(12)  # 96-bit nonce recommended for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_field(token):
    """Reverse of encrypt_field(). Returns the original plaintext string."""
    if token is None:
        return None
    raw = base64.b64decode(token.encode())
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(_get_aes_key())
    return aesgcm.decrypt(nonce, ciphertext, None).decode()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="member")  # admin | trainer | member
    full_name = db.Column(db.String(120), nullable=True)

    # Stored ENCRYPTED at rest (AES-256-GCM). Never written in plaintext.
    phone_encrypted = db.Column(db.Text, nullable=True)

    tournaments_played = db.Column(db.Integer, default=0)
    tournament_wins = db.Column(db.Integer, default=0)
    tournament_losses = db.Column(db.Integer, default=0)
    tournament_points = db.Column(db.Integer, default=0)
    tournament_championships = db.Column(db.Integer, default=0)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_phone(self, phone):
        self.phone_encrypted = encrypt_field(phone)

    def get_phone(self):
        try:
            return decrypt_field(self.phone_encrypted)
        except Exception:
            # If the key changed or data is corrupt, fail closed rather than crash.
            return None

    def to_dict(self, include_phone=False):
        data = {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "stats": {
                "tournaments_played": self.tournaments_played,
                "wins": self.tournament_wins,
                "losses": self.tournament_losses,
                "points": self.tournament_points,
                "championships": self.tournament_championships,
            },
            "created_at": self.created_at.isoformat(),
        }
        # Phone is sensitive: only decrypt+return when explicitly requested
        # (e.g. the user viewing their own profile, or an admin).
        if include_phone:
            data["phone"] = self.get_phone()
        return data


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def generate_token(user):
    """Issue a signed JWT carrying the user id and role (used by RBAC)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token):
    """Verify signature + expiry and return the payload, or raise."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# RBAC middleware
# ---------------------------------------------------------------------------
def auth_required(*allowed_roles):
    """
    Decorator that protects an endpoint. It:
      1. Reads the Bearer token from the Authorization header.
      2. Verifies the JWT (signature + expiry).
      3. Optionally checks the user's role against `allowed_roles`.

    Other microservices in the system verify tokens the same way using the
    shared JWT_SECRET, so this middleware is the single source of truth for
    "who is allowed to do what".

    Usage:
        @auth_required()                  # any logged-in user
        @auth_required("admin")           # admins only
        @auth_required("admin", "trainer")  # admins or trainers
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify({"error": "missing or malformed Authorization header"}), 401

            token = header.split(" ", 1)[1].strip()
            try:
                payload = decode_token(token)
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "token has expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "invalid token"}), 401

            # Stash the caller's identity for the handler to use.
            g.current_user_id = payload["sub"]
            g.current_user_role = payload["role"]

            if allowed_roles and payload["role"] not in allowed_roles:
                return jsonify({"error": "forbidden: insufficient role"}), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def _service_token_required():
    token = request.headers.get("X-Service-Token")
    if not token or token != SERVICE_TOKEN:
        return jsonify({"error": "forbidden: invalid service token"}), 403
    return None


# ---------------------------------------------------------------------------
# Routes — health
# ---------------------------------------------------------------------------
@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "service": "auth-service"}), 200


# ---------------------------------------------------------------------------
# Routes — authentication
# ---------------------------------------------------------------------------
@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400
    if "@" not in email:
        return jsonify({"error": "invalid email"}), 400
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    role = data.get("role", "member")
    if role not in ROLES:
        return jsonify({"error": f"role must be one of {sorted(ROLES)}"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already registered"}), 409

    user = User(
        email=email,
        # Passwords are NEVER stored in plaintext — salted hash via werkzeug.
        password_hash=generate_password_hash(password),
        role=role,
        full_name=data.get("full_name"),
    )
    if data.get("phone"):
        user.set_phone(data["phone"])  # encrypted at rest

    db.session.add(user)
    db.session.commit()

    token = generate_token(user)
    return jsonify({"user": user.to_dict(), "token": token}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password")

    user = User.query.filter_by(email=email).first()
    # Same generic error whether the email is unknown or the password is wrong,
    # so attackers can't tell which emails exist (avoids user enumeration).
    if not user or not check_password_hash(user.password_hash, password or ""):
        return jsonify({"error": "invalid credentials"}), 401
    if not user.is_active:
        return jsonify({"error": "account is disabled"}), 403

    token = generate_token(user)
    return jsonify({"user": user.to_dict(), "token": token}), 200


@app.route("/auth/verify", methods=["GET"])
@auth_required()
def verify():
    """
    Lightweight endpoint other services can call (or replicate) to confirm a
    token is valid and learn the caller's identity/role.
    """
    return jsonify({"user_id": g.current_user_id, "role": g.current_user_role}), 200


# ---------------------------------------------------------------------------
# Routes — profile (self-service)
# ---------------------------------------------------------------------------
@app.route("/me", methods=["GET"])
@auth_required()
def get_my_profile():
    user = User.query.get_or_404(g.current_user_id)
    return jsonify(user.to_dict(include_phone=True)), 200


@app.route("/me", methods=["PATCH"])
@auth_required()
def update_my_profile():
    user = User.query.get_or_404(g.current_user_id)
    data = request.get_json(force=True) or {}

    if "full_name" in data:
        user.full_name = data["full_name"]
    if "phone" in data:
        user.set_phone(data["phone"])  # re-encrypt

    # Note: a user cannot change their own role here — that's an admin action.
    db.session.commit()
    return jsonify(user.to_dict(include_phone=True)), 200


# ---------------------------------------------------------------------------
# Routes — admin: user & staff management
# ---------------------------------------------------------------------------
@app.route("/users", methods=["GET"])
@auth_required("admin")
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([u.to_dict() for u in users]), 200


@app.route("/users/<user_id>", methods=["GET"])
@auth_required("admin")
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict(include_phone=True)), 200


@app.route("/users/<user_id>/role", methods=["PATCH"])
@auth_required("admin")
def change_user_role(user_id):
    """Admin-only: promote/demote a user (e.g. make someone a trainer)."""
    user = User.query.get_or_404(user_id)
    data = request.get_json(force=True) or {}
    new_role = data.get("role")
    if new_role not in ROLES:
        return jsonify({"error": f"role must be one of {sorted(ROLES)}"}), 400

    user.role = new_role
    db.session.commit()
    return jsonify(user.to_dict()), 200


@app.route("/users/<user_id>/status", methods=["PATCH"])
@auth_required("admin")
def set_user_status(user_id):
    """Admin-only: activate/deactivate an account (soft account control)."""
    user = User.query.get_or_404(user_id)
    data = request.get_json(force=True) or {}
    is_active = data.get("is_active")
    if not isinstance(is_active, bool):
        return jsonify({"error": "is_active must be a boolean"}), 400

    user.is_active = is_active
    db.session.commit()
    return jsonify(user.to_dict()), 200


@app.route("/users/<user_id>/tournament-stats", methods=["PATCH"])
def update_tournament_stats(user_id):
    """
    Internal endpoint used by tournament-service after match results.
    Protected by a shared service token instead of user JWT because this is an
    inter-service write, not an end-user operation.
    """
    error = _service_token_required()
    if error:
        return error

    user = User.query.get_or_404(user_id)
    data = request.get_json(force=True) or {}

    if data.get("played"):
        user.tournaments_played += 1
    if data.get("win"):
        user.tournament_wins += 1
    if data.get("loss"):
        user.tournament_losses += 1
    if data.get("champion"):
        user.tournament_championships += 1

    user.tournament_points += int(data.get("points_delta", 0))
    db.session.commit()
    return jsonify(user.to_dict()), 200


# ---------------------------------------------------------------------------
# DB init with retry (handles Postgres not being ready at boot)
# ---------------------------------------------------------------------------
def _seed_default_admin():
    """
    Create a default admin on first boot so the system is usable immediately,
    mirroring the project's documented admin@gym.com / admin credentials.
    """
    if User.query.filter_by(email="admin@gym.com").first():
        return
    admin = User(
        email="admin@gym.com",
        password_hash=generate_password_hash("admin"),
        role="admin",
        full_name="Default Admin",
    )
    db.session.add(admin)
    db.session.commit()


def _migrate_stats_columns():
    """Small dev migration for existing SQLite/Postgres databases."""
    try:
        from sqlalchemy import inspect, text

        inspector = inspect(db.engine)
        if "user" not in inspector.get_table_names():
            return
        existing = {column["name"] for column in inspector.get_columns("user")}
        columns = {
            "tournaments_played": "INTEGER DEFAULT 0",
            "tournament_wins": "INTEGER DEFAULT 0",
            "tournament_losses": "INTEGER DEFAULT 0",
            "tournament_points": "INTEGER DEFAULT 0",
            "tournament_championships": "INTEGER DEFAULT 0",
        }
        with db.engine.begin() as conn:
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE \"user\" ADD COLUMN {name} {ddl}"))
    except Exception as e:
        print(f"Warning: tournament stats migration skipped: {e}")


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
                _migrate_stats_columns()
                _seed_default_admin()
            return
        except Exception as e:
            if attempt == max_attempts:
                raise
            print(f"Database not ready yet (attempt {attempt}/{max_attempts}): {e}")
            time.sleep(delay_seconds)


_init_db_with_retry()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
