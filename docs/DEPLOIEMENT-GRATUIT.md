# Déploiement 100 % gratuit (Render + Neon)

Cette option coûte **0 €** et conserve les comptes/utilisateurs
durablement, malgré l'absence de disque persistant sur le plan gratuit de
Render :

| Brique | Service gratuit | Rôle |
|---|---|---|
| Frontend | **Render**, site statique | HTTPS, micro autorisé |
| Backend | **Render**, conteneur Docker gratuit | API, Vosk, Whisper, WebSockets |
| Base de données | **Neon** (PostgreSQL gratuit) | Comptes et transcriptions |

## Limites connues du gratuit (à connaître avant)

- Le backend **s'endort après 15 min sans utilisation** : le premier
  accès suivant met 30 à 60 s à réveiller le serveur.
- 512 Mo de RAM : Vosk et le mode direct fonctionnent très bien ; le
  modèle Whisper `base` passe en règle général — si une transcription
  Whisper fait redémarrer le service, mettez la variable
  `WHISPER_MODEL_SIZE=tiny` dans les réglages Render (le modèle, plus
  léger, est téléchargé au premier usage).
- Les fichiers audio et documents ne sont pas conservés après un
  redémarrage du conteneur : les exports Word/PDF/TXT sont
  **régénérés automatiquement à la demande** depuis le texte en base ;
  seul l'export SRT peut disparaître après un redémarrage.
- Render annonce 750 minutes de construction par mois (largement
  suffisant : seuls les nouveaux `git push` reconstruisent).

Pour un service qui ne dort jamais et garde tout sur disque, voir en
fin de document l'alternative **Oracle Cloud (VPS toujours gratuit)**.

---

## Étape 1 — Créer la base PostgreSQL sur Neon

1. Inscrivez-vous sur <https://neon.tech> avec GitHub (gratuit, sans
   carte bancaire).
2. Cliquez **New project** :
   - nom : `chatbot-vocal`,
   - région : choisissez la plus proche (Francfort par exemple pour
     l'Europe),
   - Postgres : version par défaut.
3. Une fois créé, Neon affiche une **chaîne de connexion**
   (`Connection string`) qui ressemble à :

   ```
   postgresql://utilisateur:mot-de-passe@ep-xxxx-xxxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```

4. **Copiez cette chaîne** : c'est la variable `DATABASE_URL` à coller
   dans Render à l'étape suivante.

Les tables sont créées automatiquement au premier démarrage du backend
(le code gère PostgreSQL nativement).

## Étape 2 — Déployer sur Render

1. Inscrivez-vous sur <https://render.com> avec GitHub.
2. **New → Blueprint**, sélectionnez le dépôt `chatbot`. Render lit le
   fichier `render.yaml` (déjà réglé sur le plan gratuit) et propose les
   deux services.
3. Render demande les valeurs des variables marquées « sync: false » :
   - **`DATABASE_URL`** : collez la chaîne Neon copiée à l'étape 1.
   - **`ADMIN_EMAILS`** : votre adresse e-mail admin (cf. étape 3).
4. Cliquez **Apply**. La première construction dure 10 à 20 min
   (téléchargement de ffmpeg, des modèles Vosk fr/en et de Whisper).
5. À la fin, deux URL apparaissent :
   - `https://chatbot-vocal-frontend.onrender.com` (le site)
   - `https://chatbot-vocal-backend.onrender.com` (l'API)

Vérification de l'API (le tout premier appel peut prendre ~1 min, le
temps du réveil) :

```
https://chatbot-vocal-backend.onrender.com/health
```

→ doit répondre `{"status": "ok", "database": "ok", ...}`. Si
`database` n'est pas `ok`, la variable `DATABASE_URL` est incorrecte.

## Étape 3 — Créer le compte administrateur

Le rôle admin est accordé **automatiquement à l'inscription** si
l'e-mail figure dans la variable `ADMIN_EMAILS`.

1. Dans Render → service **chatbot-vocal-backend** → onglet
   **Environment**, vérifiez `ADMIN_EMAILS=votre@email.com` (plusieurs
   e-mails séparés par des virgules sont possibles).
2. Ouvrez le site, cliquez sur **S'inscrire**, renseignez cet e-mail et
   un mot de passe d'au moins 8 caractères.
3. Vous êtes connecté **directement administrateur** : la section
   « Administration » du tableau de bord liste les utilisateurs.

Si le compte existait déjà avant le réglage, le rôle est aussi accordé
à la prochaine connexion (il suffit de se déconnecter/reconnecter).

---

## Créer l'admin en local (sur votre PC Windows, avant déploiement)

C'est la même logique, avec la variable d'environnement :

**PowerShell** :

```powershell
cd C:\chemin\vers\chatbot
$env:ADMIN_EMAILS="votre@email.com"
python chatbot.py
```

**Invite de commandes (cmd)** :

```bat
cd C:\chemin\vers\chatbot
set ADMIN_EMAILS=votre@email.com
python chatbot.py
```

Puis, sur `http://localhost:3000`, inscrivez-vous avec cet e-mail.
Le serveur doit avoir été (re)démarré **après** avoir posé la variable.

Si le compte existe déjà, mettez la variable puis
déconnectez-vous/reconnectez-vous : la promotion se fait à la connexion.

---

## Alternative : un vrai serveur toujours gratuit (Oracle Cloud)

Si le serveur qui s'endort vous gêne, **Oracle Cloud Free Tier** propose
un VPS gratuit **pour toujours** (machine ARM jusqu'à 4 coeurs / 24 Go
de RAM selon les régions, ou petit x86) avec carte bancaire pour
vérification (jamais débitée sur le niveau « Always Free ») :

1. Créez un compte sur <https://www.oracle.com/cloud/free/>.
2. Créez une instance **Compute** (image Ubuntu, forme `VM.Standard.A1`
   ou toujours-gratuite).
3. Connectez-vous en SSH, installez Docker et lancez le dépôt avec le
   `docker-compose.yml` du projet (Whisper s'active en passant
   `INSTALL_WHISPER: "1"` dans les arguments de construction).
4. Pour le HTTPS (obligatoire pour le micro), prenez un domaine
   gratuit ou non et ajoutez un reverse-proxy Caddy/Traefik qui obtient
   un certificat Let's Encrypt automatiquement.

Cette solution garde les données sur le disque de la machine et ne
s'endort jamais ; elle demande environ 30 à 45 min de configuration.
Dites-le-moi si vous choisissez cette voie, je fournis le pas à pas
complet.

## Dépannage

- **`database: error` sur /health** : relisez la chaîne Neon
  (`?sslmode=require` présent, pas d'espace, mot de passe non modifié).
- **502/redémarrage sur une grosse transcription Whisper** : passez
  `WHISPER_MODEL_SIZE=tiny` puis redéployez, ou utilisez Vosk.
- **Le micro refuse de démarrer** : vérifiez que l'URL du site commence
  bien par `https://` et autorisez le micro dans le navigateur.
- **« Application failed to bind to port »** : assurez-vous que
  `Dockerfile` utilise bien `${PORT}` (c'est le cas sur la branche).
- **Déploiements automatiques** : chaque `git push` sur la branche
  configurée redéploie les deux services.
