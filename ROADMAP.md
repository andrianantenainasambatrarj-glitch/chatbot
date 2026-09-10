# Analyse du projet « Chatbot Vocal » & Roadmap d'amélioration

> Document d'analyse — date : 2026-09-10
> Objet : état des lieux, bugs à corriger, fonctionnalités à ajouter et chantiers pour rendre le projet professionnel.

---

## 1. Vue d'ensemble du projet

Le projet est une application web de **transcription vocale (speech-to-text) en français** :

- **Backend** : Flask (`chatbot.py`)
  - Reçoit un fichier audio WAV sur la route `POST /speak`
  - Le transcrit avec **Vosk** (modèle `vosk-model-small-fr-0.22`, reconnaissance hors-ligne)
  - Convertit l'audio en mono 16 kHz / 16-bit avec **pydub**
  - Génère un document **Word (.docx)** avec `python-docx`
  - Conserve un historique dans un fichier JSON (`static/transcription_history.json`)
- **Frontend** : React 19 (Create React App) dans `frontend/`
  - Enregistre le micro via `MediaRecorder` (webm), convertit en WAV dans le navigateur (`wav-encoder`)
  - Envoie le WAV au backend, affiche la transcription et le lien de téléchargement
  - Historique en mémoire, mode sombre
- **Autres** : script de téléchargement NLTK (`nltk_data/setup_nltk.py`, non utilisé dans le code)

**Architecture actuelle :**

```
Navigateur (React, port 3000)
   │  POST audio/wav (URL codée en dur : localhost:5001)
   ▼
Flask (port 5001) ──► Vosk (STT) ──► python-docx ──► static/transcription.docx
                   └─► static/transcription_history.json (fichier plat)
```

Il s'agit aujourd'hui davantage d'un **transcripteur vocal** que d'un « chatbot » : il n'y a ni conversation, ni réponse vocale, ni intelligence artificielle dialoguante.

---

## 2. Bugs et problèmes à corriger en priorité (P0)

### Backend (`chatbot.py`)

1. **Bug critique : un seul fichier Word pour toutes les transcriptions.**
   Chaque requête écrase `static/transcription.docx`. Toutes les cartes de l'historique pointent vers le même fichier : télécharger une transcription ancienne renvoie en réalité la **dernière**. → utiliser un nom unique (UUID + date), et une route de téléchargement `/transcriptions/<id>`.

2. **Historique incohérent entre le backend et le frontend.**
   - Le backend écrit un JSON mais **n'expose aucune route** pour le lire ou le supprimer.
   - Le frontend garde l'historique uniquement dans un `useState` : il est **perdu au rechargement**.
   - Le bouton « Effacer l'historique » ne vide que l'état React, jamais le fichier JSON.

3. **Risque de `UnboundLocalError` dans le bloc `finally`.**
   `temp_audio` est défini dans le `try` ; si l'enregistrement du fichier temporaire échoue, le `finally` référence une variable inexistante et lève une seconde exception qui masque la vraie erreur.

4. **Erreurs renvoyées avec un code HTTP 200.**
   Réponse `{"status": "Erreur : ..."}` avec `jsonify()` → le frontend ne peut pas distinguer un succès d'un échec (il se base sur une chaîne contenant « généré »). → renvoyer les bons codes (400, 413, 415, 422, 500).

