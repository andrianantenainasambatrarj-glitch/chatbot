"""Backend Flask du Chatbot Vocal (Sprints 1 à 4).

Fonctionnalités :
  - comptes JWT, rôles admin, quotas mensuels ; transcriptions privées
  - Vosk (temps réel) ou Whisper (optionnel), multilingue, diarisation
  - fichiers multi-formats synchrones ou en tâche asynchrone (progression)
  - exports DOCX / PDF / TXT / SRT
  - analyses : résumé, actions à faire, mots-clés, tonalité, chat sur le texte
  - partage par lien signé, envoi par e-mail, webhooks, tableau de bord
  - métriques Prometheus sur /metrics
"""

import logging
import os
from tempfile import NamedTemporaryFile

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_sock import Sock

import exporters
import integrations
import services
import streaming
from audio_pipeline import AudioDecodeError, validate_extension
from auth import auth_bp, current_user, require_admin, require_auth
from config import Config
from engines import UnknownEngineError, engines_metadata, get_engine
from engines.vosk_engine import ModelUnavailableError
from engines.whisper_engine import WhisperUnavailableError
from integrations import EmailNotConfiguredError
from jobs import JobRunner
from metrics import Metrics
from migrations import ensure_sqlite_schema
from models import (
    ROLE_ADMIN,
    Job,
    ShareLink,
    Transcription,
    User,
    db,
)
from nlp.llm import is_configured as llm_is_configured
from ratelimit import limiter
from services import QuotaExceededError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("chatbot-vocal")

