"""Client LLM optionnel, compatible API OpenAI (dont Ollama en local).

Configuration par variables d'environnement :
  LLM_API_KEY      : clé API (factice pour Ollama)
  LLM_BASE_URL     : ex. https://api.openai.com/v1 (défaut) ou http://localhost:11434/v1
  LLM_MODEL        : ex. gpt-4o-mini (défaut) ou llama3.1 pour Ollama
"""

import json
import os
import urllib.error
import urllib.request

from flask import current_app


def is_configured():
    if current_app:
        return bool(current_app.config.get("LLM_API_KEY"))
    return bool(os.environ.get("LLM_API_KEY"))


class LLMClient:
    def __init__(self, timeout=60):
        self.timeout = timeout

    def _config(self):
        cfg = current_app.config
        return (
            cfg.get("LLM_BASE_URL", "https://api.openai.com/v1"),
            cfg.get("LLM_API_KEY", ""),
            cfg.get("LLM_MODEL", "gpt-4o-mini"),
        )

    def _chat(self, messages, temperature=0.3):
        base_url, api_key, model = self._config()
        payload = json.dumps(
            {"model": model, "messages": messages, "temperature": temperature}
        ).encode()
        request = urllib.request.Request(
            base_url.rstrip("/") + "/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read())
        return data["choices"][0]["message"]["content"].strip()

    def analyze(self, transcription_text, language="fr"):
        lang_name = {"fr": "français", "en": "anglais"}.get(language, language)
        system = (
            "Tu es un assistant de réunion. Analyse la transcription ci-jointe. "
            f"Réponds UNIQUEMENT en {lang_name} et uniquement avec un objet JSON valide "
            'de la forme : {"summary": string, "action_items": string[], '
            '"keywords": string[], "sentiment": {"label": "positif|neutre|négatif", "score": number}}. '
            "Le résumé tient en 3 à 5 phrases ; les actions commencent par un verbe à l'infinitif."
        )
        content = self._chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": transcription_text[:12000]},
            ]
        )
        return self._parse_json_analysis(content)

    def answer(self, transcription_text, question, history=None, language="fr"):
        """Répond à une question sur la transcription ; conseille si hors sujet."""
        context = transcription_text[:16000]
        messages = [
            {
                "role": "system",
                "content": (
                    "Tu réponds uniquement à partir de la transcription fournie. "
                    "Si la réponse n'y figure pas, dis-le clairement. "
                    f"Réponds en {language}."
                ),
            },
        ]
        for turn in history or []:
            if turn.get("role") in ("user", "assistant"):
                messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": f"Transcription :\n{context}\n\nQuestion : {question}"})
        return self._chat(messages, temperature=0.2)

    @staticmethod
    def _parse_json_analysis(content):
        # Retire un éventuel ```json ... ```
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned[cleaned.find("{"): cleaned.rfind("}") + 1]
        start, end = cleaned.find("{"), cleaned.rfind("}")
        data = json.loads(cleaned[start:end + 1])
        return {
            "summary": str(data.get("summary", "")),
            "action_items": [str(item) for item in data.get("action_items", [])],
            "keywords": [str(word) for word in data.get("keywords", [])],
            "sentiment": data.get("sentiment", {"label": "neutre", "score": 0}),
        }
