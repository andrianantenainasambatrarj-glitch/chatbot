"""Backend Flask du Chatbot Vocal.

Fonctionnalités :
  - transcription de nombreux formats audio (WAV, MP3, M4A, OGG, WEBM...) via Vosk
  - persistance dans SQLite (SQLAlchemy)
  - exports DOCX, PDF, TXT et SRT (mots horodatés)
  - édition de la transcription avant export

Routes principales :
  GET    /health
  POST   /api/transcribe
  GET    /api/transcriptions
  GET    /api/transcriptions/<id>
  PATCH  /api/transcriptions/<id>
  DELETE /api/transcriptions/<id>
  DELETE /api/transcriptions
  GET    /api/transcriptions/<id>/export/<docx|pdf|txt|srt>
"""

import logging
import os
import threading
from datetime import datetime
from tempfile import NamedTemporaryFile

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import exporters
from audio_pipeline import (
    AudioDecodeError,
    ModelUnavailableError,
    prepare_and_transcribe,
    validate_extension,
)
from config import Config
from models import EXPORT_FORMATS, Transcription, db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("chatbot-vocal")

# Le rate limiter est global (l'extension conserve des références faibles)
# et configuré par application via init_app() et les clés RATELIMIT_*.
limiter = Limiter(get_remote_address)