EXPORT_MIMETYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "txt": "text/plain",
    "srt": "application/x-subrip",
}


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
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            ensure_sqlite_schema(db)

    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    limiter.init_app(app)
    app.register_blueprint(auth_bp)

    sock = Sock(app)
    app.extensions["vosk_engine"] = get_engine("vosk")
    app.extensions["metrics"] = Metrics()
    streaming.register_websocket(sock, app)

    runner = JobRunner(app, max_workers=app.config["JOB_WORKERS"])
    app.extensions["job_runner"] = runner
    # Les tâches en cours au moment d'un arrêt précédent ne peuvent pas
    # reprendre : on les signale en erreur plutôt que de les laisser bloquées.
    runner.reset_stale_jobs()

    # Préchargement du modèle Vosk par défaut dans un thread système (pour ne
    # pas retarder la réponse de santé au démarrage) : la première
    # transcription ne paie alors plus le chargement du modèle (plusieurs
    # secondes sur petite instance).
    def _prewarm_vosk():
        if not app.config.get("PREWARM_MODELS", True):
            return
        with app.app_context():
            try:
                get_engine("vosk").create_recognizer(app.config["DEFAULT_LANGUAGE"])
                logger.info("Modèle Vosk '%s' préchargé", app.config["DEFAULT_LANGUAGE"])
            except Exception:  # noqa: BLE001 - le démarrage ne doit pas échouer
                logger.warning("Préchauffage Vosk impossible", exc_info=True)

    from jobs import _Thread as _NativeThread

    _NativeThread(target=_prewarm_vosk, name="prewarm-vosk", daemon=True).start()

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

    def send_export_file(transcription, fmt):
        if fmt not in EXPORT_MIMETYPES:
            return jsonify({"error": f"Format d'export inconnu : {fmt}"}), 404
        if fmt == "srt" and not transcription.has_timestamps:
            return jsonify({"error": "Export SRT indisponible pour cette transcription."}), 404
        path = os.path.join(
            app.config["TRANSCRIPTIONS_DIR"], f"{transcription.base_name}.{fmt}"
        )
        # Sur hébergement gratuit à disque éphémère (ex : plan Free Render),
        # les fichiers générés peuvent avoir disparu après un redémarrage :
        # on les régénère depuis le texte stocké en base.
        if not os.path.exists(path):
            if fmt == "srt":
                return jsonify({"error": "Fichier d'export manquant sur le serveur."}), 410
            kwargs = {
                "language": transcription.language,
                "duration_seconds": transcription.duration_seconds,
            }
            try:
                if fmt == "docx":
                    exporters.render_docx(transcription.text, path, **kwargs)
                elif fmt == "pdf":
                    exporters.render_pdf(transcription.text, path, **kwargs)
                elif fmt == "txt":
                    exporters.render_txt(transcription.text, path, **kwargs)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Régénération de l'export %s impossible", fmt)
                return jsonify({"error": f"Impossible de générer l'export : {exc}"}), 500
        return send_file(
            path,
            as_attachment=True,
            download_name=f"{transcription.base_name}.{fmt}",
            mimetype=EXPORT_MIMETYPES[fmt],
        )

    def handle_transcription_error(exc):
        if isinstance(exc, (ModelUnavailableError, WhisperUnavailableError)):
            logger.error("Moteur indisponible : %s", exc)
            return jsonify({"error": str(exc)}), 503
        if isinstance(exc, UnknownEngineError):
            return jsonify({"error": str(exc)}), 400
        if isinstance(exc, QuotaExceededError):
            return jsonify({"error": str(exc), "code": "quota_exceeded",
                            "limit_minutes": exc.limit_minutes}), 402
        if isinstance(exc, AudioDecodeError):
            return jsonify({"error": str(exc)}), 422
        if isinstance(exc, ValueError):
            return jsonify({"error": str(exc)}), 422
        app.extensions["metrics"].incr("transcription_errors_total")
        logger.exception("Erreur pendant le traitement de l'audio")
        return jsonify({"error": "Erreur interne lors du traitement de l'audio."}), 500

    # ------------------------------------------------------------------
    # Santé / moteurs / métriques
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
                    "llm_configured": bool(app.config["LLM_API_KEY"]),
                }
            ),
            200 if database_ok else 503,
        )

    @app.route("/metrics")
    def metrics():
        token = app.config["METRICS_TOKEN"]
        if token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header != f"Bearer {token}":
                return jsonify({"error": "Jeton de métriques requis."}), 401
        from flask import Response

        return Response(app.extensions["metrics"].render(), mimetype="text/plain")

    @app.route("/api/engines")
    @require_auth
    def list_engines():
        return jsonify(engines_metadata())

    # ------------------------------------------------------------------
    # Transcription
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
        diarization = request.form.get("diarize", "").lower() in ("1", "true", "yes")
        if engine_name not in ("vosk", "whisper"):
            return jsonify({"error": f"Moteur '{engine_name}' inconnu (vosk|whisper)."}), 400

        force_async = request.form.get("async", "").lower() in ("1", "true", "yes")
        size = request.content_length or 0
        is_large = size > app.config["ASYNC_THRESHOLD_MB"] * 1024 * 1024

        if force_async or is_large:
            return start_async_job(audio_file, engine_name, language, diarization)

        suffix = os.path.splitext(audio_file.filename)[1] or ".audio"
        temp_path = None
        try:
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                audio_file.save(tmp.name)
                temp_path = tmp.name
            transcription = services.transcribe_file(
                user=current_user(),
                audio_path=temp_path,
                engine=engine_name,
                language=language,
                diarization=diarization,
            )
        except Exception as exc:  # noqa: BLE001
            return handle_transcription_error(exc)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
        return jsonify(transcription.to_dict(include_analysis=False)), 201

    def start_async_job(audio_file, engine_name, language, diarization):
        job = Job(
            user_id=current_user().id,
            status="pending",
            progress=0,
            message="En file d'attente...",
            engine=engine_name,
            language=language,
            diarize=diarization,
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
            db.session.query(Job).filter_by(user_id=current_user().id)
            .order_by(Job.created_at.desc()).all()
        )
        return jsonify([job.to_dict() for job in jobs])

    @app.route("/api/jobs/<job_id>", methods=["GET"])
    @require_auth
    def get_job(job_id):
        job = db.session.query(Job).filter_by(id=job_id, user_id=current_user().id).first_or_404()
        return jsonify(job.to_dict())

    # ------------------------------------------------------------------
    # CRUD transcriptions
    # ------------------------------------------------------------------
    @app.route("/api/transcriptions", methods=["GET"])
    @require_auth
    def list_transcriptions():
        items = (
            db.session.query(Transcription).filter_by(user_id=current_user().id)
            .order_by(Transcription.created_at.desc()).all()
        )
        return jsonify([item.to_dict() for item in items])

    @app.route("/api/transcriptions/<transcription_id>", methods=["GET"])
    @require_auth
    def get_transcription(transcription_id):
        transcription = owned_transcription_or_404(transcription_id)
        return jsonify(transcription.to_dict(include_analysis=True))

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
        kwargs = {"language": transcription.language,
                  "duration_seconds": transcription.duration_seconds}
        exporters.render_docx(transcription.text, f"{base_path}.docx", **kwargs)
        exporters.render_pdf(transcription.text, f"{base_path}.pdf", **kwargs)
        exporters.render_txt(transcription.text, f"{base_path}.txt", **kwargs)
        db.session.commit()
        return jsonify(transcription.to_dict(include_analysis=True))

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
        items = db.session.query(Transcription).filter_by(user_id=current_user().id).all()
        for transcription in items:
            delete_files(transcription)
            db.session.delete(transcription)
        db.session.commit()
        return "", 204

    @app.route("/api/transcriptions/<transcription_id>/export/<fmt>")
    @require_auth
    def export_transcription(transcription_id, fmt):
        transcription = owned_transcription_or_404(transcription_id)
        return send_export_file(transcription, fmt)

    # ------------------------------------------------------------------
    # Analyses (résumé, tâches, mots-clés) et chat
    # ------------------------------------------------------------------
    @app.route("/api/transcriptions/<transcription_id>/insights", methods=["POST", "GET"])
    @require_auth
    def transcription_insights(transcription_id):
        transcription = owned_transcription_or_404(transcription_id)
        if request.method == "POST" or transcription.summary is None:
            services.generate_insights(transcription)
        return jsonify(
            {
                "summary": transcription.summary,
                "action_items": transcription.action_items or [],
                "keywords": transcription.keywords or [],
                "sentiment": transcription.sentiment,
                "engine": transcription.insights_engine,
                "llm_available": llm_is_configured(),
            }
        )

    @app.route("/api/transcriptions/<transcription_id>/chat", methods=["POST"])
    @require_auth
    def transcription_chat(transcription_id):
        transcription = owned_transcription_or_404(transcription_id)
        payload = request.get_json(silent=True) or {}
        question = (payload.get("message") or "").strip()
        if not question:
            return jsonify({"error": "Le champ 'message' est requis."}), 400
        history = payload.get("history") if isinstance(payload.get("history"), list) else []
        reply = services.answer_question(transcription, question, history=history[-8:])
        return jsonify({"reply": reply, "llm_available": llm_is_configured()})

    # ------------------------------------------------------------------
    # Partage par lien (lecture publique, sans jeton)
    # ------------------------------------------------------------------
    @app.route("/api/transcriptions/<transcription_id>/share", methods=["POST"])
    @require_auth
    def create_share_link(transcription_id):
        transcription = owned_transcription_or_404(transcription_id)
        link = ShareLink(transcription_id=transcription.id)
        db.session.add(link)
        db.session.commit()
        return jsonify(link.to_dict()), 201

    @app.route("/api/transcriptions/<transcription_id>/share", methods=["GET"])
    @require_auth
    def list_share_links(transcription_id):
        transcription = owned_transcription_or_404(transcription_id)
        return jsonify([link.to_dict() for link in transcription.share_links if link.is_valid()])

    @app.route("/api/transcriptions/<transcription_id>/share/<token>", methods=["DELETE"])
    @require_auth
    def revoke_share_link(transcription_id, token):
        transcription = owned_transcription_or_404(transcription_id)
        link = next((item for item in transcription.share_links if item.token == token), None)
        if link is None:
            return jsonify({"error": "Lien de partage introuvable."}), 404
        db.session.delete(link)
        db.session.commit()
        return "", 204

    @app.route("/api/shared/<token>")
    def shared_transcription(token):
        link = db.session.get(ShareLink, token)
        if link is None or not link.is_valid():
            return jsonify({"error": "Lien de partage invalide ou expiré."}), 404
        return jsonify(link.transcription.to_dict(include_analysis=True))

    @app.route("/api/shared/<token>/export/<fmt>")
    def shared_export(token, fmt):
        link = db.session.get(ShareLink, token)
        if link is None or not link.is_valid():
            return jsonify({"error": "Lien de partage invalide ou expiré."}), 404
        return send_export_file(link.transcription, fmt)

    # ------------------------------------------------------------------
    # Intégrations : e-mail et webhook
    # ------------------------------------------------------------------
    @app.route("/api/transcriptions/<transcription_id>/email", methods=["POST"])
    @require_auth
    def email_transcription(transcription_id):
        transcription = owned_transcription_or_404(transcription_id)
        payload = request.get_json(silent=True) or {}
        to_email = (payload.get("email") or "").strip()
        if not to_email or "@" not in to_email:
            return jsonify({"error": "Adresse e-mail de destination invalide."}), 400
        try:
            files = integrations.attachment_files(app.config, transcription)
            integrations.send_transcription_email(
                to_email=to_email, transcription=transcription,
                files=files, config=app.config,
            )
        except EmailNotConfiguredError as exc:
            return jsonify({"error": str(exc)}), 503
        except Exception as exc:  # noqa: BLE001
            logger.exception("Échec d'envoi d'e-mail")
            return jsonify({"error": f"Échec de l'envoi : {exc}"}), 502
        return jsonify({"status": "envoyé", "email": to_email})

    @app.route("/api/transcriptions/<transcription_id>/webhook", methods=["POST"])
    @require_auth
    def webhook_transcription(transcription_id):
        transcription = owned_transcription_or_404(transcription_id)
        payload = request.get_json(silent=True) or {}
        url = (payload.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            return jsonify({"error": "URL de webhook invalide (http/https)."}), 400
        try:
            status = integrations.post_webhook(
                url, {"event": "transcription.created",
                      "transcription": transcription.to_dict(include_analysis=True)}
            )
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": f"Le webhook a échoué : {exc}"}), 502
        return jsonify({"status": "livré", "http_status": status})

    # ------------------------------------------------------------------
    # Tableau de bord et administration
    # ------------------------------------------------------------------
    @app.route("/api/stats")
    @require_auth
    def user_stats():
        return jsonify(_dashboard_stats(current_user()))

    @app.route("/api/admin/users")
    @require_admin
    def admin_users():
        users = db.session.query(User).order_by(User.created_at.desc()).all()
        result = []
        for user in users:
            data = user.to_dict()
            data.update(_dashboard_stats(user))
            result.append(data)
        return jsonify(result)

    @app.route("/api/admin/users/<user_id>", methods=["PATCH"])
    @require_admin
    def admin_update_user(user_id):
        user = db.get_or_404(User, user_id)
        payload = request.get_json(silent=True) or {}
        if "role" in payload and payload["role"] in ("user", ROLE_ADMIN):
            user.role = payload["role"]
        if "monthly_quota_minutes" in payload:
            value = payload["monthly_quota_minutes"]
            user.monthly_quota_minutes = None if value in (None, 0, "0") else int(value)
        db.session.commit()
        return jsonify(user.to_dict())

    @app.route("/api/admin/stats")
    @require_admin
    def admin_stats():
        totals = {
            "users": db.session.query(User).count(),
            "transcriptions": db.session.query(Transcription).count(),
            "jobs_pending": db.session.query(Job).filter(Job.status != "done").count(),
        }
        return jsonify(totals)

    def _dashboard_stats(user):
        from sqlalchemy import func

        rows = (
            db.session.query(
                func.date(Transcription.created_at).label("day"),
                func.count().label("count"),
                func.coalesce(func.sum(Transcription.duration_seconds), 0).label("seconds"),
            )
            .filter(Transcription.user_id == user.id)
            .group_by("day").all()
        )
        total_seconds = sum(row.seconds or 0 for row in rows)
        by_engine = dict(
            db.session.query(Transcription.engine, func.count())
            .filter(Transcription.user_id == user.id)
            .group_by(Transcription.engine).all()
        )
        by_language = dict(
            db.session.query(Transcription.language, func.count())
            .filter(Transcription.user_id == user.id)
            .group_by(Transcription.language).all()
        )
        return {
            "total_transcriptions": db.session.query(Transcription)
            .filter_by(user_id=user.id).count(),
            "total_minutes": round(total_seconds / 60, 1),
            "used_minutes_month": round(services.used_minutes_this_month(user.id), 1),
            "quota_minutes": user.monthly_quota_minutes,
            "by_engine": by_engine,
            "by_language": by_language,
            "daily": [
                {"day": str(row.day), "count": row.count,
                 "minutes": round((row.seconds or 0) / 60, 1)}
                for row in rows
            ][-30:],
        }

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
                    "POST /api/auth/register|login",
                    "POST /api/transcribe",
                    "WS /ws/transcribe, /ws/commands",
                    "GET /api/transcriptions/<id>/insights|chat|share",
                    "GET /api/stats, /api/admin/users",
                    "GET /metrics",
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
