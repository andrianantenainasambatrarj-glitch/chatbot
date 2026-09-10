# Image backend : Flask + ffmpeg + modèle Vosk
FROM python:3.11-slim

# ffmpeg : conversion/décodage de tous les formats audio
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Télécharge le petit modèle Vosk français au build (1) ou non (0)
ARG DOWNLOAD_MODEL=1
RUN if [ "$DOWNLOAD_MODEL" = "1" ]; then python scripts/download_model.py; fi

ENV DATA_DIR=/app/data \
    HOST=0.0.0.0 \
    PORT=5001

VOLUME ["/app/data"]
EXPOSE 5001

# --timeout élevé : la transcription de gros fichiers peut prendre du temps
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5001", "--timeout", "600", "chatbot:app"]
