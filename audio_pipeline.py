"""Conversion audio avant reconnaissance.

Passe par un unique appel ``ffmpeg`` en flux (fichier -> WAV 16 kHz mono
PCM 16 bits) : constant en mémoire, quel que soit la taille de l'audio, et
beaucoup plus rapide qu'un décodage pydub intégral en Python suivi d'un
second ré-encodage (sur les petites instances CPU partagées, type Render
gratuit, la différence est de plusieurs dizaines de secondes).

En production gevent, les sous-processus sont lancés via le lanceur natif
``native_subprocess`` (les « child watchers » de gevent n'existent que sur
la boucle principale) ; en développement, le ``subprocess`` standard est
utilisé.
"""

import logging
import os
import shutil
import wave
from tempfile import NamedTemporaryFile

from config import Config

logger = logging.getLogger("chatbot-vocal")

SAMPLE_RATE = 16000


# Choix du lanceur de processus (compatible threads système sous gevent)
try:
    from gevent.monkey import is_module_patched as _is_patched

    if _is_patched("subprocess"):
        from native_subprocess import PIPE as _PIPE
        from native_subprocess import Popen as _Popen
    else:
        raise ImportError
except Exception:  # développement sans gevent (Windows/Linux)
    from subprocess import PIPE as _PIPE  # type: ignore
    from subprocess import Popen as _Popen  # type: ignore


class AudioDecodeError(ValueError):
    """Fichier reçu illisible, ffmpeg absent ou audio sans piste exploitable."""


def validate_extension(filename):
    """Retourne (autorisé, extension) à partir du nom de fichier."""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    return ext in Config.ALLOWED_EXTENSIONS, ext


def _ffmpeg_binary():
    return shutil.which("ffmpeg") or "ffmpeg"


def _wav_duration(wav_path):
    try:
        with wave.open(wav_path, "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            return frames / float(rate) if rate else 0.0
    except (wave.Error, EOFError, OSError):
        return 0.0


def prepare_audio(src_path):
    """Convertit un audio pris en charge par ffmpeg en WAV Vosk.

    Retourne (chemin_wav_temporaire, durée_en_secondes).
    L'appelant est responsable de la suppression du fichier temporaire.
    """
    converted = NamedTemporaryFile(delete=False, suffix="_converted.wav")
    converted.close()
    command = [
        _ffmpeg_binary(),
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", src_path,
        "-vn",                       # ignore la piste vidéo
        "-ac", "1",                  # mono
        "-ar", str(SAMPLE_RATE),     # 16 kHz
        "-acodec", "pcm_s16le",      # PCM 16 bits signés little-endian
        "-f", "wav",
        converted.name,
    ]
    try:
        proc = _Popen(command, stdin=None, stdout=_PIPE, stderr=_PIPE)
        _stdout, stderr = proc.communicate()
    except FileNotFoundError as exc:
        _safe_unlink(converted.name)
        raise AudioDecodeError(
            "Le binaire ffmpeg est introuvable sur le serveur ; "
            "installez-le pour traiter cet audio."
        ) from exc
    except OSError as exc:
        _safe_unlink(converted.name)
        raise AudioDecodeError(f"Échec du lancement de ffmpeg : {exc}") from exc

    if proc.returncode != 0 or not os.path.exists(converted.name) \
            or os.path.getsize(converted.name) <= 44:
        detail = ""
        if isinstance(stderr, (bytes, bytearray)):
            detail = stderr.decode("utf-8", "ignore").strip()[-400:]
        _safe_unlink(converted.name)
        if proc.returncode != 0 and ("not found" in detail.lower()
                                     or "no such file" in detail.lower()):
            raise AudioDecodeError(
                "Le binaire ffmpeg est introuvable sur le serveur."
            )
        raise AudioDecodeError(
            "Impossible de décoder ce fichier : format audio illisible ou "
            "endommagé." + (f" Détail ffmpeg : {detail}" if detail else "")
        )

    duration = _wav_duration(converted.name)
    if duration <= 0:
        _safe_unlink(converted.name)
        raise AudioDecodeError(
            "Aucune piste audio exploitable n'a été trouvée dans ce fichier."
        )
    return converted.name, duration


def _safe_unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass
