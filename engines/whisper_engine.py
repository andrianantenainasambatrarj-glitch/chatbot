"""Moteur Whisper (faster-whisper) : optionnel, très précis, multilingue.

La dépendance faster-whisper n'est pas installée par défaut (lourde) :
    pip install faster-whisper
Le premier usage télécharge le modèle depuis le réseau.
"""

import importlib.util
import logging
import threading

from flask import current_app

logger = logging.getLogger("chatbot-vocal")


class WhisperUnavailableError(RuntimeError):
    """faster-whisper ou ses modèles ne sont pas disponibles."""


class WhisperEngine:
    name = "whisper"

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()

    @staticmethod
    def is_installed():
        return importlib.util.find_spec("faster_whisper") is not None

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    if not self.is_installed():
                        raise WhisperUnavailableError(
                            "Le moteur Whisper n'est pas installé. "
                            "Lancez : pip install faster-whisper"
                        )
                    try:
                        from faster_whisper import WhisperModel

                        size = current_app.config["WHISPER_MODEL_SIZE"]
                        device = current_app.config["WHISPER_DEVICE"]
                        compute = current_app.config["WHISPER_COMPUTE_TYPE"]
                        logger.info("Chargement de faster-whisper (%s, %s/%s)", size, device, compute)
                        self._model = WhisperModel(size, device=device, compute_type=compute)
                    except WhisperUnavailableError:
                        raise
                    except Exception as exc:
                        raise WhisperUnavailableError(
                            f"Impossible de charger le modèle Whisper : {exc}"
                        ) from exc
        return self._model

    def transcribe(self, wav_path, language="fr", progress=None):
        model = self._get_model()
        if progress:
            progress(20)
        try:
            segments, _info = model.transcribe(
                wav_path,
                language=language,
                word_timestamps=True,
                vad_filter=True,
            )
        except Exception as exc:
            raise WhisperUnavailableError(f"Échec de la transcription Whisper : {exc}") from exc

        text_parts, words = [], []
        count = 0
        for segment in segments:
            text_parts.append(segment.text.strip())
            for word in segment.words or []:
                words.append({"word": word.word.strip(), "start": word.start, "end": word.end})
            count += 1
            if progress:
                progress(min(90, 20 + count * 5))
        if progress:
            progress(100)
        return " ".join(text_parts).strip(), words

    def metadata(self):
        installed = self.is_installed()
        return {
            "name": "whisper",
            "label": f"Whisper ({current_app.config['WHISPER_MODEL_SIZE']}, grande précision)",
            "streaming": False,
            "installed": installed,
            "languages": [
                {"code": code, "available": installed}
                for code in current_app.config["WHISPER_LANGUAGES"]
            ],
        }
