"""Intégrations sortantes : e-mail SMTP et webhooks (Zapier, n8n, Notion...)."""

import json
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib import request as urllib_request

logger = logging.getLogger("chatbot-vocal")


class EmailNotConfiguredError(RuntimeError):
    """SMTP absent de la configuration."""


def send_transcription_email(*, to_email, transcription, files, config):
    """Envoie la transcription par e-mail avec les exports en pièces jointes.

    `files` est une liste de tuples (nom_de_fichier, chemin, mime_type).
    Nécessite les variables SMTP_* ; lève EmailNotConfiguredError sinon.
    """
    host = config.get("SMTP_HOST")
    if not host:
        raise EmailNotConfiguredError(
            "L'envoi d'e-mails n'est pas configuré (variables SMTP_HOST, SMTP_PORT...)."
        )

    message = EmailMessage()
    message["Subject"] = f"Transcription vocale du {transcription.created_at:%d/%m/%Y %H:%M}"
    message["From"] = config.get("SMTP_FROM", config.get("SMTP_USER", "chatbot@example.com"))
    message["To"] = to_email
    message.set_content(
        "Bonjour,\n\n"
        "Veuillez trouver ci-joint la transcription vocale demandée.\n\n"
        f"Date : {transcription.created_at:%d/%m/%Y à %H:%M}\n"
        f"Langue : {transcription.language} — Moteur : {transcription.engine}\n\n"
        "---\n\n"
        f"{transcription.text}\n"
    )

    for filename, path, mime_type in files:
        maintype, subtype = (mime_type.split("/", 1) + ["octet-stream"])[:2]
        with open(path, "rb") as handle:
            message.add_attachment(
                handle.read(),
                maintype=maintype,
                subtype=subtype,
                filename=filename,
            )

    port = int(config.get("SMTP_PORT", "587"))
    use_ssl = bool(config.get("SMTP_USE_SSL"))
    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            if config.get("SMTP_USER"):
                server.login(config["SMTP_USER"], config.get("SMTP_PASSWORD", ""))
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            try:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            except smtplib.SMTPNotSupportedError:
                pass
            if config.get("SMTP_USER"):
                server.login(config["SMTP_USER"], config.get("SMTP_PASSWORD", ""))
            server.send_message(message)
    logger.info("Transcription %s envoyée par e-mail à %s", transcription.id, to_email)


def post_webhook(url, payload, timeout=15):
    """Publie le JSON d'une transcription vers un webhook (n8n, Zapier, Notion...)."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_obj = urllib_request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Chatbot-Vocal/1.0"},
        method="POST",
    )
    with urllib_request.urlopen(request_obj, timeout=timeout) as response:
        return response.status


def attachment_files(config, transcription):
    """Liste (nom, chemin, mime) des DOCX/PDF à joindre, en n'incluant que ceux présents."""
    base = os.path.join(config["TRANSCRIPTIONS_DIR"], transcription.base_name)
    candidates = [
        (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        (".pdf", "application/pdf"),
    ]
    files = []
    for suffix, mime in candidates:
        path = base + suffix
        if os.path.exists(path):
            files.append((f"{transcription.base_name}{suffix}", path, mime))
    return files
