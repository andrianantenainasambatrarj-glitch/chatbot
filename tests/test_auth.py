"""Tests de l'authentification et de l'isolation des données."""


def test_register_creates_token(client):
    response = client.post(
        "/api/auth/register", json={"email": "user@example.com", "password": "motdepasse123"}
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["token"]
    assert body["user"]["email"] == "user@example.com"


def test_register_rejects_bad_email_and_short_password(client):
    r1 = client.post("/api/auth/register", json={"email": "pas-un-email", "password": "motdepasse123"})
    assert r1.status_code == 400
    r2 = client.post("/api/auth/register", json={"email": "a@b.co", "password": "court"})
    assert r2.status_code == 400


def test_register_duplicate_email_returns_409(client, register):
    register("dup@example.com")
    response = client.post(
        "/api/auth/register", json={"email": "dup@example.com", "password": "motdepasse123"}
    )
    assert response.status_code == 409


def test_login_flow(client, register):
    register("login@example.com", "motdepasse123")
    bad = client.post(
        "/api/auth/login", json={"email": "login@example.com", "password": "mauvais"}
    )
    assert bad.status_code == 401
    ok = client.post(
        "/api/auth/login", json={"email": "login@example.com", "password": "motdepasse123"}
    )
    assert ok.status_code == 200 and ok.get_json()["token"]


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_token(client, register):
    headers = register()
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["email"] == "alice@example.com"


def test_protected_endpoints_require_auth(client):
    assert client.get("/api/transcriptions").status_code == 401
    assert client.get("/api/jobs").status_code == 401
    assert client.delete("/api/transcriptions").status_code == 401


def test_invalid_token_rejected(client):
    response = client.get(
        "/api/transcriptions", headers={"Authorization": "Bearer jeton-faux"}
    )
    assert response.status_code == 401


def test_users_cannot_see_each_other_transcriptions(client, register):
    alice = register("alice@example.com")
    bob = register("bob@example.com")

    created = client.post(
        "/api/transcribe",
        data={"audio": (__import__("io").BytesIO(b"x"), "a.webm")},
        content_type="multipart/form-data",
        headers=alice,
    )
    assert created.status_code == 201
    transcription_id = created.get_json()["id"]

    # La liste de Bob est vide
    assert client.get("/api/transcriptions", headers=bob).get_json() == []
    # Bob ne peut ni lire, ni exporter, ni supprimer la transcription d'Alice
    assert client.get(f"/api/transcriptions/{transcription_id}", headers=bob).status_code == 404
    assert client.get(f"/api/transcriptions/{transcription_id}/export/docx", headers=bob).status_code == 404
    assert client.delete(f"/api/transcriptions/{transcription_id}", headers=bob).status_code == 404
