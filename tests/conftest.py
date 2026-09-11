"""Configuration des tests pytest : application isolée, moteur et ffmpeg mockés."""

import io
import json

import pytest

import chatbot
import services
from config import Config

WORDS = [
    {"word": "bonjour", "start": 0.0, "end": 0.5},
    {"word": "ceci", "start": 0.5, "end": 0.9},
    {"word": "est", "start": 0.9, "end": 1.1},
    {"word": "un", "start": 1.1, "end": 1.3},
    {"word": "test", "start": 1.3, "end": 1.8},
]
TRANSCRIPT = "bonjour ceci est un test"


class FakeRecognizer:
    """Simule un KaldiRecognizer Vosk."""

    def __init__(self):
        self.chunks = 0
        self.words_enabled = False

    def SetWords(self, value):
        self.words_enabled = value

    def AcceptWaveform(self, _data):
        self.chunks += 1
        return self.chunks % 3 == 0  # un résultat final toutes les 3 trames

    def Result(self):
        if self.chunks % 3 == 0:
            return json.dumps(
                {"text": f"partie {self.chunks}", "result": WORDS[:2]}
            )
        return json.dumps({})

    def PartialResult(self):
        return json.dumps({"partial": "transcription partielle"})

    def FinalResult(self):
        return json.dumps({"text": "texte final", "result": WORDS[2:]})


class FakeEngine:
    name = "vosk"

    def transcribe(self, _wav_path, _language="fr", progress=None, timestamps=False):
        if progress:
            progress(50)
            progress(100)
        return TRANSCRIPT, [dict(w) for w in WORDS]

    def create_recognizer(self, _language):
        return FakeRecognizer()

    def metadata(self):
        return {"name": "vosk", "languages": [{"code": "fr", "available": True}]}


@pytest.fixture
def app(tmp_path, monkeypatch):
    class TestConfig(Config):
        DATA_DIR = str(tmp_path)
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"
        RATELIMIT_ENABLED = False
        JOB_WORKERS = 2
        PREWARM_MODELS = False
        VOSK_MODELS = {"fr": "models/fake-fr", "en": "models/fake-en"}

    def fake_factory(_name=None):
        return FakeEngine()

    # ffmpeg est mocké : la conversion est considérée comme acquise
    monkeypatch.setattr(services, "prepare_audio", lambda _src: ("/tmp/fake-converted.wav", 1.8))
    monkeypatch.setattr(chatbot, "get_engine", fake_factory)
    monkeypatch.setattr(services, "get_engine", fake_factory)

    application = chatbot.create_app(TestConfig)
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def register(client):
    """Crée un compte et retourne les en-têtes d'authentification."""

    def _register(email="alice@example.com", password="motdepasse123"):
        response = client.post(
            "/api/auth/register", json={"email": email, "password": password}
        )
        assert response.status_code == 201, response.get_json()
        token = response.get_json()["token"]
        return {"Authorization": f"Bearer {token}"}

    return _register


def audio_bytes(content=b"audio-bidon"):
    return io.BytesIO(content)
