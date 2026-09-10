# 🎙️ Chatbot Vocal

Application web de **transcription vocale multilingue** : enregistrez votre voix
en direct ou importez un fichier audio, le serveur transcrit avec
[Vosk](https://alphacephei.com/vosk/) (100 % hors-ligne) ou **Whisper** (optionnel)
et génère des documents **Word, PDF, TXT et sous-titres SRT**.

## ✨ Fonctionnalités

- 🔐 **Comptes utilisateurs** (JWT), rôles **admin**, **quotas mensuels** ; transcriptions privées
- 📡 **Transcription en temps réel** par WebSocket (texte qui apparaît pendant la parole)
- 🗣️ **Commandes vocales** : « nouvel enregistrement », « mode sombre », « télécharger word »,
  « tableau de bord », « résumé », « déconnexion »… (WebSocket `/ws/commands`, FR/EN)
- 🎙️ **Diarisation légère** : séparation Intervenant 1 / Intervenant 2 sur les silences
- 🧠 **Analyse automatique** : résumé extractif, actions à faire, mots-clés, tonalité
  (100 % hors-ligne), ou via un **LLM** optionnel compatible OpenAI / Ollama
- 💬 **Chat questions/réponses** sur chaque transcription (LLM ou recherche de similarité)
- 🔊 **Synthèse vocale** (lecture audio du texte et des réponses, Web Speech API)
- 🔗 **Partage par lien** signé et expirable (30 jours, lecture publique sans compte)
- ✉️ Envoi par **e-mail** (SMTP) et **webhooks** (n8n, Zapier, Notion…)
- 📊 **Tableau de bord** : activité, minutes, moteurs, langues ; **espace admin** (rôles, quotas)
- 🎤 Enregistrement avec **chronomètre, pause/reprise et réécoute avant l'envoi**
- 📁 Import multi-formats : WAV, MP3, M4A, OGG, WEBM, MP4, FLAC, AAC, OPUS, WMA
- ⏳ Gros fichiers traités **en arrière-plan avec barre de progression** (file de tâches)
- 🌍 **Multilingue et multi-moteurs** : Vosk (streaming, hors-ligne) ou faster-whisper
- 📝 Texte **éditable** ; exports **DOCX / PDF / TXT / SRT** (mots horodatés)
- 🗄️ Persistance en **SQLite/PostgreSQL** (SQLAlchemy, migration automatique SQLite)
- 🇫🇷🇬🇧 Interface bilingue **FR/EN**, mode sombre, **PWA** installable
- 📈 Métriques **Prometheus** (`/metrics`), rate limiting, CORS, Docker + CI

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
| `POST` | `/api/transcribe` | Champ `audio` + `engine`, `language`, `diarize`, `async` → 201 ou **202 + tâche** (402 si quota dépassé) |
| `GET` | `/api/jobs` · `/api/jobs/<id>` | Suivi des tâches (`status`, `progress`, résultat) |
| `GET` | `/api/transcriptions` | Liste de l'utilisateur (récent d'abord) |
| `GET/PATCH/DELETE` | `/api/transcriptions/<id>` | Détail, édition de texte, suppression |
| `DELETE` | `/api/transcriptions` | Vide l'historique de l'utilisateur |
| `GET` | `/api/transcriptions/<id>/export/<docx\|pdf\|txt\|srt>` | Téléchargement |
| `POST/GET` | `/api/transcriptions/<id>/insights` | Résumé, actions, mots-clés, tonalité |
| `POST` | `/api/transcriptions/<id>/chat` | `{message, history}` → réponse sur le contenu |
| `POST/GET/DELETE` | `/api/transcriptions/<id>/share[/<token>]` | Gestion des liens de partage |
| `GET` | `/api/shared/<token>[/export/<fmt>]` | **Public** : lecture/téléchargement via un lien |
| `POST` | `/api/transcriptions/<id>/email` | Envoi par e-mail `{email}` (SMTP) |
| `POST` | `/api/transcriptions/<id>/webhook` | Publication JSON `{url}` |
| `GET` | `/api/stats` | Tableau de bord de l'utilisateur |
| `GET/PATCH` | `/api/admin/users[/<id>]`, `/api/admin/stats` | **Admin** : rôles et quotas |
| `GET` | `/metrics` | Métriques Prometheus (optionnel : `METRICS_TOKEN`) |
| `WS` | `/ws/transcribe?token=<jwt>&language=fr` | Temps réel : trames PCM 16 kHz, messages `ready/partial/final/error` |
| `WS` | `/ws/commands?token=<jwt>&language=fr` | Commandes vocales : messages `command/heard/partial` |

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
`CORS_ORIGINS`, `MAX_CONTENT_LENGTH_MB`, `DEFAULT_QUOTA_MINUTES`,
`ADMIN_EMAILS`, `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` (ou Ollama en local),
`SMTP_*`, `METRICS_TOKEN`, `DIARIZE_GAP_SECONDS`. Côté frontend :
`REACT_APP_API_URL` (dans `frontend/.env.example`).

Sans `LLM_API_KEY`, les analyses et le chat utilisent un moteur **extractif
hors-ligne** (les réponses sont plus simples mais aucune donnée ne sort du serveur).

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
auth.py               # JWT, inscription/connexion, décorateurs user/admin
ratelimit.py          # Flask-Limiter
models.py             # User, Transcription, Job, ShareLink (SQLAlchemy)
migrations.py         # migration automatique SQLite (colonnes de sprint en sprint)
services.py           # pipeline métier : conversion → moteur → diarisation → exports
jobs.py               # tâches asynchrones (ThreadPoolExecutor)
streaming.py          # WebSockets temps réel : /ws/transcribe et /ws/commands
diarize.py            # séparation des interlocuteurs par les silences
commands.py           # motifs de commandes vocales FR/EN
nlp/                  # analyse extractive hors-ligne, chat, client LLM optionnel
integrations.py       # e-mail SMTP et webhooks
metrics.py            # métriques Prometheus
audio_pipeline.py     # conversion ffmpeg
exporters.py          # DOCX, PDF, TXT, SRT
engines/              # vosk_engine.py, whisper_engine.py
tests/                # pytest (54 tests)
scripts/download_model.py
Dockerfile · docker-compose.yml · .github/workflows/ci.yml
frontend/src/         # App, AuthScreen, LiveMode, CommandMic, DashboardView,
                      # TranscriptionActions, api/i18n/speech/audioStream
```
