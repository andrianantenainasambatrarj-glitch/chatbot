"""Moteurs de reconnaissance vocale.

Chaque moteur implémente :
  - transcribe(wav_path, language, progress=None) -> (texte, mots_horodatés)
  - metadata() -> informations pour l'API /api/engines
"""

from engines.vosk_engine import VoskEngine
from engines.whisper_engine import WhisperEngine


class UnknownEngineError(ValueError):
    """Moteur demandé inconnu."""


_engines = {}


def get_engine(name):
    name = (name or "vosk").lower()
    if name not in ("vosk", "whisper"):
        raise UnknownEngineError(
            f"Moteur '{name}' inconnu. Moteurs disponibles : vosk, whisper."
        )
    if name not in _engines:
        _engines[name] = VoskEngine() if name == "vosk" else WhisperEngine()
    return _engines[name]


def engines_metadata():
    """Décrit les moteurs et leurs langues pour l'interface."""
    return [get_engine("vosk").metadata(), get_engine("whisper").metadata()]


__all__ = [
    "get_engine",
    "engines_metadata",
    "UnknownEngineError",
    "VoskEngine",
    "WhisperEngine",
]
