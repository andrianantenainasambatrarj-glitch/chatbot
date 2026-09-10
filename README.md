# 🎙️ Chatbot Vocal

Application web de **transcription vocale en français** : enregistrez votre voix
(directement dans le navigateur, avec pause et réécoute) ou importez un fichier
audio, le serveur transcrit avec [Vosk](https://alphacephei.com/vosk/)
(100 % hors-ligne, aucune donnée n'est envoyée dans le cloud).

Fonctionnalités :

- 🎤 Enregistrement micro avec **chronomètre, pause/reprise et réécoute avant l'envoi**
- 📁 **Import de fichiers** : WAV, MP3, M4A, OGG, WEBM, MP4, FLAC, AAC, OPUS, WMA
- 📝 Texte **éditable** avant export (les documents sont régénérés)
- 📄 Exports **Word (.docx), PDF, TXT** et **sous-titres SRT** (mots horodatés)
- 🗄️ Historique persistant en **base SQLite** (compatible PostgreSQL), suppression unitaire ou globale
- 🌙 Mode sombre, interface en français, PWA-ready
- 🔒 Limitation de débit (rate limiting), CORS restreint, validation des formats

## 🏗️ Architecture

```
Navigateur (React, port 3000)
   │  MediaRecorder (webm/ogg/mp4) ou import de fichier
   │  POST /api/transcribe (proxy CRA en développement, nginx en Docker)
   ▼
Flask (port 5001)
   ├── pydub + ffmpeg        : conversion (mono, 16 kHz, 16-bit)
   ├── Vosk                  : reconnaissance vocale + mots horodatés
   ├── SQLAlchemy / SQLite   : persistance des transcriptions
   ├── exporters             : DOCX (python-docx), PDF (reportlab), TXT, SRT
   └── data/
       ├── chatbot.db
       └── transcriptions/   : fichiers générés (nom unique par transcription)
```

## ✅ Prérequis

- **Python 3.10+**
- **Node.js 18+** et npm
- **ffmpeg** (requis par `pydub`) :
  - **Ubuntu / Debian** : `sudo apt update && sudo apt install -y ffmpeg`
  - **macOS** (Homebrew) : `brew install ffmpeg`
  - **Windows** : <https://ffmpeg.org/download.html>, puis ajoutez-le au `PATH`

## 🚀 Démarrage rapide (développement)

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate           # Windows : .venv\Scripts\activate
pip install -r requirements.txt

python scripts/download_model.py    # modèle Vosk français (~40 Mo)
cp .env.example .env                # configuration (optionnel)

python chatbot.py                   # http://localhost:5001
```

Vérification : <http://localhost:5001/health> (état base de données + modèle).

### Frontend

```bash
cd frontend
npm install
npm start                           # http://localhost:3000
```

Les appels API sont relayés vers le port 5001 par la clé `proxy` de
`package.json`. En production, renseignez `REACT_APP_API_URL`
(voir `frontend/.env.example`).

> ⚠️ L'accès au microphone nécessite **HTTPS** ou `localhost`.

## 🐳 Démarrage avec Docker (recommandé en production)

```bash
docker compose up --build
```

- Frontend + nginx : <http://localhost:8080>
- L'API est relayée par nginx (`/api`, `/health`) vers le backend
- Le modèle Vosk est téléchargé lors du build de l'image backend
- Les transcriptions sont conservées dans le volume Docker `chatbot-data`

Variables utiles dans `docker-compose.yml` : `CORS_ORIGINS`,
`MAX_CONTENT_LENGTH_MB`, `RATELIMIT_*`. Pour utiliser le grand modèle Vosk,
recompilez avec le modèle monté dans `./models` et `DOWNLOAD_MODEL=0`.

## 🔌 API

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/health` | État du service, de la base et du modèle |
| `POST` | `/api/transcribe` | Champ `audio` (formats acceptés ci-dessus) → 201 + transcription |
| `GET` | `/api/transcriptions` | Liste, du plus récent au plus ancien |
| `GET` | `/api/transcriptions/<id>` | Détail d'une transcription |
| `PATCH` | `/api/transcriptions/<id>` | Corrige le texte (`{"text": "..."}`) et régénère DOCX/PDF/TXT |
| `DELETE` | `/api/transcriptions/<id>` | Supprime une transcription et ses fichiers |
| `DELETE` | `/api/transcriptions` | Vide l'historique |
| `GET` | `/api/transcriptions/<id>/export/<fmt>` | `docx`, `pdf`, `txt` ou `srt` |

Exemple :

```bash
curl -X POST -F "audio=@entretien.mp3" http://localhost:5001/api/transcribe
```

Réponse (201) :

```json
{
  "id": "uuid",
  "text": "texte transcrit",
  "language": "fr",
  "duration_seconds": 12.4,
  "has_timestamps": true,
  "created_at": "2026-09-10T08:00:00+00:00",
  "exports": {
    "docx": "/api/transcriptions/uuid/export/docx",
    "pdf":  "/api/transcriptions/uuid/export/pdf",
    "txt":  "/api/transcriptions/uuid/export/txt",
    "srt":  "/api/transcriptions/uuid/export/srt"
  }
}
```

## ⚙️ Configuration (variables d'environnement)

| Variable | Défaut | Description |
|---|---|---|
| `FLASK_DEBUG` | `0` | Mode debug (jamais `1` en production) |
| `HOST` / `PORT` | `0.0.0.0` / `5001` | Interface d'écoute |
| `MODEL_PATH` | `models/vosk-model-small-fr-0.22` | Dossier du modèle Vosk |
| `DATA_DIR` | `data` | Base SQLite + documents générés |
| `DATABASE_URL` | SQLite dans `DATA_DIR` | URL SQLAlchemy (PostgreSQL, etc.) |
| `LANGUAGE` | `fr` | Langue indiquée dans les exports |
| `MAX_CONTENT_LENGTH_MB` | `100` | Taille maximale des uploads |
| `RATELIMIT_TRANSCRIBE` | `10/minute` | Limite de transcription par IP |
| `RATELIMIT_DEFAULT` | `300/hour` | Limite globale par IP |
| `RATELIMIT_STORAGE_URI` | `memory://` | Stockage des compteurs (Redis en multi-workers) |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Origines autorisées |

## 🧪 Tests

```bash
# Backend (pytest, le modèle Vosk et ffmpeg sont mockés)
pip install -r requirements-dev.txt
python -m pytest tests/ -v

# Frontend
cd frontend
npm test -- --watchAll=false
npm run build
```

Les tests s'exécutent aussi automatiquement dans **GitHub Actions**
(`.github/workflows/ci.yml`) à chaque push / pull request.

## 📦 Déploiement manuel

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:5001 --timeout 600 'chatbot:app'
```

Compilez ensuite le frontend (`npm run build`) et servez `build/` avec nginx,
en relayant `/api` et `/health` vers gunicorn (une configuration prête à
l'emploi est fournie dans `frontend/nginx.conf`).

## 🗺️ Feuille de route

Voir [**ROADMAP.md**](ROADMAP.md) : analyse, fonctionnalités (temps réel, Whisper,
authentification, résumés IA, diarisation…) et roadmap en sprints.

## 📂 Structure du projet

```
.
├── chatbot.py              # Application Flask (factory + routes)
├── config.py               # Configuration par variables d'environnement
├── models.py               # Modèle SQLAlchemy
├── audio_pipeline.py       # Conversion ffmpeg + reconnaissance Vosk
├── exporters.py            # DOCX, PDF, TXT, SRT
├── tests/                  # Tests pytest
├── scripts/download_model.py
├── Dockerfile / docker-compose.yml
├── .github/workflows/ci.yml
└── frontend/               # React (Create React App)
    ├── Dockerfile / nginx.conf
    └── src/{App.js, styles.css, App.test.js}
```
