"""Analyse automatique des transcriptions (NLP).

Deux modes :
  - par défaut, un analyseur extractif hors-ligne, sans dépendance ni réseau
    (nlp.extractive) : résumé, actions à faire, mots-clés, tonalité ;
  - si un grand modèle de langage est configuré (LLM_API_KEY / LLM_BASE_URL,
    compatible OpenAI dont Ollama en local), il est utilisé à la place.
"""

from nlp.extractive import analyze_extractive
from nlp.llm import LLMClient, is_configured

__all__ = ["analyze_extractive", "LLMClient", "is_configured", "analyze"]


def analyze(text, language="fr"):
    """Retourne {summary, action_items, keywords, sentiment, engine}."""
    if is_configured():
        try:
            result = LLMClient().analyze(text, language)
            result["engine"] = "llm"
            return result
        except Exception:  # repli silencieux sur l'analyseur hors-ligne
            pass
    result = analyze_extractive(text, language)
    result["engine"] = "extractive"
    return result
