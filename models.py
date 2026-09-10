"""Modèle de persistance SQLAlchemy."""

import uuid
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

EXPORT_FORMATS = ("docx", "pdf", "txt", "srt")


def _utcnow():
    return datetime.now(timezone.utc)


class Transcription(db.Model):
    __tablename__ = "transcriptions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    text = db.Column(db.Text, nullable=False)
    # Préfixe commun des fichiers générés (sans extension)
    base_name = db.Column(db.String(120), nullable=False)
    duration_seconds = db.Column(db.Float, nullable=True)
    language = db.Column(db.String(10), nullable=False, default="fr")
    has_timestamps = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    def to_dict(self):
        created = self.created_at
        if created.tzinfo is None:  # SQLite renvoie des datetimes naïves (UTC)
            created = created.replace(tzinfo=timezone.utc)
        iso = created.astimezone(timezone.utc).isoformat()
        formats = ["docx", "pdf", "txt"]
        if self.has_timestamps:
            formats.append("srt")
        return {
            "id": self.id,
            "text": self.text,
            "language": self.language,
            "duration_seconds": round(self.duration_seconds, 2)
            if self.duration_seconds is not None
            else None,
            "has_timestamps": self.has_timestamps,
            "created_at": iso,
            "exports": {
                fmt: f"/api/transcriptions/{self.id}/export/{fmt}" for fmt in formats
            },
        }
