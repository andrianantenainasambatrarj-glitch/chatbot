"""Modèles de persistance SQLAlchemy."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

EXPORT_FORMATS = ("docx", "pdf", "txt", "srt")

JOB_PENDING = "pending"
JOB_PROCESSING = "processing"
JOB_DONE = "done"
JOB_ERROR = "error"

ROLE_USER = "user"
ROLE_ADMIN = "admin"

SHARE_TOKEN_DAYS = 30


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=_new_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_USER)
    # Quota mensuel en minutes d'audio (None = illimité)
    monthly_quota_minutes = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    transcriptions = db.relationship(
        "Transcription", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "monthly_quota_minutes": self.monthly_quota_minutes,
        }


class Transcription(db.Model):
    __tablename__ = "transcriptions"

    id = db.Column(db.String(36), primary_key=True, default=_new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    base_name = db.Column(db.String(120), nullable=False)
    duration_seconds = db.Column(db.Float, nullable=True)
    language = db.Column(db.String(10), nullable=False, default="fr")
    engine = db.Column(db.String(20), nullable=False, default="vosk")
    has_timestamps = db.Column(db.Boolean, nullable=False, default=False)
    diarized = db.Column(db.Boolean, nullable=False, default=False)
    speakers = db.Column(db.JSON, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    action_items = db.Column(db.JSON, nullable=True)
    keywords = db.Column(db.JSON, nullable=True)
    sentiment = db.Column(db.JSON, nullable=True)
    insights_engine = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    user = db.relationship("User", back_populates="transcriptions")
    share_links = db.relationship(
        "ShareLink", back_populates="transcription", cascade="all, delete-orphan"
    )

    def to_dict(self, include_analysis=False):
        created = self.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        formats = ["docx", "pdf", "txt"]
        if self.has_timestamps:
            formats.append("srt")
        data = {
            "id": self.id,
            "text": self.text,
            "language": self.language,
            "engine": self.engine,
            "duration_seconds": round(self.duration_seconds, 2)
            if self.duration_seconds is not None
            else None,
            "has_timestamps": self.has_timestamps,
            "diarized": self.diarized,
            "created_at": created.astimezone(timezone.utc).isoformat(),
            "exports": {
                fmt: f"/api/transcriptions/{self.id}/export/{fmt}" for fmt in formats
            },
        }
        if self.diarized and self.speakers:
            data["speakers"] = self.speakers
        if include_analysis and self.summary is not None:
            data["analysis"] = {
                "summary": self.summary,
                "action_items": self.action_items or [],
                "keywords": self.keywords or [],
                "sentiment": self.sentiment,
                "engine": self.insights_engine,
            }
        return data


class ShareLink(db.Model):
    __tablename__ = "share_links"

    token = db.Column(db.String(64), primary_key=True, default=lambda: secrets.token_urlsafe(24))
    transcription_id = db.Column(
        db.String(36), db.ForeignKey("transcriptions.id"), nullable=False
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: _utcnow() + timedelta(days=SHARE_TOKEN_DAYS))

    transcription = db.relationship("Transcription", back_populates="share_links")

    def is_valid(self):
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires > _utcnow()

    def to_dict(self):
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return {
            "token": self.token,
            "url": f"/api/shared/{self.token}",
            "expires_at": expires.astimezone(timezone.utc).isoformat(),
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
    diarize = db.Column(db.Boolean, nullable=False, default=False)
    error = db.Column(db.Text, nullable=True)
    transcription_id = db.Column(
        db.String(36), db.ForeignKey("transcriptions.id"), nullable=True
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow,
                           onupdate=_utcnow)

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
