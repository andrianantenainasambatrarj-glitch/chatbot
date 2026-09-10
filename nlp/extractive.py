"""Analyse extractive hors-ligne : résumé, tâches, mots-clés, tonalité.

Aucun prétraitencement lourd : un petit lexique de mots outils et des motifs
réguliers suffisent pour de l'aide à la relecture de comptes rendus.
"""

import re
from collections import Counter

STOPWORDS = {
    "fr": set(
        """
        au aux avec ce ces dans de des du elle en et eux il ils je la le les leur lui ma mais me
        meme mes moi mon ne nos notre nous on ou par pas pour qu que qui quoi sa se ses son sur
        ta te tes toi ton tu un une vos votre vous c d j l m n s t y à as â ai aie ait es est sont
        suis suis êtes être été avoir as ai avons avez ont avait étaient comme cette ces donc plus
        moins très tout tous toutes aucun aucune aussi entre vers chez selon lors pendant après
        avant dès afin parce parce car ni or soit peut quand même puis alors donc ainsi cette
        """
        .split()
    ),
    "en": set(
        """
        the a an and or but if then else of to in on at by for with from into onto upon is are was
        were be been being am do does did doing have has had having i you he she it we they me him
        her us them my your his its our their mine yours hers ours theirs this that these those as
        not no so than then there here when where why how what which while because about over under
        again further once can will would should could shall may might must ought
        """.split()
    ),
}

# Indices d'actions à réaliser dans un compte rendu
ACTION_PATTERNS = {
    "fr": [
        r"(?:il\s+faut|faudra|faudrait|il\s+est\s+question\s+de)\b[^.!?\n]*",
        r"(?:je|nous|vous|tu|il|elle|ils|elles)?\s*(?:dois|devons|devez|doivent|devrait|devrions|devriez)\b[^.!?\n]*",
        r"(?:penser\s+à|pensez\s+à|prévoir|planifier|planifions|organiser|contacter|appeler|envoyer|rédiger|préparer|terminer|finir|valider|vérifier|corriger|revoir|renvoyer|acheter|commander|réserver|confirmer|noter|rajouter|ajouter|créer|mettre\s+à\s+jour)\b[^.!?\n]*",
        r"(?:action\s*:|action\s+\d+\s*:|à\s+faire\s*:|rappel\s*:|todo\s*:)\s*[^.!?\n]*",
        r"(?:d'ici\s+(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|demain|la\s+semaine|fin|aujourd'hui|[\wé]+\s*\d{1,2}))[^.!?\n]*",
        r"(?:avant\s+le\s+|pour\s+le\s+|au\s+plus\s+tard\s+le\s+)\d{1,2}[^.!?\n]*",
    ],
    "en": [
        r"(?:we|you|i|he|she|they)\s+(?:need(?:s|ed)? to|must|should|have to|has to|had to|will|shall)\b[^.!?\n]*",
        r"(?:action\s*:|to\s?do\s*:|todo\s*:|follow[- ]up\s*:|reminder\s*:)\s*[^.!?\n]*",
        r"(?:please|remember to|don't forget to|make sure to|schedule|contact|call|send|prepare|finish|review|confirm|book|buy|create|update|check|write)\b[^.!?\n]*",
        r"(?:by\s+(?:monday|tuesday|wednesday|thursday|friday|tomorrow|next|end of|today|the end))[^.!?\n]*",
    ],
}

POSITIVE = {
    "fr": ["bien", "bon", "bonne", "super", "excellent", "ravi", "content", "accord", "validé",
           "approuvé", "ok", "parfait", "succès", "réussi", "positive", "merci", "avance", "opportunité"],
    "en": ["good", "great", "excellent", "happy", "pleased", "agree", "approved", "ok", "perfect",
           "success", "successful", "positive", "thanks", "thank", "opportunity", "glad"],
}
NEGATIVE = {
    "fr": ["problème", "erreur", "bug", "retard", "échec", "manque", "raté", "urgent", "bloquer",
           "bloque", "bloqué", "danger", "risque", "critique", "plainte", "défaut", "panne", "cassé", "impossible"],
    "en": ["problem", "issue", "error", "bug", "delay", "failed", "failure", "miss", "missed", "urgent",
           "block", "blocked", "risk", "critical", "complaint", "defect", "outage", "broken", "impossible"],
}


def split_sentences(text):
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text.strip())
    return [p.strip(" \t-–•") for p in parts if p and p.strip()]


def tokenize(text):
    return re.findall(r"[\wÀ-ÿ']+", text.lower())


def _keywords(text, language, top_n=10):
    stop = STOPWORDS.get(language, STOPWORDS["fr"]) | STOPWORDS["en"]
    words = [w for w in tokenize(text) if len(w) > 2 and w not in stop and not w.isdigit()]
    counter = Counter(words)
    return [word for word, _count in counter.most_common(top_n)]


def _summary(text, language, max_sentences=4):
    """Résumé extractif : phrases les plus denses en mots informatifs (fréquence)."""
    sentences = split_sentences(text)
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    stop = STOPWORDS.get(language, STOPWORDS["fr"]) | STOPWORDS["en"]
    words = [w for w in tokenize(text) if len(w) > 2 and w not in stop]
    freq = Counter(words)
    if not freq:
        return " ".join(sentences[:max_sentences])

    scored = []
    for index, sentence in enumerate(sentences):
        tokens = [w for w in tokenize(sentence) if w in freq]
        if not tokens:
            continue
        score = sum(freq[w] for w in tokens) / (len(tokens) ** 0.7)
        # Les phrases d'introduction gardent un léger avantage
        score += max(0, (3 - index)) * 0.15
        scored.append((score, index, sentence))

    chosen = sorted(sorted(scored, reverse=True)[:max_sentences], key=lambda item: item[1])
    return " ".join(sentence for _score, _index, sentence in chosen)


def _action_items(text, language):
    patterns = ACTION_PATTERNS.get(language, ACTION_PATTERNS["fr"])
    seen = set()
    items = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            item = match.group(0).strip(" .;:\n\t")
            normalized = re.sub(r"\s+", " ", item.lower())
            if len(item) < 4 or normalized in seen:
                continue
            seen.add(normalized)
            items.append(item[0].upper() + item[1:])
    return items[:10]


def _sentiment(text, language):
    tokens = set(tokenize(text))
    positive = len(tokens & set(POSITIVE.get(language, POSITIVE["fr"])))
    negative = len(tokens & set(NEGATIVE.get(language, NEGATIVE["fr"])))
    if positive == negative:
        label, score = "neutre" if language == "fr" else "neutral", 0.0
    elif positive > negative:
        label, score = "positif" if language == "fr" else "positive", round(positive / (positive + negative), 2)
    else:
        label, score = "négatif" if language == "fr" else "negative", round(-negative / (positive + negative), 2)
    return {"label": label, "score": score, "positive_hits": positive, "negative_hits": negative}


def analyze_extractive(text, language="fr"):
    language = language if language in STOPWORDS else "fr"
    return {
        "summary": _summary(text, language),
        "action_items": _action_items(text, language),
        "keywords": _keywords(text, language),
        "sentiment": _sentiment(text, language),
    }
