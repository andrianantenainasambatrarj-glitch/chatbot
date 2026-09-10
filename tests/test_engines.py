"""Tests des moteurs de reconnaissance."""

import pytest

from engines import UnknownEngineError, get_engine
from engines.vosk_engine import VoskEngine
from engines.whisper_engine import WhisperEngine, WhisperUnavailableError


def test_factory_returns_engines():
    assert isinstance(get_engine("vosk"), VoskEngine)
    assert isinstance(get_engine("whisper"), WhisperEngine)
    assert isinstance(get_engine("VOSK"), VoskEngine)


def test_unknown_engine():
    with pytest.raises(UnknownEngineError):
        get_engine("siri")


def test_whisper_raises_when_not_installed(monkeypatch, app):
    engine = WhisperEngine()
    monkeypatch.setattr(WhisperEngine, "is_installed", staticmethod(lambda: False))
    with app.app_context():
        with pytest.raises(WhisperUnavailableError):
            engine.transcribe("/tmp/quelque-chose.wav", "fr")


def test_vosk_missing_language_model(app, monkeypatch):
    engine = VoskEngine()
    with app.app_context():
        with pytest.raises(Exception):  # ModelUnavailableError
            engine._get_model("xx-langue-inexistante")
