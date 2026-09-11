# Déploiement sur Render

> **Vous cherchez la version 100 % gratuite ?** Voir
> [`DEPLOIEMENT-GRATUIT.md`](./DEPLOIEMENT-GRATUIT.md) (plan Free Render +
> base PostgreSQL Neon gratuite). Le guide ci-dessous correspond à la version
> payante avec disque persistant (serveur qui ne dort jamais).

Ce guide déploie l'application sur [Render](https://render.com) en deux services :

| Service | Type | URL prévue | Coût |
|---|---|---|---|
| `chatbot-vocal-backend` | API Docker (Vosk + Whisper, WebSockets) | `https://chatbot-vocal-api.onrender.com` | plan **Starter** (~7 $/mois) + disque 1 Go |
| `chatbot-vocal-frontend` | Site statique React | `https://chatbot-vocal-app.onrender.com` | **gratuit**, HTTPS compris |

## Quelles fonctionnalités sont disponibles ?

Les modèles sont **pré-téléchargés dans l'image Docker**, ils ne dépendent
pas de votre machine :

- **Transcription Vosk** (français + anglais) : ✅
- **Mode en direct** (WebSocket `/ws/transcribe`) : ✅
- **Commandes vocales** (WebSocket `/ws/commands`) : ✅
- **Whisper** (modèle `tiny` préchargé, multilingue) : ✅ ; les modèles `base`/`small` s'obtiennent par argument de build Docker sur une instance d'au moins 1 Go de RAM
- Exports Word / PDF / TXT / SRT, analyse, chat, partage, e-mail : ✅
- Analyse LLM et envoi SMTP : optionnels (variables d'environnement)

Le microphone du navigateur impose le **HTTPS** : le sous-domaine
`*.onrender.com` fourni par Render est déjà en HTTPS, aucune démarche
supplémentaire.

## Étapes

### 1. Pré-requis

- Le code est poussé sur GitHub (branche `arena/01a08aa8-chatbot`, ou
  `main` après fusion de la pull request).
- Un compte Render gratuit (connexion avec GitHub possible).

### 2. Créer le blueprint

1. Dans Render : **New → Blueprint**.
2. Sélectionnez le dépôt `chatbot`. Render lit automatiquement le fichier
   `render.yaml` à la racine et propose les deux services.
3. Il demande la valeur de **`ADMIN_EMAILS`** : saisissez l'adresse e-mail
   avec laquelle vous allez créer votre compte (elle obtiendra le rôle
   administrateur au premier login). Laissez vide si vous ne voulez pas
   d'admin pour l'instant.
4. Cliquez **Apply**.

La première construction dure **10 à 20 minutes** : elle installe ffmpeg,
télécharge les modèles Vosk (fr + en, ~80 Mo) et pré-charge le modèle
Whisper `tiny` (~75 Mo). Les déploiements suivants sont plus rapides
(les couches Docker sont en cache).

### 3. Vérifier

- Backend : ouvrez `https://chatbot-vocal-api.onrender.com/health`,
  vous devez obtenir `{"status": "ok", ...}`.
- Frontend : ouvrez `https://chatbot-vocal-app.onrender.com`,
  inscrivez-vous, puis testez l'enregistrement, le **mode en direct** et
  les **commandes vocales** (autorisez le micro dans le navigateur).

### 4. Mises à jour

À chaque `git push`, Render redéploie automatiquement la branche
configurée. Si vous fusionnez la pull request vers `main`, modifiez la
ligne `branch:` du fichier `render.yaml` (ou changez la branche dans les
réglages des deux services sur Render).

## Réglages utiles

### Whisper : précision vs mémoire vive

L'image embarque par défaut le modèle **`tiny`**, sûr même en 512 Mo de
RAM. Pour gagner en précision avec **`base`** (~1 Go de RAM nécessaire) ou
**`small`** (~2 Go) :

1. passez sur un plan **Standard** (2 Go de RAM) ;
2. reconstruisez l'image avec l'argument de build `WHISPER_MODEL_SIZE=base`
   (ou `small`) et fixez la variable d'environnement du même nom ;
3. relancez « Clear build cache & deploy ».

Le modèle utilisé doit correspondre à celui pré-téléchargé : toute
modification de `WHISPER_MODEL_SIZE` nécessite une reconstruction de
l'image.

### Persistance des données

Le disque monté sur `/app/data` contient la base SQLite, les fichiers
audio envoyés et les documents générés. **Sans disque, tout est effacé à
chaque redéploiement.** Le disque est une option payante (~0,25 $/Go/mois)
et impose un service payant (Starter minimum).

### Option 100 % gratuite (démonstration)

Vous pouvez passer le backend en plan **Free** et supprimer le bloc
`disk` du `render.yaml` : l'application fonctionne, mais :

- le serveur s'endort après 15 min d'inactivité (premier chargement
  suivant lent, ~30-60 s de réveil) ;
- les comptes et transcriptions sont perdus à chaque redéploiement ;
- Whisper `tiny` tient en 512 Mo ; les modèles plus gros redémarrent le conteneur (Vosk reste
  parfaitement utilisable dans tous les cas).

### Analyse par LLM (résumés de meilleure qualité)

Dans les variables du backend : `LLM_API_KEY`, `LLM_BASE_URL`,
`LLM_MODEL` (compatible OpenAI, y compris un serveur Ollama exposé
publiquement). Sans cela, l'analyse extractive hors-ligne prend le relais.

### Envoi d'e-mails

Renseignez `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
`SMTP_FROM` (par exemple avec un compte SendGrid, Mailjet, Brevo…).

## Dépannage

- **Le micro ne démarre pas** : vérifiez que l'URL est bien en `https://`
  et que le navigateur a l'autorisation (icône à gauche de la barre
  d'adresse).
- **Le mode en direct renvoie une erreur** : consultez les journaux du
  backend sur Render (onglet **Logs**). Un message « modèle Vosk
  introuvable » indique une construction incomplète : relancez un
  déploiement sans cache.
- **Le frontend pointe vers la mauvaise URL** : la variable
  `REACT_APP_API_URL` est gravée au moment du *build* du site statique ;
  si vous renommez les services, mettez-la à jour et redéployez le
  frontend.
- **CORS refusé** : `CORS_ORIGINS` doit valoir exactement l'URL du
  frontend (déjà réglé par le blueprint).

## Construction locale de l'image complète (facultatif)

Pour tester exactement la même image que Render sur votre machine :

```bash
docker build -t chatbot-vocal --build-arg INSTALL_WHISPER=1 .
docker run --rm -p 5001:5001 -e PORT=5001 chatbot-vocal
```

Le `docker-compose.yml` du dépôt construit une image **légère sans
Whisper** pour le développement quotidien.
