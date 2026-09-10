#!/usr/bin/env bash
# Lance le backend Flask sur http://localhost:5001
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
python chatbot.py
