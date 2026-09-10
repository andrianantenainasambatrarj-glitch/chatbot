"""Configuration des tests pytest : application isolée dans un dossier temporaire."""

import io

import pytest

import chatbot
from config import Config

WORDS = [
    {"word": "bonjour", "start": 0.0, "end": 0.5},
    {"word": "ceci", "start": 0.5, "end": 0.9},
    {"word": "est", "start": 0.9, "end": 1.1},
    {"word": "un", "start": 1.1, "end": 1.3},
    {"word": "test", "start": 1.3, "end": 1.8},
]
TRANSCRIPT = "bonjour ceci est un test"


@pytest.fixture
def app(tmp_path, monkeypatch):
    class TestConfig(Config):
        DATA_DIR = str(tmp_path)
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"
        RATELIMIT_ENABLED = False
        TRANSCRIBE_RESULT = (
            TRANSCRIPT,
            [dict(w) for w in WORDS],
            1.8,
        )

    # Le pipeline Vosk/ffmpeg est mocké : les tests ne dépendent ni du modèle ni de ffmpeg
    def fake_pipeline(_src_path, _get_model):
        return TestConfig.TRANSCRIBE_RESULT

    monkeypatch.setattr(chatbot, "prepare_and_transcribe", fake_pipeline)
    monkeypatch.setattr(chatbot, "get_model", lambda: object())

    application = chatbot.create_app(TestConfig)
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


def audio_file(content=b"audio-bidon", filename="recording.webm"):
    return io.BytesIO(content), filename
