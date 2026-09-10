"""Services métier : création et persistance des transcriptions."""

import logging
import os
from datetime import datetime

from flask import current_app

import exporters
from audio_pipeline import prepare_audio
from engines import get_engine
from models import Transcription, db

logger = logging.getLogger("chatbot-vocal")


def _base_name():
    return f"transcription_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"


def _write_exports(transcription, text, words):
    base_path = os.path.join(current_app.config["TRANSCRIPTIONS_DIR"], transcription.base_name)
    kwargs = {
        "language": transcription.language,
        "duration_seconds": transcription.duration_seconds,
    }
    exporters.render_docx(text, f"{base_path}.docx", **kwargs)
    exporters.render_pdf(text, f"{base_path}.pdf", **kwargs)
    exporters.render_txt(text, f"{base_path}.txt", **kwargs)
    if words:
        exporters.render_srt(words, f"{base_path}.srt", **kwargs)
        transcription.has_timestamps = True


def save_transcription(*, user_id, text, words=None, duration_seconds=None,
                       engine="vosk", language="fr"):
    """Crée la transcription et ses exports à partir d'un texte déjà obtenu."""
    transcription = Transcription(
        user_id=user_id,
        text=text,
        base_name=_base_name(),
        duration_seconds=round(duration_seconds, 2) if duration_seconds else None,
        language=language,
        engine=engine,
    )
    db.session.add(transcription)
    db.session.flush()
    transcription.base_name = f"{transcription.base_name}_{transcription.id[:8]}"
    _write_exports(transcription, text, words)
    db.session.commit()
    return transcription


def transcribe_file(*, user_id, audio_path, engine="vosk", language="fr", progress=None):
    """Convertit un fichier audio, le transcrit, persiste et exporte."""
    wav_path = None
    try:
        wav_path, duration = prepare_audio(audio_path)
        engine_obj = get_engine(engine)
        if progress:
            progress(5)
        text, words = engine_obj.transcribe(wav_path, language, progress)
        text = text.strip()
        if not text:
            raise ValueError("Aucun texte transcrit (audio vide, silencieux ou inaudible).")
        return save_transcription(
            user_id=user_id,
            text=text,
            words=words,
            duration_seconds=duration,
            engine=engine,
            language=language,
        )
    finally:
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)
