# Chatbot Vocal — Frontend

Interface React (Create React App) : enregistrement du microphone, conversion en
WAV dans le navigateur, envoi au backend Flask et téléchargement du document Word.

## Scripts

```bash
npm install        # installer les dépendances
npm start          # serveur de développement sur http://localhost:3000
npm test           # lancer les tests (--watchAll=false pour un passage unique)
npm run build      # build de production dans build/
```

## Configuration

Les requêtes API utilisent des chemins relatifs (`/api/...`).

- En **développement**, la clé `proxy` du `package.json` les relaie vers
  `http://localhost:5001`.
- En **production**, créez un fichier `.env.local` avec l'URL du backend :
  `REACT_APP_API_URL=https://votre-backend.exemple.com` (voir `.env.example`).

La documentation complète (installation de ffmpeg, du modèle Vosk, API) se trouve
dans le [README racine](../README.md).
