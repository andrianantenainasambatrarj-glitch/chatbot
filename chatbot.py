import sys
import os
from flask import Flask, request, jsonify
from docx import Document
from tempfile import NamedTemporaryFile
import wave
import json
from flask_cors import CORS
from vosk import Model, KaldiRecognizer  # Import Vosk
import pydub  # Pour convertir l'audio si besoin

# Initialiser Flask
app = Flask(__name__, static_folder='static')
CORS(app)
print("Flask initialisé")

# Créer le dossier static s'il n'existe pas
if not os.path.exists(app.static_folder):
    os.makedirs(app.static_folder)
    print(f"Dossier static créé : {app.static_folder}")

# Chemin du modèle Vosk (ajuste selon où tu l'as mis)
MODEL_PATH = "models/vosk-model-small-fr-0.22"  # Exemple : dossier 'models/vosk-model-fr' dans ton projet
model = Model(MODEL_PATH)
print(f"Modèle Vosk chargé depuis {MODEL_PATH}")

# Chemin pour sauvegarder l'historique
HISTORY_FILE = os.path.join(app.static_folder, 'transcription_history.json')

# Charger l'historique existant
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# Sauvegarder l'historique
def save_history(history):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

# Fonction pour vérifier et convertir le format WAV en PCM compatible Vosk (mono, 16-bit, 16000Hz)
def prepare_wav_for_vosk(file_path):
    try:
        audio = pydub.AudioSegment.from_wav(file_path)
        audio = audio.set_channels(1)  # Mono
        audio = audio.set_frame_rate(16000)  # 16000 Hz
        audio = audio.set_sample_width(2)  # 16-bit
        converted_path = file_path.replace(".wav", "_converted.wav")
        audio.export(converted_path, format="wav")
        print(f"Audio converti : {converted_path}")
        return converted_path
    except Exception as e:
        print(f"Erreur conversion audio : {e}")
        return file_path  # Retourne l'original si échec

# Fonction pour traiter l'audio et générer un document Word (avec Vosk)
def process_audio(audio_file):
    print("Traitement de l'audio avec Vosk...")
    try:
        # Sauvegarder le fichier audio temporairement
        with NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            audio_file.save(temp_audio.name)
            print(f"Fichier audio temporaire sauvegardé : {temp_audio.name}")

        # Préparer l'audio pour Vosk (conversion si besoin)
        audio_path = prepare_wav_for_vosk(temp_audio.name)

        # Reconnaissance vocale avec Vosk
        recognizer = KaldiRecognizer(model, 16000)  # Sample rate 16000 Hz
        with open(audio_path, "rb") as wf:
            while True:
                data = wf.read(4000)
                if len(data) == 0:
                    break
                recognizer.AcceptWaveform(data)
        result = json.loads(recognizer.FinalResult())
        text = result.get("text", "")
        print(f"Texte transcrit : {text}")

        if not text:
            raise ValueError("Aucun texte transcrit (audio vide ou non compris)")

        # Générer un document Word dans static
        doc = Document()
        doc.add_heading("Transcription Vocale", level=0)
        doc.add_paragraph(text)
        output_path = os.path.join(app.static_folder, "transcription.docx")
        doc.save(output_path)
        print(f"Document généré : {output_path}")

        # Mettre à jour l'historique
        history = load_history()
        history.append({"text": text, "timestamp": str(os.path.getmtime(output_path)), "file": "transcription.docx"})
        save_history(history)

        return {"text": text, "status": f"Document généré : {output_path}"}
    except Exception as e:
        print(f"Erreur inattendue : {str(e)}")
        return {"text": "", "status": f"Erreur : {str(e)}"}
    finally:
        # Supprimer les fichiers temporaires
        if os.path.exists(temp_audio.name):
            os.unlink(temp_audio.name)
            print(f"Fichier temporaire {temp_audio.name} supprimé")
        if 'audio_path' in locals() and os.path.exists(audio_path) and audio_path != temp_audio.name:
            os.unlink(audio_path)
            print(f"Fichier converti {audio_path} supprimé")

# Route pour recevoir une requête audio
@app.route('/speak', methods=['POST'])
def speak():
    print("Requête reçue sur /speak")
    if 'audio' not in request.files:
        return jsonify({"status": "Aucun fichier audio reçu"})
    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({"status": "Aucun fichier audio sélectionné"})
    if audio_file and audio_file.filename.endswith('.wav'):
        result = process_audio(audio_file)
        return jsonify(result)
    return jsonify({"status": "Erreur : Seuls les fichiers WAV sont acceptés"})

# Route principale pour tester (optionnel, sera remplacé par React)
@app.route('/')
def home():
    return "Chatbot vocal actif ! Utilisez /speak pour transcrire en document Word."

if __name__ == '__main__':
    print("Démarrage du serveur...")
    app.run(debug=True, port=5001)