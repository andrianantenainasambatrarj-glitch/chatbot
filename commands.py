"""Détection de commandes vocales dictées par l'utilisateur.

Utilisée par la WebSocket /ws/commands : chaque phrase reconnue par Vosk est
testée contre des motifs FR/EN ; si une commande est reconnue, le navigateur
reçoit un événement lui demandant d'effectuer l'action.
"""

import re

# code commande -> motifs (FR puis EN)
COMMANDS = {
    "new_recording": [
        r"nouvel(?:le)?\s+enregistrement", r"nouvelle dictée", r"recommencer",
        r"new recording", r"start recording", r"record again",
    ],
    "live_mode": [r"mode\s+en\s+direct", r"transcription\s+en\s+direct", r"live mode", r"go live"],
    "standard_mode": [r"mode\s+standard", r"mode\s+fichier", r"standard mode"],
    "dashboard": [r"tableau\s+de\s+bord", r"statistiques", r"dashboard", r"statistics"],
    "history": [r"historique", r"history"],
    "dark_mode": [r"mode\s+sombre", r"dark mode", r"dark theme"],
    "light_mode": [r"mode\s+clair", r"light mode", r"light theme"],
    "logout": [r"déconnexion", r"me\s+déconnecter", r"log\s?out", r"sign\s?out"],
    "clear_history": [r"effacer\s+l'historique", r"vider\s+l'historique", r"clear history", r"delete history"],
    "download_word": [r"télécharge[rz]?\s+(?:le\s+)?(?:document\s+)?word",
                      r"exporte?\s+(?:le\s+)?word", r"download (?:the )?word"],
    "download_pdf": [r"télécharge[rz]?\s+(?:le\s+)?pdf",
                     r"exporte?\s+(?:le\s+)?pdf", r"download (?:the )?pdf"],
    "insights": [r"résume?", r"résumé", r"synthèse", r"actions?\s+à\s+faire", r"summar", r"summary", r"key points"],
    "listen": [r"écoute?r?\s+(?:la\s+)?transcription", r"lis(?:ez)?\s+(?:la\s+)?transcription", r"read (?:the |aloud )?transcription"],
    "language_english": [r"passe?\s+en\s+anglais", r"switch to english"],
    "language_french": [r"passe?\s+en\s+français", r"switch to french"],
}


def detect_command(text):
    """Retourne le code de la commande reconnue ou None."""
    if not text:
        return None
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    for command, patterns in COMMANDS.items():
        for pattern in patterns:
            if re.search(pattern, normalized):
                return command
    return None