# Le modèle Vosk est chargé une seule fois, au premier appel (lazy loading).
_model = None
_model_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                if not os.path.isdir(Config.MODEL_PATH):
                    raise ModelUnavailableError(
                        f"Le modèle Vosk est introuvable dans '{Config.MODEL_PATH}'. "
                        "Lancez d'abord : python scripts/download_model.py"
                    )
                try:
                    from vosk import Model

                    logger.info("Chargement du modèle Vosk depuis %s ...", Config.MODEL_PATH)
                    _model = Model(Config.MODEL_PATH)
                    logger.info("Modèle Vosk chargé")
                except ModelUnavailableError:
                    raise
                except Exception as exc:
                    raise ModelUnavailableError(
                        f"Impossible de charger le modèle Vosk : {exc}"
                    ) from exc
    return _model


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    os.makedirs(app.config["DATA_DIR"], exist_ok=True)
    app.config["TRANSCRIPTIONS_DIR"] = os.path.join(app.config["DATA_DIR"], "transcriptions")
    os.makedirs(app.config["TRANSCRIPTIONS_DIR"], exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    # Les clés RATELIMIT_ENABLED / RATELIMIT_STORAGE_URI / RATELIMIT_DEFAULT
    # sont lues automatiquement dans la configuration Flask par l'extension.
    limiter.init_app(app)

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------
    def export_paths(base_path):
        return {fmt: f"{base_path}.{fmt}" for fmt in EXPORT_FORMATS}

    def write_exports(transcription, text, words=None):
        """Génère les fichiers DOCX, PDF, TXT (et SRT si mots horodatés)."""
        base_path = os.path.join(app.config["TRANSCRIPTIONS_DIR"], transcription.base_name)
        kwargs = {
            "language": transcription.language,
            "duration_seconds": transcription.duration_seconds,
        }
        exporters.render_docx(text, f"{base_path}.docx", **kwargs)
        exporters.render_pdf(text, f"{base_path}.pdf", **kwargs)
        exporters.render_txt(text, f"{base_path}.txt", **kwargs)
        if words:
            exporters.render_srt(words, f"{base_path}.srt", **kwargs)
            transcription.has_timestamps = True

    def process_audio(audio_file):
        # Lève tôt une 503 explicite si le modèle n'est pas installé
        get_model()
        suffix = os.path.splitext(audio_file.filename)[1] or ".audio"
        temp_path = None
        try:
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                audio_file.save(tmp.name)
                temp_path = tmp.name

            text, words, duration = prepare_and_transcribe(temp_path, get_model)
            text = text.strip()
            if not text:
                raise ValueError("Aucun texte transcrit (audio vide, silencieux ou inaudible).")

            now = datetime.now()
            transcription = Transcription(
                text=text,
                base_name=(
                    f"transcription_{now.strftime('%Y%m%d_%H%M%S_%f')}_"
                ),
                duration_seconds=round(duration, 2),
                language=app.config["LANGUAGE"],
            )
            # L'identifiant UUID est généré à l'insertion ; on le complète au base_name
            db.session.add(transcription)
            db.session.flush()
            transcription.base_name = f"{transcription.base_name}{transcription.id[:8]}"

            write_exports(transcription, text, words)
            db.session.commit()
            logger.info("Transcription %s générée (%d caractères)", transcription.id, len(text))
            return transcription
        except Exception:
            db.session.rollback()
            raise
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    logger.warning("Impossible de supprimer %s", temp_path)

    def delete_files(transcription):
        base_path = os.path.join(app.config["TRANSCRIPTIONS_DIR"], transcription.base_name)
        for path in export_paths(base_path).values():
            if os.path.exists(path):
                os.unlink(path)

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @app.route("/health")
    def health():
        from sqlalchemy import text as sql_text

        database_ok = True
        try:
            db.session.execute(sql_text("SELECT 1"))
        except Exception:
            logger.exception("La base de données ne répond pas")
            database_ok = False
        return jsonify(
            {
                "status": "ok" if database_ok else "degraded",
                "database": "ok" if database_ok else "error",
                "model_path": app.config["MODEL_PATH"],
                "model_available": os.path.isdir(app.config["MODEL_PATH"]),
            }
        ), (200 if database_ok else 503)

    @app.route("/api/transcribe", methods=["POST"])
    @limiter.limit(app.config["RATELIMIT_TRANSCRIBE"])
    def transcribe():
        if "audio" not in request.files:
            return jsonify({"error": "Aucun fichier audio reçu (champ 'audio' attendu)."}), 400

        audio_file = request.files["audio"]
        if not audio_file.filename:
            return jsonify({"error": "Aucun fichier audio sélectionné."}), 400

        allowed, ext = validate_extension(audio_file.filename)
        if not allowed:
            return (
                jsonify(
                    {
                        "error": (
                            f"Format '.{ext}' non supporté. Formats acceptés : "
                            + ", ".join(sorted(app.config["ALLOWED_EXTENSIONS"]))
                        )
                    }
                ),
                415,
            )

        try:
            transcription = process_audio(audio_file)
        except ModelUnavailableError as exc:
            logger.error("Modèle indisponible : %s", exc)
            return jsonify({"error": str(exc)}), 503
        except AudioDecodeError as exc:
            return jsonify({"error": str(exc)}), 422
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 422
        except Exception:
            logger.exception("Erreur pendant le traitement de l'audio")
            return jsonify({"error": "Erreur interne lors du traitement de l'audio."}), 500

        return jsonify(transcription.to_dict()), 201

    @app.route("/api/transcriptions", methods=["GET"])
    def list_transcriptions():
        items = (
            db.session.query(Transcription)
            .order_by(Transcription.created_at.desc())
            .all()
        )
        return jsonify([item.to_dict() for item in items])

    @app.route("/api/transcriptions/<transcription_id>", methods=["GET"])
    def get_transcription(transcription_id):
        transcription = db.get_or_404(Transcription, transcription_id)
        return jsonify(transcription.to_dict())

    @app.route("/api/transcriptions/<transcription_id>", methods=["PATCH"])
    def update_transcription(transcription_id):
        transcription = db.get_or_404(Transcription, transcription_id)
        payload = request.get_json(silent=True) or {}
        new_text = payload.get("text")
        if not isinstance(new_text, str) or not new_text.strip():
            return jsonify({"error": "Le champ 'text' doit être une chaîne non vide."}), 400

        transcription.text = new_text.strip()
        # Les exports DOCX / PDF / TXT sont régénérés ; le SRT d'origine est conservé.
        base_path = os.path.join(app.config["TRANSCRIPTIONS_DIR"], transcription.base_name)
        kwargs = {
            "language": transcription.language,
            "duration_seconds": transcription.duration_seconds,
        }
        exporters.render_docx(transcription.text, f"{base_path}.docx", **kwargs)
        exporters.render_pdf(transcription.text, f"{base_path}.pdf", **kwargs)
        exporters.render_txt(transcription.text, f"{base_path}.txt", **kwargs)
        db.session.commit()
        logger.info("Transcription %s modifiée", transcription.id)
        return jsonify(transcription.to_dict())

    @app.route("/api/transcriptions/<transcription_id>", methods=["DELETE"])
    def delete_transcription(transcription_id):
        transcription = db.get_or_404(Transcription, transcription_id)
        delete_files(transcription)
        db.session.delete(transcription)
        db.session.commit()
        return "", 204

    @app.route("/api/transcriptions", methods=["DELETE"])
    def clear_transcriptions():
        for transcription in db.session.query(Transcription).all():
            delete_files(transcription)
        db.session.query(Transcription).delete()
        db.session.commit()
        return "", 204

    @app.route("/api/transcriptions/<transcription_id>/export/<fmt>")
    def export_transcription(transcription_id, fmt):
        transcription = db.get_or_404(Transcription, transcription_id)
        if fmt not in EXPORT_FORMATS:
            return jsonify({"error": f"Format d'export inconnu : {fmt}"}), 404
        if fmt == "srt" and not transcription.has_timestamps:
            return jsonify({"error": "Export SRT indisponible pour cette transcription."}), 404

        path = os.path.join(
            app.config["TRANSCRIPTIONS_DIR"], f"{transcription.base_name}.{fmt}"
        )
        if not os.path.exists(path):
            return jsonify({"error": "Fichier d'export manquant sur le serveur."}), 410

        mimetypes = {
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pdf": "application/pdf",
            "txt": "text/plain",
            "srt": "application/x-subrip",
        }
        return send_file(
            path,
            as_attachment=True,
            download_name=f"{transcription.base_name}.{fmt}",
            mimetype=mimetypes[fmt],
        )

    # ------------------------------------------------------------------
    # Gestionnaires d'erreurs
    # ------------------------------------------------------------------
    @app.errorhandler(413)
    def file_too_large(_error):
        return (
            jsonify(
                {"error": f"Fichier trop volumineux (limite : {app.config['MAX_CONTENT_LENGTH_MB']} Mo)."}
            ),
            413,
        )

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Ressource introuvable."}), 404
        return jsonify({"error": "Ressource introuvable.", "service": "Chatbot Vocal"}), 404

    @app.errorhandler(429)
    def rate_limited(error):
        return jsonify({"error": "Trop de requêtes, réessayez plus tard.", "details": str(error.description)}), 429

    @app.errorhandler(500)
    def internal_error(_error):
        logger.exception("Erreur serveur")
        return jsonify({"error": "Erreur interne du serveur."}), 500

    @app.route("/")
    def home():
        return jsonify(
            {
                "service": "Chatbot Vocal",
                "status": "actif",
                "endpoints": [
                    "GET /health",
                    "POST /api/transcribe",
                    "GET /api/transcriptions",
                    "GET /api/transcriptions/<id>",
                    "PATCH /api/transcriptions/<id>",
                    "GET /api/transcriptions/<id>/export/<fmt>",
                ],
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5001"))
    logger.info("Démarrage du serveur sur http://%s:%s (debug=%s)", host, port, debug)
    app.run(debug=debug, host=host, port=port)
