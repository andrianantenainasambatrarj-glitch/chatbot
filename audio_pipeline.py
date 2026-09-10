"""Conversion audio et reconnaissance vocale (Vosk)."""

import json
import logging
import os
from tempfile import NamedTemporaryFile

import pydub
from pydub.exceptions import CouldntDecodeError

from config import Config

logger = logging.getLogger("chatbot-vocal")

SAMPLE_RATE = 16000


class ModelUnavailableError(RuntimeError):
    """Levée quand le modèle Vosk est absent ou impossible à charger."""


class AudioDecodeError(ValueError):
    """Levée quand le fichier reçu n'est pas un audio exploitable."""


def prepare_audio(src_path):
    """Convertit n'importe quel audio pris en charge par ffmpeg en WAV Vosk.

    Retourne (chemin_wav_converti, durée_en_secondes).
    """
    try:
        audio = pydub.AudioSegment.from_file(src_path)
    except CouldntDecodeError as exc:
        raise AudioDecodeError(
            "Impossible de décoder ce fichier : format audio illisible ou endommagé."
        ) from exc
    except FileNotFoundError as exc:
        if "ffmpeg" in str(exc).lower() or "ffprobe" in str(exc).lower():
            raise AudioDecodeError(
                "Le binaire ffmpeg est introuvable sur le serveur ; "
                "installez-le pour traiter cet audio."
            ) from exc
        raise

    duration = len(audio) / 1000.0
    audio = audio.set_channels(1).set_frame_rate(SAMPLE_RATE).set_sample_width(2)

    converted = NamedTemporaryFile(delete=False, suffix="_converted.wav")
    converted.close()
    audio.export(converted.name, format="wav")
    return converted.name, duration


def transcribe(audio_path, model):
    """Reconnaissance Vosk ; retourne (texte, mots_horodatés)."""
    from vosk import KaldiRecognizer

    recognizer = KaldiRecognizer(model, SAMPLE_RATE)
    recognizer.SetWords(True)

    text_parts = []
    words = []
    with open(audio_path, "rb") as wf:
        while True:
            data = wf.read(4000)
            if len(data) == 0:
                break
            if recognizer.AcceptWaveform(data):
                part = json.loads(recognizer.Result())
                if part.get("text"):
                    text_parts.append(part["text"])
                words.extend(part.get("result", []))

    final = json.loads(recognizer.FinalResult())
    if final.get("text"):
        text_parts.append(final["text"])
    words.extend(final.get("result", []))

    return " ".join(text_parts).strip(), words


def prepare_and_transcribe(src_path, get_model):
    """Pipeline complet : conversion, transcription, nettoyage des temporaires."""
    converted_path = None
    try:
        converted_path, duration = prepare_audio(src_path)
        text, words = transcribe(converted_path, get_model())
        return text, words, duration
    finally:
        if converted_path and os.path.exists(converted_path):
            os.unlink(converted_path)


def validate_extension(filename):
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    return ext in Config.ALLOWED_EXTENSIONS, ext
