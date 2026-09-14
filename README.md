# TradingGraph AI — RAG + Vision LLM 📈🤖

**Analyse de graphiques de trading avec prédiction IA basée sur VOS cours PDF**

> Upload tes PDFs de formation trading → Envoie une capture de graphique → Reçois une analyse technique complète avec prédiction, niveaux clés et explication selon TA méthode.

![Architecture](https://img.shields.io/badge/Architecture-RAG%20%2B%20Vision-violet) ![Python](https://img.shields.io/badge/Python-3.11-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green) ![Deploy](https://img.shields.io/badge/Deploy-Free%20Ready-brightgreen)

---

## 🎯 Architecture (celle que tu voulais)

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  PDF cours  │ --> │  Base vectorielle │ <-- │  Recherche RAG   │
└─────────────┘     │  (embeddings)     │     └────────┬─────────┘
                    └──────────────────┘              │
                                                        ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Image chart │ --> │  LLM avec vision │ --> │ Réponse finale  │
└─────────────┘     │  (GPT-4V/Claude) │     │ (analyse+contexte)│
                    └──────────────────┘     └─────────────────┘
```

### Pipeline détaillé

1. **Ingestion PDF** (`pdfplumber` + `PyPDF2` fallback)
   - Extraction texte page par page
   - Chunking intelligent ~400 mots avec overlap 50, respect des phrases
   - Un chunk = un concept (ex: "tête-épaules")

2. **Embeddings**
   - Priorité: `OpenAI text-embedding-3-small` si `OPENAI_API_KEY`
   - Sinon: `sentence-transformers/all-MiniLM-L6-v2` (local gratuit)
   - Fallback: TF-IDF sklearn (ultra léger, marche partout)

3. **Vector Store**
   - `ChromaDB` persistant local
   - Collection `trading_knowledge`
   - Recherche cosine similarity Top-K

4. **Vision LLM**
   - Essaie dans l'ordre: OpenAI GPT-4o-mini Vision → Claude 3.5 Sonnet Vision → Gemini 1.5 Flash → fallback local heuristique
   - Prompt expert trading: tendance, patterns, supports/résistances, bougies

5. **Synthèse finale**
   - Vision description + 5 chunks RAG → LLM texte → JSON structuré
   - Retourne: pattern principal, confiance, analyse, prédiction, niveaux clés (supports, résistances, entrée, SL, TP), risques, reco, timeframe

---

## 🚀 Déploiement Gratuit (sans PC puissant)

### Option 1: Render.com (Recommandé, 100% gratuit)

1. Fork ce repo sur GitHub
2. Va sur https://dashboard.render.com → New → Web Service
3. Connecte ton repo
4. Settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Plan: Free
5. Ajoute tes variables d'env dans Environment:
   - `OPENAI_API_KEY` = ta clé (optionnel mais recommandé)
   - `GOOGLE_API_KEY` = gratuit https://aistudio.google.com/app/apikey
6. Deploy → Tu as une URL `https://xxx.onrender.com`

> Render free s'endort après 15min sans trafic, se réveille à la requête (30s cold start).

### Option 2: HuggingFace Spaces (Gratuit + GPU possible)

1. Crée un Space sur https://huggingface.co/spaces → New Space → Docker
2. Upload ce repo
3. HF détecte `Dockerfile` et `app.py` automatiquement
4. Dans Settings → Variables, ajoute `OPENAI_API_KEY` etc.
5. URL: `https://huggingface.co/spaces/ton-user/ton-space`

Fichier `app.py` est déjà prévu pour HF (port 7860).

### Option 3: Railway.app (Gratuit $5/mois)

1. https://railway.app → New Project → Deploy from GitHub
2. Ajoute variables d'env
3. Deploy auto via `Procfile`

### Option 4: Local (si tu veux tester plus tard)

```bash
git clone <ton-repo>
cd chatbot
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Édite .env et mets au moins GOOGLE_API_KEY (gratuit) ou OPENAI_API_KEY

python run.py
# → http://localhost:8000
# Docs API: http://localhost:8000/docs
```

---

## 🔑 Clés API — Lesquelles choisir ?

| Provider | Vision? | Texte? | Prix | Lien |
|----------|---------|--------|------|------|
| **Google Gemini** | ✅ | ✅ | **Gratuit généreux** (60 req/min) | https://aistudio.google.com/app/apikey |
| **OpenAI** | ✅ `gpt-4o-mini` | ✅ | ~$0.15/1M tokens, $5 offerts | https://platform.openai.com/api-keys |
| **Anthropic Claude** | ✅ | ✅ | $5 offerts | https://console.anthropic.com/ |

**Sans aucune clé**, l'app marche en mode local:
- Vision = heuristique basique (taille image + message)
- Synthèse = règles basées sur tendance
- RAG = fonctionne 100% local avec TF-IDF

**Avec une clé (même une seule)**, tu débloques l'analyse pro.

> Recommandation: Mets `GOOGLE_API_KEY` (gratuit) pour commencer, puis `OPENAI_API_KEY` pour la meilleure qualité.

---

## 📁 Structure Projet

```
.
├── app/
│   ├── main.py                 # FastAPI app + routes
│   ├── config.py               # Settings via .env
│   ├── models/schemas.py       # Pydantic models
│   ├── services/
│   │   ├── pdf_service.py      # Extraction + chunking
│   │   ├── embedding_service.py # OpenAI / ST / TF-IDF
│   │   ├── vector_store.py     # ChromaDB wrapper
│   │   ├── vision_service.py   # GPT-4V / Claude / Gemini / local
│   │   ├── rag_service.py      # Ingest + search
│   │   └── analysis_service.py # Orchestration finale
│   ├── utils/helpers.py
│   ├── templates/index.html    # Frontend UI (Tailwind)
│   └── static/
│       ├── css/style.css
│       └── js/app.js
├── data/
│   ├── pdfs/                   # PDFs uploadés
│   ├── chroma_db/              # Base vectorielle persistante
│   └── temp/                   # Images temporaires
├── Dockerfile                  # Pour Render/HF/Railway
├── requirements.txt
├── .env.example
├── app.py                      # Entry point HF Spaces
├── run.py                      # Entry point local
├── render.yaml                 # Config Render
└── Procfile                    # Config Heroku/Railway
```

---

## 🎨 Interface Web

- **Left**: Base de connaissances (stats docs/chunks, mode embedding, status LLM, upload PDF drag&drop)
- **Right**: Upload graphique drag&drop + preview + analyse + résultats en onglets:
  - Analyse (technique + méthodologie RAG + reco)
  - Prédiction (texte + timeframe + risques)
  - Niveaux Clés (supports, résistances, entrée, SL, TP)
  - Contexte Cours (chunks RAG avec score)
  - Détails Vision (tendance, confiance, patterns, indicateurs)

Design sombre pro inspiré TradingView + Linear.

---

## 🧪 API Endpoints

- `GET /` → UI
- `GET /api/health` → status
- `GET /api/knowledge/status` → stats base
- `POST /api/upload-pdfs` (multipart `files`) → ingestion
- `POST /api/analyze` (multipart `file` image + `top_k`) → analyse complète
- `DELETE /api/knowledge/clear` → wipe base
- `GET /docs` → Swagger auto

Exemple curl:

```bash
curl -X POST http://localhost:8000/api/upload-pdfs -F "files=@cours_trading.pdf"
curl -X POST http://localhost:8000/api/analyze -F "file=@graph.png" -F "top_k=5"
```

---

## 💡 Tips pour de meilleurs résultats

1. **PDFs**: Plus ils sont structurés (un chapitre = un pattern), mieux le chunking marche. Évite les PDFs scannés (images) sans OCR.
2. **Graphiques**: Capture nette, bougies visibles, timeframe lisible. TradingView en mode clair/sombre marche.
3. **Prompt RAG**: Le système enrichit auto la requête avec "analyse technique trading" + description vision.
4. **Sans PDFs**: Ça marche quand même, mais la section "Méthodologie" dira "pas de contexte cours". Upload au moins 1 PDF pour débloquer le vrai RAG.

---

## ⚠️ Disclaimer

Outil éducatif uniquement. Pas un conseil financier. Toujours confirmer avec ton propre plan de trading, risk management, et timeframe supérieur. Le mode local a une confiance réduite.

---

## 🛠️ Stack

- Backend: FastAPI, Uvicorn, Jinja2
- PDF: pdfplumber, PyPDF2
- Vector DB: ChromaDB
- Embeddings: OpenAI / sentence-transformers / sklearn TF-IDF
- Vision LLM: OpenAI GPT-4o-mini Vision, Anthropic Claude 3.5 Sonnet, Google Gemini 1.5 Flash
- Frontend: Tailwind CDN, Vanilla JS, FontAwesome
- Deploy: Docker, Render, HF Spaces, Railway

---

## 📝 TODO / Améliorations possibles

- [ ] OCR pour PDFs scannés (tesseract)
- [ ] Auth + multi-user
- [ ] Historique analyses
- [ ] Export PDF rapport
- [ ] WebSocket streaming analyse
- [ ] Fine-tuning embedding sur vocab trading FR

---

## 🔥 HLZ Complet — Spécialisation

Ce projet supporte maintenant les **styles de trading** dont **HLZ Complet** :

- **HLZ Complet** (High Low ZigZag) : Structure HH/HL, BOS, CHOCH, Order Blocks, FVG, Liquidités, Premium/Discount
- SMC, ICT, Price Action, Elliott, Général

**Comment l'utiliser pour HLZ :**

1. Découpe ton cours HLZ en 8-10 PDFs thématiques :
   ```
   01_HLZ_Structure.pdf, 02_HLZ_BOS.pdf, 03_HLZ_CHOCH.pdf, 04_HLZ_OB.pdf, 
   05_HLZ_FVG.pdf, 06_HLZ_Liquidites.pdf, 07_HLZ_Premium_Discount.pdf, 08_HLZ_Checklist.pdf
   ```
   Voir guide complet dans `docs/HLZ_GUIDE.md`

2. Dans l'UI, sélectionne style **HLZ Complet 🔥**

3. Upload tous les PDFs → Indexation → Upload graphique → Analyse HLZ avec vocabulaire BOS/CHOCH/OB/FVG

Le RAG va citer exactement tes règles HLZ dans "Méthodologie (RAG)".

## 🔀 Repo séparé — Important

Si tu as cloné ce projet depuis `andrianantenainasambatrarj-glitch/chatbot` branche `arena/...`, ta branche `main` (ancien chatbot) est intacte.

Pour créer un repo propre pour le trading :

1. Crée nouveau repo vide sur GitHub : https://github.com/new → `trading-hlz-ai`
2. Puis :
```bash
git clone https://github.com/andrianantenainasambatrarj-glitch/trading-hlz-ai.git
cd trading-hlz-ai
git remote add old https://github.com/andrianantenainasambatrarj-glitch/chatbot.git
git fetch old
git checkout old/arena/01a09f1f-chatbot -- .
git add -A && git commit -m "feat: HLZ AI initial" && git push origin main
```

Ou utilise `scripts/create_new_repo.sh` fourni. Voir `MIGRATE_TO_NEW_REPO.md`.

---

**Créé pour toi — prêt à deploy gratuit sans PC puissant 🚀**

Si tu bloques sur le deploy, ouvre une issue ou demande ici.
