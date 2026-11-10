import jwt

from app.config import get_settings
from app.security import hash_password, verify_password


def test_password_hash_roundtrip():
    stored = hash_password("correct horse")
    assert stored != "correct horse"
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("anything", "garbage")


def test_register_and_login(client):
    body = {"email": "Alice@Example.com", "name": "Alice", "password": "password123"}
    resp = client.post("/api/auth/register", json=body)
    assert resp.status_code == 201
    assert resp.json()["user"]["role"] == "student"
    assert resp.json()["user"]["email"] == "alice@example.com"  # normalised

    login = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["name"] == "Alice"


def test_duplicate_email_rejected(client):
    body = {"email": "a@example.com", "name": "A", "password": "password123"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json=body).status_code == 409


def test_short_password_rejected(client):
    resp = client.post(
        "/api/auth/register", json={"email": "a@example.com", "name": "A", "password": "short"}
    )
    assert resp.status_code == 422


def test_wrong_password_and_unknown_user_look_the_same(client, student_headers):
    wrong = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "nope-nope-nope"}
    )
    unknown = client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_instructor_requires_valid_invite_code(client):
    base = {"email": "p@example.com", "name": "P", "password": "password123", "role": "instructor"}
    assert client.post("/api/auth/register", json=base).status_code == 403
    assert (
        client.post("/api/auth/register", json={**base, "invite_code": "wrong"}).status_code == 403
    )
    ok = client.post("/api/auth/register", json={**base, "invite_code": "invite-123"})
    assert ok.status_code == 201
    assert ok.json()["user"]["role"] == "instructor"


def test_missing_and_tampered_tokens_rejected(client, student_headers):
    assert client.get("/api/auth/me").status_code == 401
    bad = {"Authorization": "Bearer not.a.token"}
    assert client.get("/api/auth/me", headers=bad).status_code == 401

    forged = jwt.encode({"sub": "1", "role": "instructor"}, "wrong-key" * 4, algorithm="HS256")
    headers = {"Authorization": f"Bearer {forged}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_expired_token_rejected(client, student_headers):
    settings = get_settings()
    expired = jwt.encode(
        {"sub": "1", "role": "student", "exp": 1}, settings.secret_key, algorithm="HS256"
    )
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
