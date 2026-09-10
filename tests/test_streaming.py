"""Tests de la logique de session de streaming temps réel (sans WebSocket)."""

from streaming import StreamSession
from tests.conftest import FakeRecognizer


def test_stream_session_emits_partials_and_final_text():
    session = StreamSession(FakeRecognizer())

    partials = []
    # 7 trames : les 3e et 6e produisent un résultat final accepté
    for i in range(7):
        result = session.feed(b"0000")
        if result:
            partials.append(result)

    text, words = session.finish()

    # Deux résultats "acceptés" (trames 3 et 6) + le texte final
    assert "partie 3" in text
    assert "partie 6" in text
    assert "texte final" in text
    # Des mots horodatés ont été accumulés (pour l'export SRT)
    assert len(words) >= 4
    # Chaque trame renvoie au moins la transcription partielle du faux recognizer
    assert partials  # non vide


def test_empty_stream_produces_empty_text():
    class SilentRecognizer(FakeRecognizer):
        def AcceptWaveform(self, _data):
            return False

        def FinalResult(self):
            import json

            return json.dumps({"text": "", "result": []})

    session = StreamSession(SilentRecognizer())
    session.feed(b"0000")
    text, words = session.finish()
    assert text == ""
    assert words == []
