"""Conversion audio (ffmpeg via pydub) avant reconnaissance."""

import logging
import os
from tempfile import NamedTemporaryFile

import pydub
from pydub.exceptions import CouldntDecodeError

from config import Config

logger = logging.getLogger("chatbot-vocal")

SAMPLE_RATE = 16000


class AudioDecodeError(ValueError):
    """Fichier reçu illisible ou ffmpeg absent."""


def validate_extension(filename):
    """Retourne (autorisé, extension) à partir du nom de fichier."""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    return ext in Config.ALLOWED_EXTENSIONS, ext


def prepare_audio(src_path):
    """Convertit un audio pris en charge par ffmpeg en WAV Vosk.

    Retourne (chemin_wav_temporaire, durée_en_secondes).
    L'appelant est responsable de la suppression du fichier temporaire.
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
