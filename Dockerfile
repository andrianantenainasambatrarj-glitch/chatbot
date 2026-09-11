# Image backend : Flask + ffmpeg + modèles Vosk (et Whisper en option)
FROM python:3.11-slim

# ffmpeg : conversion/décodage de tous les formats audio
# libgomp1 : requis par ctranslate2 (moteur de faster-whisper)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Arguments de construction :
#  DOWNLOAD_MODEL=1   télécharge le petit modèle Vosk français (~40 Mo)
#  INSTALL_WHISPER=1  installe faster-whisper et pré-télécharge le modèle
#  WHISPER_MODEL_SIZE tiny|base|small (tiny : ~75 Mo, sûr en 512 Mo de RAM ;
#  base : plus précis mais ~300-400 Mo en crête, réserver 1 Go de RAM)
ARG DOWNLOAD_MODEL=1
ARG DOWNLOAD_EN_MODEL=1
ARG INSTALL_WHISPER=1
ARG WHISPER_MODEL_SIZE=tiny

COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY requirements-whisper.txt ./
RUN if [ "$INSTALL_WHISPER" = "1" ]; then \
        pip install --no-cache-dir -r requirements-whisper.txt; \
    fi

COPY . .

# Le cache HuggingFace est placé dans l'image pour un fonctionnement hors-ligne
ENV HF_HOME=/app/.hf-cache
RUN if [ "$DOWNLOAD_MODEL" = "1" ]; then python scripts/download_model.py; fi
RUN if [ "$DOWNLOAD_EN_MODEL" = "1" ]; then \
        python scripts/download_model.py --model vosk-model-small-en-us-0.15; \
    fi
# Modèles Vosk disponibles pour le temps réel (fr + en)
ENV VOSK_MODELS={\"fr\":\"models/vosk-model-small-fr-0.22\",\"en\":\"models/vosk-model-small-en-us-0.15\"}
RUN if [ "$INSTALL_WHISPER" = "1" ]; then \
        python -c "from faster_whisper import WhisperModel; \
import io, wave, numpy as np; \
m = WhisperModel('$WHISPER_MODEL_SIZE', device='cpu', compute_type='int8', cpu_threads=1); \
buf = io.BytesIO(); w = wave.open(buf, 'wb'); w.setnchannels(1); w.setsampwidth(2); \
w.setframerate(16000); w.writeframes(np.zeros(16000, dtype=np.int16).tobytes()); w.close(); \
open('/tmp/silence.wav','wb').write(buf.getvalue()); \
segs, _ = m.transcribe('/tmp/silence.wav', language='fr', beam_size=1, vad_filter=True, condition_on_previous_text=False); \
list(segs)"; \
    fi

ENV DATA_DIR=/app/data \
    HOST=0.0.0.0 \
    PORT=5001 \
    WHISPER_MODEL_SIZE=$WHISPER_MODEL_SIZE

VOLUME ["/app/data"]
EXPOSE 5001

# Worker gevent-websocket requis pour les WebSockets temps réel.
# Le port est dynamique ($PORT) : Render et la plupart des plateformes
# l'injectent ; en local/compose on retombe sur 5001.
CMD ["sh", "-c", "gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 --bind 0.0.0.0:${PORT:-5001} --timeout 600 chatbot:app"]