5. **Sécurité de la configuration.**
   - `app.run(debug=True)` : le débogueur Werkzeug permet l'exécution de code à distance en production.
   - `CORS(app)` grand ouvert : aucune restriction d'origine.
   - Aucune limite de taille de fichier, aucun rate-limiting (risque de déni de service), aucune vérification du contenu réel du fichier (seule l'extension `.wav`, sensible à la casse, est vérifiée).

6. **`requirements.txt` incomplet et non épinglé.**
   Il manque `vosk` et `pydub` (qui sont importés !), tandis que `SpeechRecognition` est déclaré mais inutilisé. Aucune version n'est figée → installations non reproductibles. Il faut aussi documenter la dépendance système **ffmpeg** (requise par pydub).

7. **Le modèle Vosk est absent et introuvable.**
   Le dossier `models/` est dans `.gitignore` (normal, il est lourd), mais aucun script ne le télécharge et le README ne l'explique pas : l'application ne démarre pas après un `git clone` frais. Le modèle est chargé au démarrage (`Model(MODEL_PATH)`) et fait planter l'app silencieusement s'il manque.

8. **`print()` partout au lieu d'un vrai logging** (`logging`), pas de gestion centralisée des erreurs ni de page/réponse d'erreur standardisée.

9. **Accès concurrent non sécurisé au fichier JSON d'historique** (lecture/écriture sans verrou) et écriture non atomique : deux requêtes simultanées peuvent corrompre le fichier.

10. **Nettoyage des fichiers temporaires incomplet** : en cas d'erreur avant la conversion, le fichier converti peut rester ; les documents générés dans `static/` s'accumulent sans politique de rétention.

### Frontend (`App.js`)

11. **Le micro reste parfois actif.**
    Après `mediaRecorder.stop()`, les pistes du flux audio ne sont jamais arrêtées (`stream.getTracks().forEach(t => t.stop())`) : le voyant d'enregistrement du navigateur peut rester allumé.

12. **URLs codées en dur** (`http://localhost:5001/speak` et `…/static/transcription.docx`) : l'application ne fonctionne ni depuis un autre poste, ni en HTTPS, ni déployée. → variable d'environnement `REACT_APP_API_URL` (ou proxy de dev CRA `/api`).

13. **Aucun retour pendant l'enregistrement** : pas de chronomètre, pas de niveau sonore (VU-mètre), pas de bouton pause/reprise, pas d'écoute du dernier enregistrement avant l'envoi.

14. **Pas de gestion fine des erreurs navigateur** : refus de permission micro, navigateur sans `MediaRecorder`, HTTPS obligatoire (`getUserMedia` bloqué en HTTP hors localhost).

15. **Test automatique factice et cassé** : `App.test.js` cherche le texte « learn react » du template CRA, qui n'existe plus → le test échoue systématiquement.

16. **Dépendances résiduelles du template** :
    - `tailwindcss` + `postcss` + `autoprefixer` en devDependencies sans configuration (ni `tailwind.config.js`, ni import `@tailwind`) → Tailwind ne fonctionne pas.
    - `App.css` contient les styles du logo React non utilisé ; `styles.css` et `App.css` coexistent.
    - `logo.svg`, `reportWebVitals` sans cible, `manifest.json` et titres HTML encore « Create React App / React App ».

### Projet / dépôt

17. **Aucun README à la racine** expliquant l'installation (Python, ffmpeg, modèle Vosk, Node), le lancement des deux serveurs, ou l'architecture.
18. **Aucun `.env.example`** alors que `.gitignore` en prévoit un ; aucune configuration par variables d'environnement.
19. **Aucun test backend, aucune pipeline CI, aucun Docker, aucun lint/format** (black/ruff, ESLint/Prettit n'est pas configuré), pas de licence ni de CONTRIBUTING.
20. **NLTK téléchargé mais jamais utilisé** (`punkt`, `stopwords`) : soit retirer, soit exploiter (cf. fonctionnalités de NLP ci-dessous).

---

## 3. Nouvelles fonctionnalités proposées

### 3.1. Cœur du produit — enregistrement & transcription

| # | Fonctionnalité | Intérêt |
|---|----------------|---------|
| F1 | **Transcription en temps réel (streaming)** via WebSocket (Socket.IO / Flask-Sock) avec Vosk en ligne de commande | Effet « dictate » professionnel, texte qui apparaît pendant la parole |
| F2 | **Upload de fichiers audio** (mp3, m4a, ogg, webm, wav…) en plus du micro, avec conversion automatique côté serveur | Traitement de réunions, entretiens, podcasts |
| F3 | **Fichiers longs / traitement asynchrone** : file de tâches (Celery ou RQ + Redis), barre de progression, notification à la fin | Les gros audios ne bloquent pas le serveur ni le navigateur |
| F4 | **Mots horodatés** (`recognizer.Result()` avec timestamps) et export **sous-titres .srt/.vtt** | Réutilisation vidéo, synchro audio/texte |
| F5 | **Choix de la langue / multilingue** (Vosk propose des modèles FR, EN, ES, DE…) avec détection automatique | Audience élargie |
| F6 | **Modèles alternatifs** : modèle Vosk large pour la précision, ou **faster-whisper / Whisper** (meilleure précision, ponctuation native, multilingue), sélectionnable par requête | Qualité professionnelle |
| F7 | **Diarisation des locuteurs** (pyannote-audio) : « Intervenant 1 : … Intervenant 2 : … » | Comptes rendus de réunion |
| F8 | **Post-traitement du texte** : ponctuation & majuscules, correction orthographique (LanguageTool / symspellpy), chiffres et unités | Textes directement exploitables |
| F9 | **Édition manuelle de la transcription** avant export (zone de texte éditable, sauvegarde) | Corriger les erreurs de reconnaissance |
| F10 | **Contrôles d'enregistrement enrichis** : pause/reprise, chronomètre, VU-mètre, annulation, réécoute (lecteur `<audio>`), durée maximale configurable | UX d'un vrai dictaphone |
| F11 | **Exports multiples** : DOCX (avec mise en page, titre, date, métadonnées), TXT, PDF, SRT/VTT, Markade, copie-presse-papiers | Diffusion tous supports |
| F12 | **Nommage intelligent des documents** (date + début du texte ou titre personnalisé), dossier organisé par date | Fin du fichier unique écrasé |

### 3.2. Historique et gestion des transcriptions

| # | Fonctionnalité |
|---|----------------|
| F13 | **API REST complète** : `GET /api/transcriptions`, `GET /api/transcriptions/<id>`, `DELETE`, téléchargement de l'export |
| F14 | **Vraie base de données** (SQLite au minimum, PostgreSQL ensuite) avec un ORM (SQLAlchemy) et migrations (Alembic), au lieu du JSON |
| F15 | Persistance de l'historique **par utilisateur**, avec recherche plein texte, filtres par date/langue, pagination, suppression individuelle ou en lot |
| F16 | **Épingler / renommer / étiqueter (tags)** les transcriptions, dossiers/projets |
| F17 | **Partage par lien** (URL signée à expiration) d'une transcription en lecture seule |
| F18 | **Réécoute audio synchronisée** : surlignage de la phrase pendant la lecture (comme un lecteur de sous-titres) |

### 3.3. Pour mériter le nom de « Chatbot »

| # | Fonctionnalité |
|---|----------------|
| F19 | **Interface conversationnelle** : après la transcription (ou par texte), poser des questions à un LLM sur le contenu |
| F20 | **Résumé automatique** du compte rendu, liste des décisions, actions à faire (action items), mots-clés, sentiments (utilise enfin NLTK, ou un LLM) |
| F21 | **Réponse vocale (Text-to-Speech)** : le chatbot répond à voix haute (synthèse navigateur `SpeechSynthesis` ou serveur e.g. Piper, gTTS) → bougle vocale complète |
| F22 | **Commandes vocales** (« efface », « nouveau paragraphe », « envoie par e-mail »), mode dictée continue |
| F23 | **Intents / FAQ locaux** (entraînement léger, hors-ligne) pour un assistant d'entreprise spécialisé sans envoyer de données dans le cloud |
| F24 | **Traduction** de la transcription dans d'autres langues |

### 3.4. Authentification et utilisateurs

- F25. Inscription / connexion (email+mot de passe avec hash `argon2`/bcrypt, ou OAuth Google/Microsoft) via **Flask-Login** ou JWT
- F26. Sessions, profils, quota d'heures de transcription par utilisateur, rôles (admin / utilisateur)
- F27. Espace « Mes transcriptions » confidentiel ; aujourd'hui tout est public dans `static/` (quiconque devine l'URL télécharge les documents)

### 3.5. Interface & expérience (UI/UX)

- F28. **Design system** cohérent : composants réutilisables (Button, Card, Toast, Modal…), variables CSS, variantes ; terminer la bascule Tailwind ou le retirer
- F29. **Accessibilité** : attributs ARIA, navigation clavier complet, contrastes AA, focus visibles, `prefers-reduced-motion`, annonce des états aux lecteurs d'écran
- F30. **Internationalisation (i18n)** FR/EN de l'interface (i18next / react-i18next)
- F31. **PWA** : installation sur mobile/desktop, mode hors-ligne, micro depuis le mobile (le manifest existe encore sous le nom « React App »)
- F32. **Notifications toast**, états vides illustrés, squelettes de chargement, confirmation avant suppression
- F33. **Tableau de bord** : nombre de transcriptions, minutes traitées, mots/minute, langues utilisées, graphiques
- F34. Raccourcis clavier (espace = enregistrer/arrêter), glisser-déposer un fichier audio
- F35. Pages supplémentaires : À propos, Aide/FAQ, tarifs (si SaaS), page 404, conditions & confidentialité (RGPD)

---

## 4. Chantiers de professionnalisation technique

### 4.1. Qualité de code & tests

- Tests backend **pytest** : conversion audio, transcription avec fichier fixture, routes API, cas d'erreur
- Tests frontend **Jest + Testing Library** réels (enregistrement simulé, affichage, historique)
- Couverture de tests visée (pytest-cov), tests E2E optionnels **Playwright**
- **GitHub Actions** (CI) : lint + tests Python et Node à chaque push, build du frontend
- **pre-commit** : `ruff`/`black`/`isort` (Python), ESLint + Prettier (JS), vérification des secrets (gitleaks), `end-of-file-fixer`
- TypeScript côté frontend (migration progressif CRA → Vite + TS recommandée)
- Structuration backend en paquet : `app/__init__.py` (application factory), `routes/`, `services/`, `models/`, `config.py`, au lieu d'un unique `chatbot.py` de 130 lignes

### 4.2. Configuration, déploiement & DevOps

- **Docker + docker-compose** : image backend (avec ffmpeg), frontend buildé et servi par nginx, volume pour les données, Redis pour les tâches
- Variables d'environnement via un fichier `.env.example` complété (`FLASK_ENV`, `SECRET_KEY`, `MODEL_PATH`, `MAX_CONTENT_LENGTH`, `CORS_ORIGINS`, `DATABASE_URL`, `UPLOAD_DIR`)
- Servir le build React **par Flask** (ou un reverse proxy) → un seul domaine, plus aucun `localhost:5001` codé en dur
- **Makefile** ou scripts : `make setup`, `make backend`, `make frontend`, `make test`
- Utiliser un serveur WSGI (**gunicorn** / waitress) au lieu de `app.run()` ; ne jamais activer le debug en production
- Déploiement documenté (Render, Fly.io, Railway, VPS + nginx, Kubernetes plus tard) ; stockage des fichiers sur disque persistant ou **S3-compatible** (MinIO) avec URLs présignées
- **Migrations de BDD** (Alembic), seeds, sauvegardes

### 4.3. Sécurité

- Authentification des utilisateurs + autorisation sur chaque ressource
- `MAX_CONTENT_LENGTH` et limitation de durée audio ; **Flask-Limiter** (rate limit par IP/utilisateur)
- Validation réelle des fichiers : magic bytes (`python-magic`), liste blanche de types, antivirus optionnel
- CORS restreint aux origines connues ; **Flask-Talisman** (en-têtes de sécurité, CSP) ; HTTPS obligatoire
- `SECRET_KEY` fort via variable d'environnement ; gestion des dépendances vulnérables (`pip-audit`, `npm audit`) dans la CI
- Journalisation sans données personnelles ; **conformité RGPD** : consentement micro, conservation limitée des audios, droit à l'oubli, mention de traitement des données
- Sortie des documents du dossier `static/` (public) : downloads authentifiés, jamais de noms devinables

### 4.4. Observabilité

- **Logging structuré** (niveaux, IDs de corrélation, rotation de fichiers) en remplacement des `print`
- Page `GET /health` et `/ready` (modèle chargé, BDD OK, disque OK) pour l'orchestration
- Monitoring d'erreurs **Sentry**, métriques (Prometheus) : latence, taux d'échec, minutes transcrites
- Mesure des performances web (reportWebVitals déjà présent, branché sur une vraie cible)

### 4.5. Documentation

- **README racine** : présentation, captures d'écran/démo, prérequis (Python 3.x, ffmpeg, Node), commande de téléchargement du modèle Vosk, lancement, tests, Docker
- Documentation API (Swagger/OpenAPI avec **flask-smorest** ou Flasgger)
- `CONTRIBUTING.md`, `LICENSE`, Architecture Decision Records, feuille de version et **CHANGELOG** (Keep a Changelog + versionnement sémantique)

---

## 5. Roadmap recommandée (par priorité et effort)

### Sprint 1 — Stabilisation et correction ✅ LIVRÉ (2026-09-10) 🔴
1. Fichiers Word à noms uniques + route de téléchargement ; fin de l'écrasement (bug n°1)
2. Bons codes HTTP et gestions d'erreur ; variable `temp_audio` du `finally` (n°3, n°4)
3. `requirements.txt` complet et épinglé + script de setup (ffmpeg, téléchargement du modèle Vosk)
4. Externaliser les URLs (`REACT_APP_API_URL` / proxy) et arrêter les pistes micro (n°11, n°12)
5. `debug=False` par défaut, config par variables d'env, CORS restreint, limite de taille
6. README racine avec instructions complètes ; retirer NLTK/SpeechRecognition/Tailwind inutilisés OU les mettre en œuvre
7. Corriger/remplacer le test React cassé

### Sprint 2 — Expérience et données ✅ LIVRÉ (2026-09-10) 🟠
8. ✅ Base SQLite + SQLAlchemy, API REST complète synchronisée avec le frontend (F13, F14)
9. ✅ Chronomètre, pause/reprise, réécoute avant envoi, upload multi-formats MP3/M4A/OGG... (F2, F10)
10. ✅ Exports DOCX/PDF/TXT/SRT (mots horodatés) + édition du texte avant export (F9, F11, F12)
11. ✅ Logging structuré, /health (base + modèle), validation des formats et rate limiting (Flask-Limiter)
12. ✅ Docker + docker-compose (backend ffmpeg/gunicorn, frontend nginx relayant l'API) et CI GitHub Actions (pytest + Jest + build)
    - Restent pour plus tard : lint/format automatisés (ruff/Prettier) dans la CI

### Sprint 3 — Fonctionnalités avancées ✅ LIVRÉ (2026-09-10) 🟡
13. ✅ Transcription temps réel par **WebSocket** (flux PCM 16 kHz, partiels affichés en direct, sauvegarde à l'arrêt) et **tâches asynchrones** pour les gros fichiers avec progression (`/api/jobs`, exécuteur en threads remplaçable par Celery/Redis) (F1, F3)
14. ✅ **Authentification JWT** (inscription/connexion, hash werkzeug) et **transcriptions privées** par utilisateur, isolation complète des ressources (F25–F27 partiel : OAuth et quotas restent à faire)
15. ✅ **Multilingue et multi-moteurs** : abstraction `engines/`, Vosk avec modèles par langue (`VOSK_MODELS`), moteur **faster-whisper** optionnel (`requirements-whisper.txt`), endpoint `/api/engines` reflétant la disponibilité (F5, F6)
16. 🔶 Mots horodatés → **SRT** déjà livré au sprint 2 ; restent la ponctuation/correction automatiques (F8) et les lexiques métier
17. ✅ **PWA** (service worker, manifest, mode hors-ligne), **i18n FR/EN** (i18next), accessibilité (skip-link, ARIA live, focus visibles, rôles tab) ; un vrai design system de composants reste souhaitable (F28–F32 partiel)
    - Backend découpé en modules + **35 tests pytest** ; worker **gevent-websocket** pour gunicorn/Docker ; proxy WebSocket dans nginx

### Sprint 4 — Différenciation (« chatbot » assumé) ✅ LIVRÉ (2026-09-10) 🟢
18. ✅ **Analyses NLP** (`nlp/`) : résumé extractif, actions à faire, mots-clés, tonalité
    100 % hors-ligne, avec bascule optionnelle sur un **LLM compatible OpenAI/Ollama**
    (`LLM_API_KEY`) ; **chat questions/réponses** sur la transcription (LLM ou repli
    par similarité) (F19, F20)
19. ✅ **Synthèse vocale** via la Web Speech API (lecture du texte et des réponses) et
    **commandes vocales** via WebSocket `/ws/commands` (FR/EN, 15 commandes :
    enregistrement, mode sombre, tableau de bord, téléchargements, langues, déconnexion…) (F21, F22)
20. ✅ **Diarisation** par silences (Intervenant 1/2, option `diarize`) ; **partage par
    lien** signé expirable avec routes publiques `/api/shared/<token>` ; **e-mail SMTP**
    avec DOCX/PDF joints et **webhooks** (n8n/Zapier/Notion) ; **tableau de bord**
    (activité 30 jours, minutes, moteurs, langues) (F7, F17, F33)
21. ✅ Quotas mensuels par utilisateur (402 quand dépassés), **espace admin** (rôles,
    quotas, totaux), **métriques Prometheus** `/metrics`, migration automatique SQLite ;
    **facturation Stripe expressément exclue du périmètre**

Reste disponible pour la suite (au choix) : OAuth Google/Microsoft, pyannote.audio pour
une diarisation par empreinte vocale, Celery/Redis pour la montée en charge multi-processus,
intégrations natives Drive/Notion/OAuth, design system de composants et E2E Playwright.

---

## 6. Idées bonus / innovation

- **Mode réunion** : enregistrement multi-microphones, séparation des voix, résumé envoyé automatiquement par e-mail aux participants
- **Vocabulaire métier** : charger des lexiques personnalisés (médecine, droit, finance) pour améliorer Vosk via sa grammaire/`setWords`
- **Dictée médicale/juridique** avec modèles spécialisés et modèles Word prédéfinis (comptes rendus types)
- **Sous-titrage vidéo en direct dans le navigateur** (WebVTS en sortie, overlay)
- **Plugin navigateur / extension** et bot de réunion (Zoom, Teams, Google Meet) qui transcrit en direct
- **API publique avec clés API** et quota pour développeurs (modèle SaaS B2B)
- **Marque blanche / multi-tenant** pour entreprises
- Fonctionnement **100 % hors-ligne** (Vosk + TTS Piper + petit LLM local) : argument fort pour les données sensibles (santé, juridique)
- Gamification de la productivité : streak de dictée, statistiques de vocabulaire
- Version mobile (React Native / PWA installable) avec widgets « dicter une note »

---

## 7. Synthèse

**Forces du projet actuel :** concept clair et utile, stack simple et légère, reconnaissance 100 % locale (confidentialité), interface déjà agréable avec mode sombre, transcription + export Word fonctionnels en bout de chaîne.

**Freins principaux vers un niveau « professionnel » :** un bug majeur d'écrasement des documents, une absence de persistance réelle et d'API d'historique, une configuration uniquement locale (URLs en dur, debug, CORS ouvert), des dépendances et du modèle non reproductibles après clonage, et zéro test/CI/Docker/documentation.

Les deux plus gros leviers de valeur à court terme : **fiabiliser le cycle transcription → stockage → téléchargement** (sprints 1) puis **passer à une vraie API persistante avec une UX d'enregistrement enrichie** (sprint 2). Les leviers de différenciation à moyen terme sont le **temps réel**, le **multilingue/Whisper**, la **diarisation** et les **fonctions conversationnelles (résumés, chatbot, TTS)** qui justifieraient pleinement le nom du projet.
