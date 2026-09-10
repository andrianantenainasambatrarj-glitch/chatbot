"""Moteur Vosk : reconnaissance hors-ligne, supports du streaming."""

import json
import logging
import os
import threading

from flask import current_app

logger = logging.getLogger("chatbot-vocal")

SAMPLE_RATE = 16000


class ModelUnavailableError(RuntimeError):
    """Modèle Vosk absent ou impossible à charger."""


class VoskEngine:
    name = "vosk"

    def __init__(self):
        self._models = {}
        self._locks = {}
        self._global_lock = threading.Lock()

    # ------------------------------------------------------------------
    def _model_path(self, language):
        models_map = current_app.config["VOSK_MODELS"]
        path = models_map.get(language)
        if not path:
            available = ", ".join(sorted(models_map)) or "aucune"
            raise ModelUnavailableError(
                f"Aucun modèle Vosk configuré pour la langue '{language}' "
                f"(langues installées : {available})."
            )
        return path

    def _get_model(self, language):
        """Charge et cache le modèle Vosk d'une langue (lazy, thread-safe)."""
        path = self._model_path(language)
        if language not in self._models:
            with self._global_lock:
                self._locks.setdefault(language, threading.Lock())
            with self._locks[language]:
                if language not in self._models:
                    if not os.path.isdir(path):
                        raise ModelUnavailableError(
                            f"Le modèle Vosk pour '{language}' est introuvable dans '{path}'. "
                            "Lancez : python scripts/download_model.py"
                        )
                    try:
                        from vosk import Model, SetLogLevel

                        SetLogLevel(-1)
                        logger.info("Chargement du modèle Vosk '%s' (%s)", language, path)
                        self._models[language] = Model(path)
                    except Exception as exc:  # dépendance manquante, modèle corrompu
                        raise ModelUnavailableError(
                            f"Impossible de charger le modèle Vosk '{language}' : {exc}"
                        ) from exc
        return self._models[language]

    def create_recognizer(self, language):
        """Reconnaiseur Vosk pour le streaming temps réel."""
        from vosk import KaldiRecognizer

        recognizer = KaldiRecognizer(self._get_model(language), SAMPLE_RATE)
        recognizer.SetWords(True)
        return recognizer

    # ------------------------------------------------------------------
    def transcribe(self, wav_path, language="fr", progress=None):
        recognizer = self.create_recognizer(language)
        text_parts, words = [], []
        total = os.path.getsize(wav_path)
        read = 0
        with open(wav_path, "rb") as wf:
            while True:
                data = wf.read(4000)
                if len(data) == 0:
                    break
                read += len(data)
                if recognizer.AcceptWaveform(data):
                    part = json.loads(recognizer.Result())
                    if part.get("text"):
                        text_parts.append(part["text"])
                    words.extend(part.get("result", []))
                if progress and total:
                    progress(min(99, int(read * 95 / total)))

        final = json.loads(recognizer.FinalResult())
        if final.get("text"):
            text_parts.append(final["text"])
        words.extend(final.get("result", []))
        if progress:
            progress(100)
        return " ".join(text_parts).strip(), words

    # ------------------------------------------------------------------
    def metadata(self):
        languages = []
        for language, path in current_app.config["VOSK_MODELS"].items():
            languages.append(
                {"code": language, "available": os.path.isdir(path), "model_path": path}
            )
        return {
            "name": "vosk",
            "label": "Vosk (hors-ligne, temps réel)",
            "streaming": True,
            "languages": languages,
        }
