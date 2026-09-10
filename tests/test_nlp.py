"""Tests du NLP hors-ligne, de la diarisation et des commandes vocales."""

from commands import detect_command
from diarize import diarize, format_speakers
from nlp.chat import answer_extractive
from nlp.extractive import analyze_extractive

MEETING = (
    "Bonjour à tous, merci d'être présents pour cette réunion de lancement. "
    "Nous devons préparer la nouvelle version du produit pour la fin du mois. "
    "Il faut contacter le client demain afin de valider le cahier des charges. "
    "Pensez à rédiger le rapport d'étonnement avant vendredi. "
    "La réunion se passe très bien, nous sommes contents de l'avancement. "
    "Nous avons malheureusement un problème de délai sur le serveur, c'est urgent. "
)


def test_extractive_analysis_french():
    result = analyze_extractive(MEETING, "fr")
    assert result["summary"]
    assert len(result["summary"]) <= len(MEETING)
    # Au moins une action à faire détectée
    joined = " | ".join(result["action_items"])
    assert "contacter le client" in joined.lower() or "rédiger le rapport" in joined.lower()
    # Mots-clés informatifs
    assert any(word in ("produit", "client", "réunion") for word in result["keywords"])
    assert result["sentiment"]["label"] in ("positif", "négatif", "neutre")


def test_extractive_analysis_english():
    text = (
        "We need to finish the report by Friday. Please contact the customer tomorrow. "
        "Great progress this week, the team did an excellent job."
    )
    result = analyze_extractive(text, "en")
    assert result["summary"]
    assert any("report" in item or "customer" in item for item in result["action_items"])


def test_chat_extractive_finds_answer():
    reply = answer_extractive("Qui faut-il contacter ?", MEETING, "fr")
    assert "client" in reply.lower()


def test_chat_extractive_unknown_question():
    reply = answer_extractive("Quel est le cours de la bourse à Tokyo ?", MEETING, "fr")
    assert "trouve pas" in reply


def test_diarization_by_silence():
    words = [
        {"word": "bonjour", "start": 0.0, "end": 0.4},
        {"word": "à", "start": 0.4, "end": 0.5},
        {"word": "tous", "start": 0.5, "end": 0.8},
        # silence de 2 secondes -> changement d'intervenant
        {"word": "merci", "start": 2.8, "end": 3.2},
        {"word": "pour", "start": 3.2, "end": 3.4},
        {"word": "l'accueil", "start": 3.4, "end": 3.9},
    ]
    turns = diarize(words, gap_seconds=0.9)
    assert len(turns) == 2
    assert turns[0]["speaker"] == 1
    assert turns[1]["speaker"] == 2
    formatted = format_speakers(turns, "fr")
    assert "Intervenant 1" in formatted
    assert "Intervenant 2" in formatted


def test_diarization_empty():
    assert diarize([]) == []


def test_command_detection_french():
    assert detect_command("nouvel enregistrement s'il vous plaît") == "new_recording"
    assert detect_command("passe en mode sombre") == "dark_mode"
    assert detect_command("montre le tableau de bord") == "dashboard"
    assert detect_command("télécharge le document word") == "download_word"
    assert detect_command("déconnexion") == "logout"
    assert detect_command("paroles sans signification") is None


def test_command_detection_english():
    assert detect_command("please download the pdf") == "download_pdf"
    assert detect_command("switch to english") == "language_english"
    assert detect_command("show me the dashboard") == "dashboard"
