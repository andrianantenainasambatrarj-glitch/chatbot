#!/usr/bin/env bash
# Installation complète (Linux / macOS) : backend Python, modèle Vosk, frontend.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> 1/4 Environnement virtuel Python"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip

echo "==> 2/4 Dépendances backend"
pip install -r requirements.txt

echo "==> 3/4 Modèle Vosk français (~40 Mo, ignorez si déjà téléchargé)"
python scripts/download_model.py || echo "Le téléchargement a échoué (réseau ?) — relancez cette commande plus tard."

echo "==> 4/4 Dépendances frontend (Node.js)"
if command -v npm >/dev/null 2>&1; then
  (cd frontend && npm install)
else
  echo "npm introuvable : installez Node.js 18+ (https://nodejs.org) puis relancez : cd frontend && npm install"
fi

cat <<'MSG'

✅ Installation terminée !

Démarrage (2 terminaux) :
  Terminal 1 (backend)  : ./scripts/run_backend.sh
  Terminal 2 (frontend) : ./scripts/run_frontend.sh
Puis ouvrez http://localhost:3000

Vérification du modèle : http://localhost:5001/health  -> "model_available": true
MSG
