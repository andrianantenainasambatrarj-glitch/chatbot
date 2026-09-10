"""Transcription en temps réel via WebSocket.

Le navigateur envoie des trames PCM 16 kHz mono (Int16). Le serveur les
fournit à Vosk au fil de l'eau et renvoie les transcriptions partielles.
À la réception du message de contrôle {"action": "stop"}, le texte final est
persisté comme n'importe quelle transcription.
"""

import json
import logging
import time

from flask import request
from flask_sock import Server

import services
from auth import user_from_token
from commands import detect_command
from engines.vosk_engine import ModelUnavailableError
from models import db

logger = logging.getLogger("chatbot-vocal")


class StreamSession:
    """Logique d'une session Vosk continue, indépendante du transport (testable)."""

    def __init__(self, recognizer):
        self.recognizer = recognizer
        self.text_parts = []
        self.words = []

    def feed(self, pcm_bytes):
        """Ingère une trame PCM ; retourne un texte intermédiaire (ou None)."""
        if self.recognizer.AcceptWaveform(pcm_bytes):
            part = json.loads(self.recognizer.Result())
            if part.get("text"):
                self.text_parts.append(part["text"])
            self.words.extend(part.get("result", []))
            return part.get("text")
        partial = json.loads(self.recognizer.PartialResult())
        return partial.get("partial") or None

    def finish(self):
        final = json.loads(self.recognizer.FinalResult())
        if final.get("text"):
            self.text_parts.append(final["text"])
        self.words.extend(final.get("result", []))
        return " ".join(self.text_parts).strip(), self.words


def _authorize_ws(ws):
    """Authentifie la WebSocket via le paramètre 'token' (les navigateurs
    ne peuvent pas fixer d'en-tête Authorization sur une WebSocket)."""
    token = request.args.get("token", "")
    user = user_from_token(token)
    if user is None:
        ws.send(json.dumps({"type": "error", "error": "Authentification requise."}))
        ws.close()
        return None
    return user


def register_websocket(sock, app):
    @sock.route("/ws/transcribe")
    def ws_transcribe(ws: Server):
        user = _authorize_ws(ws)
        if user is None:
            return

        language = request.args.get("language", app.config["DEFAULT_LANGUAGE"])
        started = time.time()

        try:
            engine = app.extensions["vosk_engine"]
            recognizer = engine.create_recognizer(language)
        except ModelUnavailableError as exc:
            ws.send(json.dumps({"type": "error", "error": str(exc)}))
            ws.close()
            return

        session = StreamSession(recognizer)
        ws.send(json.dumps({"type": "ready", "language": language}))

        try:
            while True:
                message = ws.receive(timeout=30)
                if message is None:
                    break
                if isinstance(message, str):
                    try:
                        control = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    if control.get("action") == "stop":
                        break
                    continue
                # Trame audio binaire (PCM Int16, 16 kHz, mono)
                partial = session.feed(message)
                if partial:
                    ws.send(json.dumps({"type": "partial", "text": partial}))
        except Exception:  # noqa: BLE001 - connexion coupée, timeout...
            logger.info("Session WebSocket interrompue")

        text, words = session.finish()
        if text:
            duration = time.time() - started
            transcription = services.save_transcription(
                user_id=user.id,
                text=text,
                words=words,
                duration_seconds=duration,
                engine="vosk",
                language=language,
            )
            db.session.refresh(transcription)
            ws.send(json.dumps({"type": "final", "transcription": transcription.to_dict()}))
        else:
            ws.send(json.dumps({"type": "final", "transcription": None}))
        ws.close()

    @sock.route("/ws/commands")
    def ws_commands(ws: Server):
        """Reconnaissance continue de courtes commandes vocales."""
        user = _authorize_ws(ws)
        if user is None:
            return

        language = request.args.get("language", app.config["DEFAULT_LANGUAGE"])
        try:
            engine = app.extensions["vosk_engine"]
            recognizer = engine.create_recognizer(language)
        except ModelUnavailableError as exc:
            ws.send(json.dumps({"type": "error", "error": str(exc)}))
            ws.close()
            return

        ws.send(json.dumps({"type": "ready"}))
        last_partial = ""
        try:
            while True:
                message = ws.receive(timeout=60)
                if message is None:
                    break
                if isinstance(message, str):
                    try:
                        control = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    if control.get("action") == "stop":
                        break
                    continue

                if recognizer.AcceptWaveform(message):
                    result = json.loads(recognizer.Result())
                    phrase = result.get("text", "")
                    command = detect_command(phrase)
                    if command:
                        ws.send(json.dumps({"type": "command", "command": command, "phrase": phrase}))
                    elif phrase:
                        ws.send(json.dumps({"type": "heard", "phrase": phrase}))
                else:
                    partial = json.loads(recognizer.PartialResult()).get("partial", "")
                    if partial != last_partial:
                        last_partial = partial
                        ws.send(json.dumps({"type": "partial", "text": partial}))
        except Exception:  # noqa: BLE001
            logger.info("Session WebSocket de commandes interrompue")
        ws.close()
