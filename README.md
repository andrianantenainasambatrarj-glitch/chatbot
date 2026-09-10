# 🎙️ Chatbot Vocal

Application web de **transcription vocale en français** : enregistrez votre voix
dans le navigateur, le serveur transcrit l'audio avec [Vosk](https://alphacephei.com/vosk/)
(100 % hors-ligne, aucune donnée n'envoie dans le cloud) et génère un document
**Word (.docx)** téléchargeable. L'historique des transcriptions est conservé côté serveur.

![Stack](https://img.shields.io/badge/stack-Flask%20%E2%80%A2%20React%20%E2%80%20Vosk-00aaff)

## 🏗️ Architecture

```
Navigateur (React, port 3000)
   │  MediaRecorder (webm → wav dans le navigateur)
   │  POST /api/transcribe (relayé par le proxy CRA en développement)
   ▼
Flask (port 5001)
   ├── Vosk                 : reconnaissance vocale (mono, 16 kHz, 16-bit)
   ├── pydub + ffmpeg       : conversion audio
   ├── python-docx          : génération du document Word
   └── data/
       ├── transcriptions/  : documents Word (nom unique par transcription)
       └── transcription_history.json
```

## ✅ Prérequis

- **Python 3.10+**
- **Node.js 18+** et npm
- **ffmpeg** (requis par `pydub` pour décoder/convertir l'audio) :
  - **Ubuntu / Debian** : `sudo apt update && sudo apt install -y ffmpeg`
  - **macOS** (Homebrew) : `brew install ffmpeg`
  - **Windows** : téléchargez-le sur <https://ffmpeg.org/download.html> et ajoutez-le au `PATH`

## 🚀 Installation

### 1. Backend

```bash
# Depuis la racine du projet
python3 -m venv .venv
source .venv/bin/activate           # Windows : .venv\Scripts\activate
pip install -r requirements.txt

# Télécharger le modèle Vosk français (~40 Mo pour le petit modèle)
python scripts/download_model.py

# Configuration (optionnel, des valeurs par défaut existent)
cp .env.example .env

# Démarrage
python chatbot.py
```

Le serveur démarre sur <http://localhost:5001>.
Vérifiez l'état du service sur <http://localhost:5001/health>.

Pour le grand modèle Vosk, plus précis (~1,8 Go) :

```bash
python scripts/download_model.py --model vosk-model-fr-0.22
# puis adaptez MODEL_PATH dans .env
```

### 2. Frontend

```bash
cd frontend
npm install
npm start
```

L'application s'ouvre sur <http://localhost:3000>. Les appels API sont relayés
vers le backend sur le port 5001 grâce à la clé `proxy` de `package.json`.

> ⚠️ L'accès au microphone nécessite **HTTPS** ou `localhost`. Pour un autre nom
> d'hôte, configurez un certificat (ou un tunnel HTTPS) et renseignez
> `REACT_APP_API_URL` (voir `frontend/.env.example`).

## 🔌 API

| Méthode | Route | Description |
|---|---|---|
| `GET`  | `/health` | État du service et disponibilité du modèle |
| `POST` | `/api/transcribe` | Envoie un champ `audio` (WAV), retourne la transcription (201) |
| `GET`  | `/api/transcriptions` | Liste l'historique (du plus récent au plus ancien) |
| `GET`  | `/api/transcriptions/<id>` | Détail d'une transcription |
| `GET`  | `/api/transcriptions/<id>/download` | Télécharge le document Word |
| `DELETE` | `/api/transcriptions/<id>` | Supprime une transcription et son document |
| `DELETE` | `/api/transcriptions` | Vide tout l'historique |

Exemple :

```bash
curl -X POST -F "audio=@mon_enregistrement.wav" http://localhost:5001/api/transcribe
```

## ⚙️ Configuration (variables d'environnement)

| Variable | Défaut | Description |
|---|---|---|
| `FLASK_DEBUG` | `0` | Mode debug Flask (**jamais `1` en production**) |
| `HOST` | `0.0.0.0` | Interface d'écoute |
| `PORT` | `5001` | Port du serveur |
| `MODEL_PATH` | `models/vosk-model-small-fr-0.22` | Dossier du modèle Vosk |
| `DATA_DIR` | `data` | Stockage (documents + historique) |
| `MAX_CONTENT_LENGTH_MB` | `50` | Taille maximale des uploads audio |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Origines autorisées, séparées par des virgules |

## 🧪 Tests

```bash
# Frontend
cd frontend && npm test -- --watchAll=false

# Build de production
npm run build
```

## 📦 Déploiement (manuel)

1. `pip install gunicorn` puis :
   `gunicorn -w 2 -b 0.0.0.0:5001 'chatbot:app'`
2. Compilez le frontend avec `npm run build` dans `frontend/` et servez le
   dossier `build/` avec un reverse proxy (nginx) — ou par Flask.
3. Définissez `CORS_ORIGINS` et, côté frontend, `REACT_APP_API_URL`.

## 🗺️ Feuille de route

Voir [**ROADMAP.md**](ROADMAP.md) : analyse complète, bugs, fonctionnalités
(temps réel, Whisper, authentification, résumés IA, PWA…) et roadmap en sprints.

## 📂 Structure du projet

```
.
├── chatbot.py                 # API Flask
├── requirements.txt           # dépendances Python (versions figées)
├── scripts/
│   └── download_model.py      # téléchargement du modèle Vosk
├── data/                      # généré au runtime (ignoré par Git)
├── models/                    # modèle Vosk (ignoré par Git)
└── frontend/                  # application React (Create React App)
    ├── public/                # index.html, manifest PWA
    └── src/
        ├── App.js
        ├── App.test.js
        └── styles.css
```
