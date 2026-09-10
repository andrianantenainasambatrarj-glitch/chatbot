"""Question/réponse sur une transcription sans LLM (recherche de similarité).

Utilisé comme repli quand aucun grand modèle n'est configuré : trouve les
phrases de la transcription les plus proches de la question par fréquence de
mots (recouvrement TF) et les renvoie sous forme de réponse.
"""

import math
from collections import Counter

from nlp.extractive import STOPWORDS, split_sentences, tokenize


def _vector(text, language):
    stop = STOPWORDS.get(language, STOPWORDS["fr"]) | STOPWORDS["en"]
    tokens = [w for w in tokenize(text) if w not in stop and len(w) > 1]
    return Counter(tokens)


def _cosine(vec_a, vec_b):
    common = set(vec_a) & set(vec_b)
    if not common:
        return 0.0
    dot = sum(vec_a[w] * vec_b[w] for w in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    return dot / (norm_a * norm_b)


def answer_extractive(question, transcription_text, language="fr"):
    sentences = split_sentences(transcription_text)
    if not sentences:
        return ""
    question_vec = _vector(question, language)
    ranked = sorted(
        ((_cosine(question_vec, _vector(sentence, language)), index, sentence)
         for index, sentence in enumerate(sentences)),
        reverse=True,
    )
    best_score = ranked[0][0]
    if best_score <= 0.05:
        return (
            "Je ne trouve pas cette information dans la transcription. "
            if language == "fr"
            else "I can't find that information in the transcription. "
        )
    # Renvoie les 2 meilleures phrases si elles sont pertinentes, dans l'ordre du texte
    picks = sorted(
        [(index, sentence) for score, index, sentence in ranked if score >= best_score * 0.75][:2]
    )
    return " ".join(sentence for _index, sentence in picks)
