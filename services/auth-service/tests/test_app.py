import pytest
from app import app, db, encrypt_field, decrypt_field


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
def test_healthz(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Registration & login
# ---------------------------------------------------------------------------
def test_register_requires_email_and_password(client):
    res = client.post("/auth/register", json={"email": "a@b.com"})
    assert res.status_code == 400


def test_register_and_login_flow(client):
    res = client.post(
        "/auth/register",
        json={"email": "jo@gym.com", "password": "secret1", "full_name": "Jo"},
    )
    assert res.status_code == 201
    body = res.get_json()
    assert "token" in body
    assert body["user"]["role"] == "member"

    res = client.post("/auth/login", json={"email": "jo@gym.com", "password": "secret1"})
    assert res.status_code == 200
    assert "token" in res.get_json()


def test_duplicate_email_rejected(client):
    client.post("/auth/register", json={"email": "dup@gym.com", "password": "secret1"})
    res = client.post("/auth/register", json={"email": "dup@gym.com", "password": "secret1"})
    assert res.status_code == 409


def test_login_with_wrong_password_fails(client):
    client.post("/auth/register", json={"email": "x@gym.com", "password": "secret1"})
    res = client.post("/auth/login", json={"email": "x@gym.com", "password": "WRONG"})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# JWT / RBAC middleware
# ---------------------------------------------------------------------------
def _register(client, email, password, role="member"):
    res = client.post(
        "/auth/register", json={"email": email, "password": password, "role": role}
    )
    return res.get_json()["token"]


def test_protected_route_requires_token(client):
    res = client.get("/me")
    assert res.status_code == 401


def test_protected_route_with_valid_token(client):
    token = _register(client, "me@gym.com", "secret1")
    res = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.get_json()["email"] == "me@gym.com"


def test_invalid_token_rejected(client):
    res = client.get("/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert res.status_code == 401


def test_member_cannot_list_users(client):
    member_token = _register(client, "member@gym.com", "secret1", role="member")
    res = client.get("/users", headers={"Authorization": f"Bearer {member_token}"})
    assert res.status_code == 403  # forbidden: RBAC blocks non-admins


def test_admin_can_list_users(client):
    admin_token = _register(client, "boss@gym.com", "secret1", role="admin")
    res = client.get("/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200


def test_admin_can_change_role(client):
    admin_token = _register(client, "boss2@gym.com", "secret1", role="admin")
    # create a member to promote
    res = client.post(
        "/auth/register", json={"email": "rookie@gym.com", "password": "secret1"}
    )
    member_id = res.get_json()["user"]["id"]

    res = client.patch(
        f"/users/{member_id}/role",
        json={"role": "trainer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.get_json()["role"] == "trainer"


# ---------------------------------------------------------------------------
# AES-256 encryption
# ---------------------------------------------------------------------------
def test_encrypt_decrypt_roundtrip():
    secret = "+1-555-0100"
    token = encrypt_field(secret)
    assert token != secret  # stored value is not plaintext
    assert decrypt_field(token) == secret


def test_phone_stored_encrypted(client):
    token = _register(client, "phone@gym.com", "secret1")
    client.patch(
        "/me",
        json={"phone": "+1-555-0199"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # The owner can read it back decrypted
    res = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert res.get_json()["phone"] == "+1-555-0199"
