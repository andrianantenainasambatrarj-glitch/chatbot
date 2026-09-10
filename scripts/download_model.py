"""Télécharge et installe le modèle Vosk français.

Usage :
    python scripts/download_model.py
    python scripts/download_model.py --model vosk-model-fr-0.22 --models-dir models

Le petit modèle (~40 Mo) est suffisant pour démarrer ; le grand modèle
(vosk-model-fr-0.22, ~1,8 Go) offre une meilleure précision.
"""

import argparse
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

MODELS = {
    # Français
    "vosk-model-small-fr-0.22": "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip",
    "vosk-model-fr-0.22": "https://alphacephei.com/vosk/models/vosk-model-fr-0.22.zip",
    # Autres langues (petits modèles)
    "vosk-model-small-en-us-0.15": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
    "vosk-model-small-es-0.42": "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip",
    "vosk-model-small-de-0.15": "https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip",
    "vosk-model-small-it-0.22": "https://alphacephei.com/vosk/models/vosk-model-small-it-0.22.zip",
    "vosk-model-small-pt-0.3": "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip",
    "vosk-model-small-nl-0.22": "https://alphacephei.com/vosk/models/vosk-model-small-nl-0.22.zip",
}

# Après avoir téléchargé un modèle d'une autre langue, déclarez-le dans VOSK_MODELS
# (variable d'environnement, JSON langue -> chemin), par exemple :
#   VOSK_MODELS={"fr": "models/vosk-model-small-fr-0.22",
#                "en": "models/vosk-model-small-en-us-0.15"}


def _report_progress(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        percent = min(100, downloaded * 100 // total_size)
        sys.stdout.write(f"\rTéléchargement : {percent}%")
        sys.stdout.flush()


def download_model(model_name, models_dir):
    if model_name not in MODELS:
        raise SystemExit(
            f"Modèle inconnu : {model_name}. Choix possibles : {', '.join(MODELS)}"
        )

    target = Path(models_dir) / model_name
    if target.exists():
        print(f"Le modèle existe déjà : {target}")
        return

    url = MODELS[model_name]
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    archive_path = models_dir / f"{model_name}.zip"

    print(f"Téléchargement de {model_name} depuis {url}")
    urllib.request.urlretrieve(url, archive_path, reporthook=_report_progress)
    print("\nDécompression...")
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(models_dir)
    archive_path.unlink()

    extracted_root = models_dir / model_name
    if not extracted_root.exists():
        # L'archive peut contenir un dossier au nom légèrement différent
        candidates = [p for p in models_dir.iterdir() if p.is_dir() and model_name in p.name]
        if candidates:
            shutil.move(str(candidates[0]), str(extracted_root))

    print(f"Modèle installé dans : {target.resolve()}")
    print("Vous pouvez lancer le backend : python chatbot.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Télécharge un modèle Vosk.")
    parser.add_argument(
        "--model",
        default="vosk-model-small-fr-0.22",
        help="Nom du modèle (voir le dictionnaire MODELS dans le script)",
    )
    parser.add_argument("--models-dir", default="models", help="Dossier de destination")
    args = parser.parse_args()
    download_model(args.model, args.models_dir)
