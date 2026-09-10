# Intégration continue (GitHub Actions)

La définition de pipeline est fournie dans [`github-actions.yml`](github-actions.yml).

## Activation

Copiez-la dans le dossier des workflows GitHub (opération à effectuer une fois,
avec un compte disposant du droit « workflows ») :

```bash
mkdir -p .github/workflows
cp docs/ci/github-actions.yml .github/workflows/ci.yml
git add .github/workflows/ci.yml
git commit -m "CI : active le pipeline GitHub Actions"
git push
```

## Ce que fait la pipeline

- **Backend** : installe ffmpeg et les dépendances, lance `ruff check .` puis
  `pytest` (le modèle Vosk est mocké, aucun téléchargement n'est nécessaire).
- **Frontend** : `npm ci`, ESLint, tests Jest, build de production.
