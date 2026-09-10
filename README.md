# 🎙️ Chatbot Vocal

Application web de **transcription vocale multilingue** : enregistrez votre voix
en direct ou importez un fichier audio, le serveur transcrit avec
[Vosk](https://alphacephei.com/vosk/) (100 % hors-ligne) ou **Whisper** (optionnel)
et génère des documents **Word, PDF, TXT et sous-titres SRT**.

## ✨ Fonctionnalités

- 🔐 **Comptes utilisateurs** (JWT) : chaque transcription est privée
- 📡 **Transcription en temps réel** par WebSocket (texte qui apparaît pendant la parole)
- 🎤 Enregistrement avec **chronomètre, pause/reprise et réécoute avant l'envoi**
- 📁 Import multi-formats : WAV, MP3, M4A, OGG, WEBM, MP4, FLAC, AAC, OPUS, WMA
- ⏳ Gros fichiers traités **en arrière-plan avec barre de progression** (file de tâches)
- 🌍 **Multilingue et multi-moteurs** : Vosk (streaming, hors-ligne) ou faster-whisper
- 📝 Texte **éditable** ; exports **DOCX / PDF / TXT / SRT** (mots horodatés)
- 🗄️ Persistance en **SQLite/PostgreSQL** (SQLAlchemy)
- 🇫🇷🇬🇧 Interface bilingue **FR/EN**, mode sombre, **PWA** installable
- 🔒 Rate limiting, CORS restreint, validation des formats ; Docker + CI

## 🏗️ Architecture

```
Navigateur (React, port 3000)
   ├── POST /api/transcribe   : synchro (petit) ou 202 + GET /api/jobs/<id> (gros)
   ├── WS   /ws/transcribe    : flux PCM 16 kHz -> Vosk en temps réel
   └── /api/auth/*            : inscription, connexion, JWT
        ▼
Flask (port 5001)
   ├── Auth JWT (PyJWT) + Flux de tâches (ThreadPoolExecutor)
   ├── Moteurs : engines/vosk_engine.py · engines/whisper_engine.py
   ├── pydub + ffmpeg → WAV mono 16 kHz
   ├── SQLAlchemy → SQLite (users, transcriptions, jobs)
   └── exporters → DOCX, PDF, TXT, SRT dans data/transcriptions/
```

## ✅ Prérequis

- **Python 3.10+**, **Node.js 18+**
- **ffmpeg** :
  - Ubuntu/Debian : `sudo apt install -y ffmpeg`
  - macOS : `brew install ffmpeg`
  - Windows : <https://ffmpeg.org/download.html> (à ajouter au `PATH`)

## 🚀 Démarrage en développement

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_model.py         # modèle Vosk français (~40 Mo)
cp .env.example .env                     # pensez à changer JWT_SECRET_KEY
python chatbot.py                        # http://localhost:5001

# Frontend
cd frontend && npm install && npm start  # http://localhost:3000
```

### Modèles supplémentaires (autres langues)

```bash
python scripts/download_model.py --model vosk-model-small-en-us-0.15
```

Déclarez ensuite chaque modèle dans la variable `VOSK_MODELS` (JSON
langue → chemin), voir `.env.example`.

### Moteur Whisper (optionnel, grande précision)

```bash
pip install -r requirements-whisper.txt   # installe faster-whisper
# Le premier usage télécharge le modèle (WHISPER_MODEL_SIZE=small|medium|large-v3)
```

## 🐳 Docker

```bash
docker compose up --build
```

Application servie par nginx sur <http://localhost:8080> (API et WebSocket
relayés vers le backend gevent/gunicorn), données dans le volume `chatbot-data`.

## 🔌 API

Toutes les routes `/api/*` (sauf `/api/auth/register` et `/api/auth/login`)
exigent un en-tête `Authorization: Bearer <jeton>`.

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/auth/register` | `{email, password}` → `{token, user}` (201) |
| `POST` | `/api/auth/login` | Connexion, renvoie un jeton |
| `GET` | `/api/auth/me` | Utilisateur courant |
| `GET` | `/api/engines` | Moteurs et langues disponibles |
| `POST` | `/api/transcribe` | Champ `audio` + `engine`, `language`, `async` → 201 ou **202 + tâche** |
| `GET` | `/api/jobs` · `/api/jobs/<id>` | Suivi des tâches (`status`, `progress`, résultat) |
| `GET` | `/api/transcriptions` | Liste de l'utilisateur (récent d'abord) |
| `GET/PATCH/DELETE` | `/api/transcriptions/<id>` | Détail, édition de texte, suppression |
| `DELETE` | `/api/transcriptions` | Vide l'historique de l'utilisateur |
| `GET` | `/api/transcriptions/<id>/export/<docx\|pdf\|txt\|srt>` | Téléchargement |
| `WS` | `/ws/transcribe?token=<jwt>&language=fr` | Temps réel : trames PCM 16 kHz, messages JSON `ready/partial/final/error` |

Exemple :

```bash
TOKEN=$(curl -s -X POST localhost:5001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"a@b.co","password":"motdepasse123"}' | python -c 'import sys,json;print(json.load(sys.stdin)["token"])')

curl -X POST -F "audio=@entretien.mp3" -F "engine=vosk" -F "language=fr" \
  -H "Authorization: Bearer $TOKEN" http://localhost:5001/api/transcribe
```

## ⚙️ Configuration

Voir `.env.example` : `JWT_SECRET_KEY`, `DATABASE_URL`, `VOSK_MODELS`,
`DEFAULT_ENGINE`, `ASYNC_THRESHOLD_MB`, `WHISPER_*`, `RATELIMIT_*`,
`CORS_ORIGINS`, `MAX_CONTENT_LENGTH_MB`. Côté frontend : `REACT_APP_API_URL`
(dans `frontend/.env.example`).

## 🧪 Tests et qualité

```bash
pip install -r requirements-dev.txt
ruff check .
python -m pytest tests/ -v          # 35 tests (Vosk/ffmpeg mockés)

cd frontend
npx eslint src
npm test -- --watchAll=false
npm run build
```

Le tout est exécuté par **GitHub Actions** (`.github/workflows/ci.yml`).

## 📦 Notes de production

- Serveur WebSocket : `gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker ...`
  (déjà configuré dans le `Dockerfile`)
- Changez impérativement `JWT_SECRET_KEY` ; avec plusieurs workers/processus,
  utilisez **Redis** pour le rate limiting (`RATELIMIT_STORAGE_URI`)
- PostgreSQL via `DATABASE_URL`, fichiers exportables vers un stockage S3

## 🗺️ Feuille de route

Voir [**ROADMAP.md**](ROADMAP.md) (diarisation, résumés IA, commandes vocales,
SaaS, multi-locataire…).

## 📂 Structure

```
chatbot.py            # factory Flask + routes REST
config.py             # configuration par variables d'environnement
auth.py               # JWT, inscription / connexion
ratelimit.py          # Flask-Limiter
models.py             # User, Transcription, Job (SQLAlchemy)
services.py           # pipeline métier : conversion → moteur → exports
jobs.py               # tâches asynchrones (ThreadPoolExecutor)
streaming.py          # session WebSocket temps réel
audio_pipeline.py     # conversion ffmpeg
exporters.py          # DOCX, PDF, TXT, SRT
engines/              # vosk_engine.py, whisper_engine.py
tests/                # pytest
scripts/download_model.py
Dockerfile · docker-compose.yml · .github/workflows/ci.yml
frontend/             # React : AuthScreen, LiveMode, i18n, PWA (sw.js)
```
