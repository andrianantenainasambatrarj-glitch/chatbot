"""Traitement asynchrone des gros fichiers audio.

Un exécuteur en threads (ThreadPoolExecutor) traite les tâches en arrière-plan
avec suivi de progression dans la base. Pour du multi-processus, cette brique
se remplace par Celery/RQ + Redis (le schéma de la table Job et l'API REST
restent identiques).

En production (gunicorn avec GeventWebSocketWorker), gevent remplace les
threads Python par des greenlets : un calcul CPU bloquant (Vosk, Whisper,
ffmpeg) gèlerait alors toute la boucle événementielle et le serveur ne
répondrait plus pendant la transcription. On délègue donc les tâches au
*vrai* pool de threads système fourni par gevent quand il est disponible.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor

from flask import current_app

# Verrou qui reste un verrou de thread système même quand gevent a
# monkey-patché `threading` (les tâches tournent dans le pool natif gevent).
try:
    from gevent.monkey import get_original as _get_original

    NativeLock = _get_original("threading", "Lock")
except Exception:  # noqa: BLE001
    from threading import Lock as NativeLock

from models import (
    JOB_DONE,
    JOB_ERROR,
    JOB_PENDING,
    JOB_PROCESSING,
    Job,
    User,
    db,
)
from services import QuotaExceededError, transcribe_file

logger = logging.getLogger("chatbot-vocal")

try:  # production gevent/gunicorn
    from gevent import get_hub as _get_gevent_hub
except Exception:  # environnement de développement (serveur Werkzeug/Windows)
    _get_gevent_hub = None


class JobRunner:
    def __init__(self, app, max_workers=2):
        self.app = app
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="transcribe"
        )
        self._lock = NativeLock()
        if _get_gevent_hub is not None:
            # Le pool de threads natifs de gevent doit être assez grand pour
            # accueillir les tâches plus les traitements internes de gevent.
            hub = _get_gevent_hub()
            try:
                hub.threadpool.resize(max_workers + 8)
            except Exception:  # noqa: BLE001 - API optionnelle selon la version
                pass

    def submit(self, job_id, audio_path):
        if _get_gevent_hub is not None:
            # Vrai thread système : le calcul bloquant n'immobilise pas la
            # boucle gevent, l'API reste joignable pendant la transcription.
            _get_gevent_hub().threadpool.spawn(self._run, job_id, audio_path)
        else:
            self._executor.submit(self._run, job_id, audio_path)

    def reset_stale_jobs(self):
        """Marque comme échouées les tâches interrompues par un redémarrage.

        Le traitement vit en mémoire : si le conteneur redémarre (mise à
        jour, dépassement de mémoire sur une petite instance), la tâche ne
        reprend jamais et doit être signalée plutôt que de rester bloquée.
        """
        with self.app.app_context():
            stale = (
                db.session.query(Job)
                .filter(Job.status.in_((JOB_PENDING, JOB_PROCESSING)))
                .all()
            )
            for job in stale:
                job.status = JOB_ERROR
                job.message = "Interrompue par un redémarrage du serveur"
                job.error = (
                    "Le serveur a redémarré pendant le traitement. "
                    "Relancez la transcription."
                )
            if stale:
                db.session.commit()
                logger.warning("%d tâche(s) interrompue(s) basculée(s) en erreur", len(stale))

    def _run(self, job_id, audio_path):
        with self.app.app_context():
            job = db.session.get(Job, job_id)
            if job is None:
                return
            user = db.session.get(User, job.user_id)
            job.status = JOB_PROCESSING
            job.progress = 1
            job.message = "Conversion et reconnaissance en cours..."
            db.session.commit()
            metrics = current_app.extensions.get("metrics")
            if metrics:
                metrics.incr("jobs_total")

            def progress(percent):
                with self._lock:
                    if percent - (job.progress or 0) >= 5 or percent >= 100:
                        job.progress = percent
                        db.session.commit()

            try:
                transcription = transcribe_file(
                    user=user,
                    audio_path=audio_path,
                    engine=job.engine,
                    language=job.language,
                    diarization=job.diarize,
                    progress=progress,
                )
                job.status = JOB_DONE
                job.progress = 100
                job.message = "Terminée"
                job.transcription_id = transcription.id
                db.session.commit()
                logger.info("Tâche %s terminée", job_id)
            except Exception as exc:  # noqa: BLE001 - tracer toute erreur de tâche
                db.session.rollback()
                job = db.session.get(Job, job_id)
                job.status = JOB_ERROR
                job.error = str(exc)
                if isinstance(exc, QuotaExceededError):
                    job.message = "Quota dépassé"
                else:
                    job.message = "Échec de la transcription"
                db.session.commit()
                if metrics:
                    metrics.incr("jobs_failed_total")
                logger.exception("Tâche %s en échec", job_id)
            finally:
                if audio_path and os.path.exists(audio_path):
                    os.unlink(audio_path)

    def shutdown(self):
        self._executor.shutdown(wait=False, cancel_futures=True)
