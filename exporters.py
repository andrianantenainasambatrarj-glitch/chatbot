"""Génération des fichiers d'export : DOCX, PDF, TXT, SRT."""

import html
from datetime import datetime

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _footer_date():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------
def render_docx(text, path, *, language="fr", duration_seconds=None):
    doc = Document()
    doc.add_heading("Transcription Vocale", level=0)
    meta = doc.add_paragraph()
    run = meta.add_run(f"Généré le {_footer_date}")
    run.italic = True
    if duration_seconds:
        meta.add_run(f" — Durée audio : {_format_duration(duration_seconds)}")
    if language:
        meta.add_run(f" — Langue : {language}")
    doc.add_paragraph(text)
    doc.save(path)


# ---------------------------------------------------------------------------
# TXT
# ---------------------------------------------------------------------------
def render_txt(text, path, **_kwargs):
    with open(path, "w", encoding="utf-8") as f:
        f.write("Transcription Vocale\n")
        f.write(f"Généré le {_footer_date()}\n\n")
        f.write(text)
        f.write("\n")


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def render_pdf(text, path, *, language="fr", duration_seconds=None, **_kwargs):
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Transcription Vocale",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Titre", parent=styles["Title"], fontSize=20, spaceAfter=12
    )
    meta_style = ParagraphStyle("Meta", parent=styles["Normal"], fontSize=9, textColor="#666666")
    body_style = ParagraphStyle(
        "Corps", parent=styles["Normal"], fontSize=11, leading=16, spaceAfter=8
    )

    story = [Paragraph("Transcription Vocale", title_style)]
    meta = f"Généré le {html.escape(_footer_date())}"
    if duration_seconds:
        meta += f" — Durée audio : {_format_duration(duration_seconds)}"
    if language:
        meta += f" — Langue : {html.escape(language)}"
    story.append(Paragraph(meta, meta_style))
    story.append(Spacer(1, 12))

    # ReportLab gère le retour à la ligne automatique ; on respecte les sauts de ligne
    for paragraph in text.split("\n") or [""]:
        escaped = html.escape(paragraph).strip() or "&nbsp;"
        story.append(Paragraph(escaped, body_style))

    doc.build(story)


# ---------------------------------------------------------------------------
# SRT (sous-titres à partir des mots horodatés Vosk)
# ---------------------------------------------------------------------------
def render_srt(words, path, *, max_words_per_line=8, max_line_seconds=5.0, **_kwargs):
    """Génère un fichier .srt à partir de mots Vosk [{word, start, end}, ...]."""
    if not words:
        return

    lines = []
    buffer = []

    def flush(index):
        if not buffer:
            return index
        start = buffer[0]["start"]
        end = buffer[-1]["end"]
        text = " ".join(w["word"] for w in buffer).capitalize()
        lines.append(
            f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}\n"
        )
        buffer.clear()
        return index + 1

    index = 1
    for word in words:
        if not all(k in word for k in ("word", "start", "end")):
            continue
        buffer.append(word)
        if (
            len(buffer) >= max_words_per_line
            or (buffer[-1]["end"] - buffer[0]["start"]) >= max_line_seconds
        ):
            index = flush(index)
    flush(index)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _srt_time(seconds):
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_duration(seconds):
    seconds = int(seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    return f"{minutes}m{secs:02d}s"
