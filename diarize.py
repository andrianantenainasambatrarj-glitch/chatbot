"""Diarisation légère des locuteurs à partir des silences.

Les mots horodatés fournis par Vosk/Whisper permettent de repérer les longues
pauses : un silence supérieur à `gap_seconds` marque un changement probable
d'intervenant. Pour une vraie séparation des voix par empreinte vocale, une
intégration pyannote.audio peut remplacer cette fonction (l'API reste la même).
"""

DEFAULT_GAP = 0.9


def diarize(words, gap_seconds=DEFAULT_GAP):
    """Retourne une liste de tours de parole [{speaker, start, end, text}]."""
    if not words:
        return []
    turns = []
    current = {"speaker": 1, "start": words[0]["start"], "end": words[0]["end"],
               "words": [words[0]["word"]]}
    speaker = 1

    for previous, word in zip(words, words[1:]):
        gap = word["start"] - previous["end"]
        if gap >= gap_seconds:
            # On clôture le tour ; l'intervenant alterne entre 1 et 2
            turns.append(_finalize(current))
            speaker = 2 if speaker == 1 else 1
            current = {"speaker": speaker, "start": word["start"], "end": word["end"],
                       "words": [word["word"]]}
        else:
            current["end"] = word["end"]
            current["words"].append(word["word"])
    turns.append(_finalize(current))
    return turns


def _finalize(turn):
    return {
        "speaker": turn["speaker"],
        "start": round(turn["start"], 2),
        "end": round(turn["end"], 2),
        "text": " ".join(turn["words"]).strip().capitalize(),
    }


def format_speakers(turns, language="fr"):
    """Texte mis en forme avec les étiquettes d'intervenants."""
    label = "Intervenant" if language == "fr" else "Speaker"
    lines = []
    last_speaker = None
    for turn in turns:
        prefix = f"{label} {turn['speaker']} : "
        if turn["speaker"] == last_speaker:
            lines.append(turn["text"])
        else:
            lines.append(f"\n{prefix}{turn['text']}")
        last_speaker = turn["speaker"]
    return "\n".join(lines).strip()
