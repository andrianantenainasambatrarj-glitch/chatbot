"""Configuration de l'application, lue depuis les variables d'environnement."""

import os


def _bool(name, default=False):
    return os.environ.get(name, "1" if default else "0") == "1"


class Config:
    # Chemins
    MODEL_PATH = os.environ.get("MODEL_PATH", "models/vosk-model-small-fr-0.22")
    DATA_DIR = os.environ.get("DATA_DIR", "data")

    # Base de données (SQLite par défaut)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.abspath(os.path.join(DATA_DIR, "chatbot.db"))
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads
    MAX_CONTENT_LENGTH_MB = int(os.environ.get("MAX_CONTENT_LENGTH_MB", "100"))
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH_MB * 1024 * 1024
    ALLOWED_EXTENSIONS = {
        "wav", "mp3", "m4a", "ogg", "oga", "webm", "mp4",
        "flac", "aac", "opus", "wma",
    }

    # CORS
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.environ.get(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ]

    # Rate limiting (mettre RATELIMIT_ENABLED=0 pour les tests)
    RATELIMIT_ENABLED = _bool("RATELIMIT_ENABLED", default=True)
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_TRANSCRIBE = os.environ.get("RATELIMIT_TRANSCRIBE", "10/minute")
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "300/hour")

    # Reconnaissance
    LANGUAGE = os.environ.get("LANGUAGE", "fr")
