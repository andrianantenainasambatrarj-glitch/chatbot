"""Services métier : transcription, diarisation, analyses, persistance."""

import logging
import os
from datetime import datetime, timezone

from flask import current_app

import diarize as diarize_module
import exporters
import nlp
from audio_pipeline import prepare_audio
from engines import get_engine
from models import Transcription, db
from nlp.chat import answer_extractive
from nlp.llm import LLMClient, is_configured

logger = logging.getLogger("chatbot-vocal")


class QuotaExceededError(Exception):
    """Quota mensuel d'audio dépassé pour cet utilisateur."""

    def __init__(self, limit_minutes):
        self.limit_minutes = limit_minutes
        super().__init__(
            f"Quota mensuel de {limit_minutes} minutes d'audio dépassé."
        )


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
                       engine="vosk", language="fr", speakers=None):
    transcription = Transcription(
        user_id=user_id,
        text=text,
        base_name=_base_name(),
        duration_seconds=round(duration_seconds, 2) if duration_seconds else None,
        language=language,
        engine=engine,
        diarized=bool(speakers),
        speakers=speakers,
    )
    db.session.add(transcription)
    db.session.flush()
    transcription.base_name = f"{transcription.base_name}_{transcription.id[:8]}"
    _write_exports(transcription, text, words)
    db.session.commit()
    return transcription


def used_minutes_this_month(user_id):
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = (
        db.session.query(Transcription.duration_seconds)
        .filter(Transcription.user_id == user_id, Transcription.created_at >= start)
        .all()
    )
    total_seconds = sum(row[0] or 0 for row in rows)
    return total_seconds / 60.0


def check_quota(user, duration_seconds):
    if user.monthly_quota_minutes in (None, 0):
        return
    projected = used_minutes_this_month(user.id) + (duration_seconds or 0) / 60.0
    if projected > user.monthly_quota_minutes:
        raise QuotaExceededError(user.monthly_quota_minutes)


def transcribe_file(*, user, audio_path, engine="vosk", language="fr",
                    diarization=False, progress=None):
    """Convertit, transcrit, éventuellement diarise, persiste et exporte."""
    wav_path = None
    try:
        wav_path, duration = prepare_audio(audio_path)
        check_quota(user, duration)
        engine_obj = get_engine(engine)
        if progress:
            progress(5)
        # L'alignement mot à mot (coûteux sur CPU pour Whisper) n'est requis
        # que par la diarisation ; Vosk fournit toujours les horodatages.
        text, words = engine_obj.transcribe(
            wav_path, language, progress, timestamps=diarization
        )
        text = text.strip()
        if not text:
            raise ValueError("Aucun texte transcrit (audio vide, silencieux ou inaudible).")

        speakers = None
        if diarization and words:
            gap = current_app.config["DIARIZE_GAP_SECONDS"]
            turns = diarize_module.diarize(words, gap_seconds=gap)
            if turns:
                speakers = turns
                text = diarize_module.format_speakers(turns, language)

        transcription = save_transcription(
            user_id=user.id,
            text=text,
            words=words,
            duration_seconds=duration,
            engine=engine,
            language=language,
            speakers=speakers,
        )
        metrics = current_app.extensions.get("metrics")
        if metrics:
            metrics.incr("transcriptions_total")
            metrics.incr("audio_seconds_total", int(duration or 0))
        return transcription
    finally:
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)


def generate_insights(transcription):
    """Calcule résumé/tâches/mots-clés et les persiste sur la transcription."""
    result = nlp.analyze(transcription.text, transcription.language)
    transcription.summary = result.get("summary", "")
    transcription.action_items = result.get("action_items", [])
    transcription.keywords = result.get("keywords", [])
    transcription.sentiment = result.get("sentiment")
    transcription.insights_engine = result.get("engine")
    db.session.commit()
    return transcription


def answer_question(transcription, question, history=None):
    """Répond à une question sur la transcription (LLM ou repli extractif)."""
    language = transcription.language
    if is_configured():
        try:
            return LLMClient().answer(
                transcription.text, question, history=history, language=language
            )
        except Exception as exc:  # repli si le LLM échoue
            logger.warning("LLM indisponible, repli extractif : %s", exc)
    return answer_extractive(question, transcription.text, language)
