"""Configuration de l'application, lue depuis les variables d'environnement."""

import json
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
    # Au-delà de ce seuil, la transcription passe en tâche asynchrone
    ASYNC_THRESHOLD_MB = float(os.environ.get("ASYNC_THRESHOLD_MB", "5"))
    JOB_WORKERS = int(os.environ.get("JOB_WORKERS", "2"))

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
    RATELIMIT_AUTH = os.environ.get("RATELIMIT_AUTH", "20/hour")
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "300/hour")

    # Authentification
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", os.environ.get("SECRET_KEY", "change-me-dev"))
    JWT_EXPIRES_HOURS = int(os.environ.get("JWT_EXPIRES_HOURS", "168"))  # 7 jours

    # Moteurs de reconnaissance
    DEFAULT_ENGINE = os.environ.get("DEFAULT_ENGINE", "vosk")
    DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "fr")
    # Mapping langue -> chemin du modèle Vosk, surchargeable par variable d'env (JSON)
    VOSK_MODELS = json.loads(
        os.environ.get(
            "VOSK_MODELS",
            json.dumps({"fr": os.environ.get("MODEL_PATH", "models/vosk-model-small-fr-0.22")}),
        )
    )
    WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")
    WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
    WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
    # Langues reconnues par Whisper (sous-ensemble courant)
    WHISPER_LANGUAGES = [
        "fr", "en", "es", "de", "it", "pt", "nl", "pl", "ru",
        "zh", "ja", "ar", "mg", "tr", "sv", "fi", "da", "no",
    ]

    # Langue des métadonnées d'export (conservée pour compatibilité)
    LANGUAGE = DEFAULT_LANGUAGE

    # Diarisation légère (changement d'intervenant sur les silences)
    DIARIZE_GAP_SECONDS = float(os.environ.get("DIARIZE_GAP_SECONDS", "0.9"))

    # Quotas : minutes d'audio par utilisateur et par mois (0 = illimité)
    DEFAULT_QUOTA_MINUTES = int(os.environ.get("DEFAULT_QUOTA_MINUTES", "0"))

    # Comptes administrateurs (e-mails séparés par des virgules)
    ADMIN_EMAILS = [
        email.strip().lower()
        for email in os.environ.get("ADMIN_EMAILS", "").split(",")
        if email.strip()
    ]

    # Grand modèle de langage optionnel (API compatible OpenAI, dont Ollama)
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    # Envoi d'e-mails SMTP
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "")
    SMTP_USE_SSL = _bool("SMTP_USE_SSL", default=False)

    # Métriques Prometheus (jeton obligatoire s'il est défini)
    METRICS_TOKEN = os.environ.get("METRICS_TOKEN", "")
