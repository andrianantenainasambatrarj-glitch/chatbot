"""Backend Flask du Chatbot Vocal.

Fonctionnalités (Sprints 1 à 3) :
  - authentification JWT (inscription / connexion), transcriptions privées
  - transcription Vosk hors-ligne ou Whisper (optionnel), multilingue
  - fichiers multi-formats, exports DOCX / PDF / TXT / SRT
  - transcription en temps réel par WebSocket (/ws/transcribe)
  - gros fichiers traités en tâche asynchrone avec progression (/api/jobs)
"""

import logging
import os
from tempfile import NamedTemporaryFile

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_sock import Sock

import exporters
import services
import streaming
from audio_pipeline import AudioDecodeError, validate_extension
from auth import auth_bp, current_user, require_auth
from config import Config
from engines import UnknownEngineError, engines_metadata, get_engine
from engines.vosk_engine import ModelUnavailableError
from engines.whisper_engine import WhisperUnavailableError
from jobs import JobRunner
from models import (
    JOB_PENDING,
    Job,
    Transcription,
    db,
)
from ratelimit import limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("chatbot-vocal")


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    os.makedirs(app.config["DATA_DIR"], exist_ok=True)
    app.config["TRANSCRIPTIONS_DIR"] = os.path.join(app.config["DATA_DIR"], "transcriptions")
    app.config["UPLOADS_DIR"] = os.path.join(app.config["DATA_DIR"], "uploads")
    os.makedirs(app.config["TRANSCRIPTIONS_DIR"], exist_ok=True)
    os.makedirs(app.config["UPLOADS_DIR"], exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    limiter.init_app(app)
    app.register_blueprint(auth_bp)

    sock = Sock(app)
    app.extensions["vosk_engine"] = get_engine("vosk")
    streaming.register_websocket(sock, app)

    runner = JobRunner(app, max_workers=app.config["JOB_WORKERS"])
    app.extensions["job_runner"] = runner

    # ------------------------------------------------------------------
    def owned_transcription_or_404(transcription_id):
        return (
            db.session.query(Transcription)
            .filter_by(id=transcription_id, user_id=current_user().id)
            .first_or_404()
        )

    def export_paths(base_path):
        return {fmt: f"{base_path}.{fmt}" for fmt in ("docx", "pdf", "txt", "srt")}

    def delete_files(transcription):
        base_path = os.path.join(app.config["TRANSCRIPTIONS_DIR"], transcription.base_name)
        for path in export_paths(base_path).values():
            if os.path.exists(path):
                os.unlink(path)

    def handle_transcription_error(exc):
        if isinstance(exc, (ModelUnavailableError, WhisperUnavailableError)):
            logger.error("Moteur indisponible : %s", exc)
            return jsonify({"error": str(exc)}), 503
        if isinstance(exc, UnknownEngineError):
            return jsonify({"error": str(exc)}), 400
        if isinstance(exc, AudioDecodeError):
            return jsonify({"error": str(exc)}), 422
        if isinstance(exc, ValueError):
            return jsonify({"error": str(exc)}), 422
        logger.exception("Erreur pendant le traitement de l'audio")
        return jsonify({"error": "Erreur interne lors du traitement de l'audio."}), 500

    # ------------------------------------------------------------------
    # Santé / moteurs
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
        return (
            jsonify(
                {
                    "status": "ok" if database_ok else "degraded",
                    "database": "ok" if database_ok else "error",
                }
            ),
            200 if database_ok else 503,
        )

    @app.route("/api/engines")
    @require_auth
    def list_engines():
        return jsonify(engines_metadata())

    # ------------------------------------------------------------------
    # Transcription synchrone / asynchrone
    # ------------------------------------------------------------------
    @app.route("/api/transcribe", methods=["POST"])
    @require_auth
    @limiter.limit(lambda: app.config["RATELIMIT_TRANSCRIBE"])
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

        engine_name = (request.form.get("engine") or app.config["DEFAULT_ENGINE"]).lower()
        language = request.form.get("language") or app.config["DEFAULT_LANGUAGE"]
        if engine_name not in ("vosk", "whisper"):
            return jsonify({"error": f"Moteur '{engine_name}' inconnu (vosk|whisper)."}), 400

        # Whisper n'est pas streamable mais gère les fichiers ; vérification rapide
        try:
            get_engine(engine_name)
        except UnknownEngineError as exc:
            return jsonify({"error": str(exc)}), 400

        force_async = request.form.get("async", "").lower() in ("1", "true", "yes")
        size = request.content_length or 0
        is_large = size > app.config["ASYNC_THRESHOLD_MB"] * 1024 * 1024

        if force_async or is_large:
            return start_async_job(audio_file, engine_name, language)

        suffix = os.path.splitext(audio_file.filename)[1] or ".audio"
        temp_path = None
        try:
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                audio_file.save(tmp.name)
                temp_path = tmp.name
            transcription = services.transcribe_file(
                user_id=current_user().id,
                audio_path=temp_path,
                engine=engine_name,
                language=language,
            )
        except Exception as exc:  # noqa: BLE001 - gestion centralisée des codes
            return handle_transcription_error(exc)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
        return jsonify(transcription.to_dict()), 201

    def start_async_job(audio_file, engine_name, language):
        job = Job(
            user_id=current_user().id,
            status=JOB_PENDING,
            progress=0,
            message="En file d'attente...",
            engine=engine_name,
            language=language,
        )
        db.session.add(job)
        db.session.commit()

        suffix = os.path.splitext(audio_file.filename)[1] or ".audio"
        destination = os.path.join(app.config["UPLOADS_DIR"], f"{job.id}{suffix}")
        audio_file.save(destination)
        runner.submit(job.id, destination)
        return jsonify(job.to_dict()), 202

    @app.route("/api/jobs", methods=["GET"])
    @require_auth
    def list_jobs():
        jobs = (
            db.session.query(Job)
            .filter_by(user_id=current_user().id)
            .order_by(Job.created_at.desc())
            .all()
        )
        return jsonify([job.to_dict() for job in jobs])

    @app.route("/api/jobs/<job_id>", methods=["GET"])
    @require_auth
    def get_job(job_id):
        job = (
            db.session.query(Job)
            .filter_by(id=job_id, user_id=current_user().id)
            .first_or_404()
        )
        return jsonify(job.to_dict())

    # ------------------------------------------------------------------
    # CRUD transcriptions
    # ------------------------------------------------------------------
    @app.route("/api/transcriptions", methods=["GET"])
    @require_auth
    def list_transcriptions():
        items = (
            db.session.query(Transcription)
            .filter_by(user_id=current_user().id)
            .order_by(Transcription.created_at.desc())
            .all()
        )
        return jsonify([item.to_dict() for item in items])

    @app.route("/api/transcriptions/<transcription_id>", methods=["GET"])
    @require_auth
    def get_transcription(transcription_id):
        return jsonify(owned_transcription_or_404(transcription_id).to_dict())

    @app.route("/api/transcriptions/<transcription_id>", methods=["PATCH"])
    @require_auth
    def update_transcription(transcription_id):
        transcription = owned_transcription_or_404(transcription_id)
        payload = request.get_json(silent=True) or {}
        new_text = payload.get("text")
        if not isinstance(new_text, str) or not new_text.strip():
            return jsonify({"error": "Le champ 'text' doit être une chaîne non vide."}), 400

        transcription.text = new_text.strip()
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
    @require_auth
    def delete_transcription(transcription_id):
        transcription = owned_transcription_or_404(transcription_id)
        delete_files(transcription)
        db.session.delete(transcription)
        db.session.commit()
        return "", 204

    @app.route("/api/transcriptions", methods=["DELETE"])
    @require_auth
    def clear_transcriptions():
        items = (
            db.session.query(Transcription)
            .filter_by(user_id=current_user().id)
            .all()
        )
        for transcription in items:
            delete_files(transcription)
        for transcription in items:
            db.session.delete(transcription)
        db.session.commit()
        return "", 204

    @app.route("/api/transcriptions/<transcription_id>/export/<fmt>")
    @require_auth
    def export_transcription(transcription_id, fmt):
        transcription = owned_transcription_or_404(transcription_id)
        if fmt not in ("docx", "pdf", "txt", "srt"):
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
        return jsonify({"error": "Ressource introuvable."}), 404

    @app.errorhandler(429)
    def rate_limited(error):
        return (
            jsonify({"error": "Trop de requêtes, réessayez plus tard.", "details": str(error.description)}),
            429,
        )

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
                    "POST /api/auth/register",
                    "POST /api/auth/login",
                    "GET /api/engines",
                    "POST /api/transcribe",
                    "GET /api/transcriptions",
                    "GET /api/jobs/<id>",
                    "WS /ws/transcribe",
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
