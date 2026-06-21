import pytest
import jwt
from datetime import datetime, timedelta, timezone
from app import app, db

JWT_SECRET = "dev-insecure-jwt-secret-change-me"


def token_for(role="admin", user_id="test-user"):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "email": f"{role}@gym.com",
            "role": role,
            "iat": now,
            "exp": now + timedelta(hours=1),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def auth_headers(role="admin", user_id="test-user"):
    return {"Authorization": f"Bearer {token_for(role=role, user_id=user_id)}"}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as c:
        yield c


def test_healthz(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_create_tournament_requires_name(client):
    res = client.post("/tournaments", json={}, headers=auth_headers())
    assert res.status_code == 400


def test_member_cannot_create_tournament(client):
    res = client.post(
        "/tournaments",
        json={"name": "Member Cup"},
        headers=auth_headers(role="member"),
    )
    assert res.status_code == 403


def test_authenticated_member_can_list_tournaments(client):
    client.post("/tournaments", json={"name": "Visible Cup"}, headers=auth_headers())
    res = client.get("/tournaments", headers=auth_headers(role="member"))
    assert res.status_code == 200


def test_full_bracket_flow(client):
    res = client.post("/tournaments", json={"name": "Cup"}, headers=auth_headers())
    tid = res.get_json()["id"]

    for n in ["A", "B", "C", "D"]:
        client.post(f"/tournaments/{tid}/participants", json={"name": n}, headers=auth_headers())

    res = client.post(f"/tournaments/{tid}/generate-bracket", headers=auth_headers())
    assert res.status_code == 201
    matches = res.get_json()
    assert len(matches) == 3  # 2 semis + 1 final for 4 participants

    semi = [m for m in matches if m["round"] == 1][0]
    res = client.post(
        f"/matches/{semi['id']}/score",
        json={"score_a": 10, "score_b": 3},
        headers=auth_headers(),
    )
    assert res.status_code == 200
    assert res.get_json()["status"] == "finished"


def test_tie_rejected(client):
    res = client.post("/tournaments", json={"name": "Cup2"}, headers=auth_headers())
    tid = res.get_json()["id"]
    client.post(f"/tournaments/{tid}/participants", json={"name": "A"}, headers=auth_headers())
    client.post(f"/tournaments/{tid}/participants", json={"name": "B"}, headers=auth_headers())
    res = client.post(f"/tournaments/{tid}/generate-bracket", headers=auth_headers())
    match_id = res.get_json()[0]["id"]

    res = client.post(
        f"/matches/{match_id}/score",
        json={"score_a": 5, "score_b": 5},
        headers=auth_headers(),
    )
    assert res.status_code == 400


def test_tournament_dates(client):
    res = client.post(
        "/tournaments",
        json={"name": "Dated Cup", "start_date": "2026-07-01", "end_date": "2026-07-05"},
        headers=auth_headers(),
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["start_date"] == "2026-07-01"
    assert data["end_date"] == "2026-07-05"


def test_end_date_before_start_date_rejected(client):
    res = client.post(
        "/tournaments",
        json={"name": "Bad Dates", "start_date": "2026-07-05", "end_date": "2026-07-01"},
        headers=auth_headers(),
    )
    assert res.status_code == 400


def test_cannot_rescore_finished_match(client):
    res = client.post("/tournaments", json={"name": "Cup"}, headers=auth_headers())
    tid = res.get_json()["id"]
    for n in ["A", "B"]:
        client.post(f"/tournaments/{tid}/participants", json={"name": n}, headers=auth_headers())
    res = client.post(f"/tournaments/{tid}/generate-bracket", headers=auth_headers())
    match_id = res.get_json()[0]["id"]
    res = client.post(
        f"/matches/{match_id}/score",
        json={"score_a": 10, "score_b": 3},
        headers=auth_headers(),
    )
    assert res.status_code == 200
    res = client.post(
        f"/matches/{match_id}/score",
        json={"score_a": 5, "score_b": 1},
        headers=auth_headers(),
    )
    assert res.status_code == 409


def test_tournament_finishes_after_final(client):
    res = client.post("/tournaments", json={"name": "Cup"}, headers=auth_headers())
    tid = res.get_json()["id"]
    for n in ["A", "B"]:
        client.post(f"/tournaments/{tid}/participants", json={"name": n}, headers=auth_headers())
    res = client.post(f"/tournaments/{tid}/generate-bracket", headers=auth_headers())
    final_id = res.get_json()[0]["id"]
    client.post(
        f"/matches/{final_id}/score",
        json={"score_a": 10, "score_b": 3},
        headers=auth_headers(),
    )
    res = client.get(f"/tournaments/{tid}", headers=auth_headers(role="member"))
    assert res.get_json()["status"] == "finished"


def test_regenerate_blocked_after_results(client):
    res = client.post("/tournaments", json={"name": "Cup"}, headers=auth_headers())
    tid = res.get_json()["id"]
    for n in ["A", "B"]:
        client.post(f"/tournaments/{tid}/participants", json={"name": n}, headers=auth_headers())
    res = client.post(f"/tournaments/{tid}/generate-bracket", headers=auth_headers())
    final_id = res.get_json()[0]["id"]
    client.post(
        f"/matches/{final_id}/score",
        json={"score_a": 10, "score_b": 3},
        headers=auth_headers(),
    )
    res = client.post(f"/tournaments/{tid}/generate-bracket", headers=auth_headers())
    assert res.status_code == 409
    res = client.post(f"/tournaments/{tid}/generate-bracket?force=true", headers=auth_headers())
    assert res.status_code == 201


def test_tournament_list_pagination(client):
    for i in range(5):
        client.post("/tournaments", json={"name": f"T{i}"}, headers=auth_headers())
    res = client.get("/tournaments?limit=2", headers=auth_headers(role="member"))
    assert res.status_code == 200
    assert len(res.get_json()) == 2
