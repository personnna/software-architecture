import pytest
from app import app, db


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
    res = client.post("/tournaments", json={})
    assert res.status_code == 400


def test_full_bracket_flow(client):
    res = client.post("/tournaments", json={"name": "Cup"})
    tid = res.get_json()["id"]

    for n in ["A", "B", "C", "D"]:
        client.post(f"/tournaments/{tid}/participants", json={"name": n})

    res = client.post(f"/tournaments/{tid}/generate-bracket")
    assert res.status_code == 201
    matches = res.get_json()
    assert len(matches) == 3  # 2 semis + 1 final for 4 participants

    semi = [m for m in matches if m["round"] == 1][0]
    res = client.post(
        f"/matches/{semi['id']}/score", json={"score_a": 10, "score_b": 3}
    )
    assert res.status_code == 200
    assert res.get_json()["status"] == "finished"


def test_tie_rejected(client):
    res = client.post("/tournaments", json={"name": "Cup2"})
    tid = res.get_json()["id"]
    client.post(f"/tournaments/{tid}/participants", json={"name": "A"})
    client.post(f"/tournaments/{tid}/participants", json={"name": "B"})
    res = client.post(f"/tournaments/{tid}/generate-bracket")
    match_id = res.get_json()[0]["id"]

    res = client.post(f"/matches/{match_id}/score", json={"score_a": 5, "score_b": 5})
    assert res.status_code == 400


def test_tournament_dates(client):
    res = client.post(
        "/tournaments",
        json={"name": "Dated Cup", "start_date": "2026-07-01", "end_date": "2026-07-05"},
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["start_date"] == "2026-07-01"
    assert data["end_date"] == "2026-07-05"


def test_end_date_before_start_date_rejected(client):
    res = client.post(
        "/tournaments",
        json={"name": "Bad Dates", "start_date": "2026-07-05", "end_date": "2026-07-01"},
    )
    assert res.status_code == 400


def test_cannot_rescore_finished_match(client):
    res = client.post("/tournaments", json={"name": "Cup"})
    tid = res.get_json()["id"]
    for n in ["A", "B"]:
        client.post(f"/tournaments/{tid}/participants", json={"name": n})
    res = client.post(f"/tournaments/{tid}/generate-bracket")
    match_id = res.get_json()[0]["id"]
    res = client.post(f"/matches/{match_id}/score", json={"score_a": 10, "score_b": 3})
    assert res.status_code == 200
    res = client.post(f"/matches/{match_id}/score", json={"score_a": 5, "score_b": 1})
    assert res.status_code == 409


def test_tournament_finishes_after_final(client):
    res = client.post("/tournaments", json={"name": "Cup"})
    tid = res.get_json()["id"]
    for n in ["A", "B"]:
        client.post(f"/tournaments/{tid}/participants", json={"name": n})
    res = client.post(f"/tournaments/{tid}/generate-bracket")
    final_id = res.get_json()[0]["id"]
    client.post(f"/matches/{final_id}/score", json={"score_a": 10, "score_b": 3})
    res = client.get(f"/tournaments/{tid}")
    assert res.get_json()["status"] == "finished"


def test_regenerate_blocked_after_results(client):
    res = client.post("/tournaments", json={"name": "Cup"})
    tid = res.get_json()["id"]
    for n in ["A", "B"]:
        client.post(f"/tournaments/{tid}/participants", json={"name": n})
    res = client.post(f"/tournaments/{tid}/generate-bracket")
    final_id = res.get_json()[0]["id"]
    client.post(f"/matches/{final_id}/score", json={"score_a": 10, "score_b": 3})
    res = client.post(f"/tournaments/{tid}/generate-bracket")
    assert res.status_code == 409
    res = client.post(f"/tournaments/{tid}/generate-bracket?force=true")
    assert res.status_code == 201
