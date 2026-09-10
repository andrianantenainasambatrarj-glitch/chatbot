"""Tests Sprint 4 : partage, quotas, admin, e-mail, webhook, métriques, diarisation."""

import io

import integrations


def transcribe_one(client, headers, form=None):
    data = {"audio": (io.BytesIO(b"audio"), "a.webm")}
    if form:
        data.update(form)
    return client.post(
        "/api/transcribe",
        data=data,
        content_type="multipart/form-data",
        headers=headers,
    )


def test_insights_endpoint(client, register):
    headers = register()
    # La transcription mockée est très courte ; on patche l'analyse via le texte
    created = transcribe_one(client, headers).get_json()
    response = client.post(f"/api/transcriptions/{created['id']}/insights", headers=headers)
    assert response.status_code == 200
    body = response.get_json()
    assert "summary" in body
    assert "keywords" in body
    assert "sentiment" in body


def test_chat_endpoint(client, register):
    headers = register()
    created = transcribe_one(client, headers).get_json()
    response = client.post(
        f"/api/transcriptions/{created['id']}/chat",
        headers=headers,
        json={"message": "De quoi parle le texte ?"},
    )
    assert response.status_code == 200
    assert response.get_json()["reply"]


def test_chat_requires_message(client, register):
    headers = register()
    created = transcribe_one(client, headers).get_json()
    response = client.post(
        f"/api/transcriptions/{created['id']}/chat", headers=headers, json={}
    )
    assert response.status_code == 400


def test_share_link_flow(client, register):
    alice = register("alice@example.com")
    bob = register("bob@example.com")
    created = transcribe_one(client, alice).get_json()

    # Création du lien
    response = client.post(f"/api/transcriptions/{created['id']}/share", headers=alice)
    assert response.status_code == 201
    token = response.get_json()["token"]

    # Accès PUBLIC sans jeton d'authentification
    public = client.get(f"/api/shared/{token}")
    assert public.status_code == 200
    assert public.get_json()["id"] == created["id"]

    exported = client.get(f"/api/shared/{token}/export/txt")
    assert exported.status_code == 200

    # Le lien est listé ; Bob ne peut pas le révoquer
    listed = client.get(f"/api/transcriptions/{created['id']}/share", headers=alice)
    assert token in [link["token"] for link in listed.get_json()]
    assert client.delete(
        f"/api/transcriptions/{created['id']}/share/{token}", headers=bob
    ).status_code == 404

    # Alice le révoque -> 404 ensuite
    assert client.delete(
        f"/api/transcriptions/{created['id']}/share/{token}", headers=alice
    ).status_code == 204
    assert client.get(f"/api/shared/{token}").status_code == 404


def test_shared_invalid_token(client):
    assert client.get("/api/shared/jeton-inconnu").status_code == 404


