"""Modèles de persistance SQLAlchemy."""

import uuid
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

EXPORT_FORMATS = ("docx", "pdf", "txt", "srt")

JOB_PENDING = "pending"
JOB_PROCESSING = "processing"
JOB_DONE = "done"
JOB_ERROR = "error"


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=_new_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    transcriptions = db.relationship(
        "Transcription", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self):
        return {"id": self.id, "email": self.email}


class Transcription(db.Model):
    __tablename__ = "transcriptions"

    id = db.Column(db.String(36), primary_key=True, default=_new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)
    text = db.Column(db.Text, nullable=False)
    # Préfixe commun des fichiers générés (sans extension)
    base_name = db.Column(db.String(120), nullable=False)
    duration_seconds = db.Column(db.Float, nullable=True)
    language = db.Column(db.String(10), nullable=False, default="fr")
    engine = db.Column(db.String(20), nullable=False, default="vosk")
    has_timestamps = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    user = db.relationship("User", back_populates="transcriptions")

    def to_dict(self):
        created = self.created_at
        if created.tzinfo is None:  # SQLite renvoie des datetimes naïves (UTC)
            created = created.replace(tzinfo=timezone.utc)
        formats = ["docx", "pdf", "txt"]
        if self.has_timestamps:
            formats.append("srt")
        return {
            "id": self.id,
            "text": self.text,
            "language": self.language,
            "engine": self.engine,
            "duration_seconds": round(self.duration_seconds, 2)
            if self.duration_seconds is not None
            else None,
            "has_timestamps": self.has_timestamps,
            "created_at": created.astimezone(timezone.utc).isoformat(),
            "exports": {
                fmt: f"/api/transcriptions/{self.id}/export/{fmt}" for fmt in formats
            },
        }


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.String(36), primary_key=True, default=_new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default=JOB_PENDING, index=True)
    progress = db.Column(db.Integer, nullable=False, default=0)
    message = db.Column(db.String(255), nullable=True)
    engine = db.Column(db.String(20), nullable=False, default="vosk")
    language = db.Column(db.String(10), nullable=False, default="fr")
    error = db.Column(db.Text, nullable=True)
    transcription_id = db.Column(
        db.String(36), db.ForeignKey("transcriptions.id"), nullable=True
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    transcription = db.relationship("Transcription")

    def to_dict(self):
        updated = self.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return {
            "id": self.id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "engine": self.engine,
            "language": self.language,
            "error": self.error,
            "updated_at": updated.astimezone(timezone.utc).isoformat(),
            "transcription": self.transcription.to_dict() if self.transcription else None,
        }
