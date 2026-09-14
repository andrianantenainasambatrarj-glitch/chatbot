# TradingGraph AI - Dockerfile optimized for free deploy
FROM python:3.11-slim

# Env
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# System deps for pdfplumber, pillow, chroma
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install python deps
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Optional: install torch CPU + sentence-transformers for better embeddings
# Comment out if you want ultra-light image for free tier
# RUN pip install torch --index-url https://download.pytorch.org/whl/cpu && \
#     pip install sentence-transformers==2.6.1

# Copy app
COPY . .

# Create data dirs
RUN mkdir -p data/pdfs data/chroma_db data/temp && chmod -R 777 data

# Expose - HuggingFace uses 7860, Render uses 8000
EXPOSE 8000 7860

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s \
  CMD python -c "import httpx; httpx.get('http://localhost:${PORT:-8000}/api/health', timeout=5)" || exit 1

# Start
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