def test_email_endpoint(client, register, monkeypatch):
    headers = register()
    created = transcribe_one(client, headers).get_json()

    sent = {}

    def fake_send(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr(integrations, "send_transcription_email", fake_send)
    response = client.post(
        f"/api/transcriptions/{created['id']}/email",
        headers=headers,
        json={"email": "destinataire@example.com"},
    )
    assert response.status_code == 200
    assert sent["to_email"] == "destinataire@example.com"

    # E-mail invalide
    bad = client.post(
        f"/api/transcriptions/{created['id']}/email",
        headers=headers,
        json={"email": "pas-un-email"},
    )
    assert bad.status_code == 400


def test_email_not_configured(client, register, monkeypatch):
    headers = register()
    created = transcribe_one(client, headers).get_json()

    def raise_not_configured(**kwargs):
        raise integrations.EmailNotConfiguredError("SMTP absent")

    monkeypatch.setattr(integrations, "send_transcription_email", raise_not_configured)
    response = client.post(
        f"/api/transcriptions/{created['id']}/email",
        headers=headers,
        json={"email": "a@b.co"},
    )
    assert response.status_code == 503


def test_webhook_endpoint(client, register, monkeypatch):
    headers = register()
    created = transcribe_one(client, headers).get_json()

    captured = {}

    def fake_post_webhook(url, payload, timeout=15):
        captured["url"] = url
        captured["payload"] = payload
        return 200

    monkeypatch.setattr(integrations, "post_webhook", fake_post_webhook)
    response = client.post(
        f"/api/transcriptions/{created['id']}/webhook",
        headers=headers,
        json={"url": "https://automate.example.com/hook"},
    )
    assert response.status_code == 200
    assert captured["payload"]["event"] == "transcription.created"

    bad = client.post(
        f"/api/transcriptions/{created['id']}/webhook",
        headers=headers,
        json={"url": "ftp://interdit"},
    )
    assert bad.status_code == 400


def test_stats_endpoint(client, register):
    headers = register()
    transcribe_one(client, headers)
    transcribe_one(client, headers)
    response = client.get("/api/stats", headers=headers)
    assert response.status_code == 200
    stats = response.get_json()
    assert stats["total_transcriptions"] == 2
    assert "daily" in stats and "by_engine" in stats


def test_metrics_protected_by_token(tmp_path, monkeypatch):
    import chatbot as cb
    from config import Config

    class MetricsConfig(Config):
        DATA_DIR = str(tmp_path / "m")
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'm.db'}"
        RATELIMIT_ENABLED = False
        METRICS_TOKEN = "secret-token"

    application = cb.create_app(MetricsConfig)
    test_client = application.test_client()
    assert test_client.get("/metrics").status_code == 401
    response = test_client.get("/metrics", headers={"Authorization": "Bearer secret-token"})
    assert response.status_code == 200
    assert "chatbot_uptime_seconds" in response.get_data(as_text=True)


def test_admin_access_and_quota(tmp_path, monkeypatch):
    import chatbot as cb
    from config import Config

    class AdminConfig(Config):
        DATA_DIR = str(tmp_path / "a")
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'a.db'}"
        RATELIMIT_ENABLED = False
        ADMIN_EMAILS = ["boss@example.com"]
        DEFAULT_QUOTA_MINUTES = 1

    from tests.conftest import FakeEngine

    fake = FakeEngine()
    monkeypatch.setattr(cb, "get_engine", lambda _n=None: fake)
    monkeypatch.setattr("services.get_engine", lambda _n=None: fake)
    monkeypatch.setattr("services.prepare_audio", lambda _src: ("/tmp/x.wav", 120.0))

    app = cb.create_app(AdminConfig)
    client = app.test_client()

    admin = client.post(
        "/api/auth/register",
        json={"email": "boss@example.com", "password": "motdepasse123"},
    ).get_json()
    normal = client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "motdepasse123"},
    ).get_json()
    admin_headers = {"Authorization": f"Bearer {admin['token']}"}
    user_headers = {"Authorization": f"Bearer {normal['token']}"}

    # Le premier audio fait 120 s = 2 minutes, quota 1 minute -> 402
    response = client.post(
        "/api/transcribe",
        data={"audio": (io.BytesIO(b"x"), "a.webm")},
        content_type="multipart/form-data",
        headers=user_headers,
    )
    assert response.status_code == 402
    assert response.get_json()["code"] == "quota_exceeded"

    # L'admin relève le quota à 100 minutes
    user_id = normal["user"]["id"]
    patched = client.patch(
        f"/api/admin/users/{user_id}",
        headers=admin_headers,
        json={"monthly_quota_minutes": 100},
    )
    assert patched.status_code == 200
    assert client.post(
        "/api/transcribe",
        data={"audio": (io.BytesIO(b"x"), "a.webm")},
        content_type="multipart/form-data",
        headers=user_headers,
    ).status_code == 201

    # Un utilisateur normal n'a pas accès à l'admin
    assert client.get("/api/admin/users", headers=user_headers).status_code == 403
    listing = client.get("/api/admin/users", headers=admin_headers)
    assert listing.status_code == 200
    assert len(listing.get_json()) == 2
    totals = client.get("/api/admin/stats", headers=admin_headers).get_json()
    assert totals["users"] == 2 and totals["transcriptions"] >= 1
