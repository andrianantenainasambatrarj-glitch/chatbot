# Comment créer un nouveau repo pour Trading HLZ AI (sans toucher ton chatbot)

Tu as raison, j'ai travaillé sur la branche `arena/01a09f1f-chatbot` de ton repo `chatbot` existant. **Bonne nouvelle : ta branche `main` est intacte**, donc ton chatbot déjà déployé n'est pas cassé. Mais tu veux un repo séparé propre pour le projet trading — voici 2 méthodes.

## ✅ Vérification : ton chatbot actuel est safe

- `main` = ton ancien chatbot (inchangé)
- `arena/01a09f1f-chatbot` = nouveau projet trading (ce que j'ai créé)

Si ton déploiement pointe sur `main`, il n'a pas bougé. Vérifie sur Render/Vercel : branche déployée = `main` ?

## 🚀 Méthode 1 : Créer nouveau repo via GitHub Web (2 min, recommandé)

1. Va sur https://github.com/new
2. **Repository name** : `trading-hlz-ai` (ou `tradinggraph-hlz`)
3. Description : `IA Trading HLZ Complet - RAG + Vision LLM`
4. Public, **ne coche PAS** "Add README" (on a déjà)
5. Create repository

6. Ensuite, sur ton PC (ou ici dans Arena, je peux le faire) :

```bash
# Clone le nouveau repo vide
git clone https://github.com/andrianantenainasambatrarj-glitch/trading-hlz-ai.git
cd trading-hlz-ai

# Copie le code depuis la branche arena (méthode 1: via GitHub download)
# Ou méthode 2: ajoute l'ancien repo comme remote temporaire

git remote add old https://github.com/andrianantenainasambatrarj-glitch/chatbot.git
git fetch old
git checkout old/arena/01a09f1f-chatbot -- .

# Ou si tu as déjà le dossier chatbot local:
# cp -r ../chatbot/app ../chatbot/docs ../chatbot/data ../chatbot/*.py ../chatbot/*.md ../chatbot/Dockerfile ../chatbot/requirements.txt ../chatbot/render.yaml ../chatbot/Procfile .

git add -A
git commit -m "feat: initial commit - Trading HLZ AI RAG+Vision"
git push origin main
```

7. Maintenant tu as 2 repos séparés :
   - `chatbot` → ton ancien bot vocal (main intact)
   - `trading-hlz-ai` → nouveau projet trading HLZ

8. Déploie `trading-hlz-ai` sur Render : New Web Service → connecte ce nouveau repo

## 🛠️ Méthode 2 : Script automatique (je te le fournis)

J'ai créé `scripts/create_new_repo.sh` — exécute-le après avoir créé le repo vide sur GitHub.

```bash
chmod +x scripts/create_new_repo.sh
./scripts/create_new_repo.sh https://github.com/andrianantenainasambatrarj-glitch/trading-hlz-ai.git
```

## 🔄 Méthode 3 : Je le fais pour toi depuis Arena (si tu me donnes le nom)

Dis-moi le nom du nouveau repo que tu veux (ex: `trading-hlz-ai`), et si tu as créé le repo vide sur GitHub, je peux pousser directement le code HLZ dedans depuis cette session.

Commande que je vais exécuter :

```bash
git remote add newrepo https://github.com/andrianantenainasambatrarj-glitch/trading-hlz-ai.git
git push newrepo arena/01a09f1f-chatbot:main --force
```

## 📌 Après migration

1. Supprime la branche `arena/01a09f1f-chatbot` de l'ancien repo si tu veux nettoyer :
   ```bash
   git push origin --delete arena/01a09f1f-chatbot
   ```

2. Garde `chatbot` pour ton bot vocal, `trading-hlz-ai` pour HLZ

3. Sur Render, crée 2 services séparés pointant sur chaque repo

---

Besoin que je pousse vers un nouveau repo maintenant ? Donne-moi le nom exact et crée le repo vide sur GitHub, je m'occupe du reste.
