#!/bin/bash
# Script pour migrer le projet trading vers un nouveau repo propre
# Usage: ./scripts/create_new_repo.sh <url_nouveau_repo>
# Ex: ./scripts/create_new_repo.sh https://github.com/andrianantenainasambatrarj-glitch/trading-hlz-ai.git

set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <url_nouveau_repo_github>"
  echo "Ex: $0 https://github.com/andrianantenainasambatrarj-glitch/trading-hlz-ai.git"
  exit 1
fi

NEW_REPO_URL=$1
CURRENT_DIR=$(pwd)

echo "📦 Migration Trading HLZ AI vers nouveau repo..."
echo "Source: $CURRENT_DIR (branche arena/01a09f1f-chatbot)"
echo "Destination: $NEW_REPO_URL"
echo ""

# Vérifie qu'on est bien dans le projet trading
if [ ! -f "app/main.py" ]; then
  echo "❌ Erreur: app/main.py non trouvé. Lance ce script depuis la racine du projet trading."
  exit 1
fi

# Crée un dossier temp pour le nouveau repo
TMP_DIR="/tmp/trading-hlz-migrate-$$"
mkdir -p $TMP_DIR
echo "📁 Dossier temp: $TMP_DIR"

cd $TMP_DIR
git clone $NEW_REPO_URL new_repo
cd new_repo

# Si le repo est vide, il n'a pas de main, on init
if [ ! -d ".git" ]; then
  git init
  git remote add origin $NEW_REPO_URL
fi

# Copie tous les fichiers du projet trading (sauf .git, .venv, data temp)
echo "📋 Copie des fichiers..."
rsync -av --progress $CURRENT_DIR/ ./ \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='venv' \
  --exclude='data/chroma_db/*' \
  --exclude='data/temp/*' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.env' \
  --exclude='node_modules'

# Garde les .gitkeep
touch data/pdfs/.gitkeep
touch data/chroma_db/.gitkeep
mkdir -p data/temp

# Git add
git add -A
git status

echo ""
echo "📝 Commit..."
git commit -m "feat: initial commit - TradingGraph AI HLZ Complet RAG+Vision

- RAG + Vision LLM for trading chart analysis
- HLZ specialized prompts (BOS, CHOCH, OB, FVG, Liquidities)
- Multi-style support: HLZ, SMC, ICT, Price Action, Elliott
- FastAPI + ChromaDB + Multi-LLM (OpenAI, Claude, Gemini)
- Ready to deploy free on Render/HF Spaces
" || echo "Rien à committer ou déjà committé"

echo ""
echo "🚀 Push vers $NEW_REPO_URL..."
git branch -M main
git push -u origin main --force

echo ""
echo "✅ Migration terminée!"
echo "👉 Nouveau repo: $NEW_REPO_URL"
echo "👉 Maintenant déploie ce nouveau repo sur Render.com"
echo ""
echo "Nettoyage temp..."
cd /
rm -rf $TMP_DIR

echo "Done."
