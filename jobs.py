"""Traitement asynchrone des gros fichiers audio.

Les tâches de transcription (conversion ffmpeg, Vosk, Whisper) sont des
calculs bloquants qui ne doivent pas geler le serveur web.

En production, gunicorn utilise GeventWebSocketWorker : gevent remplace alors
`threading.Thread` par des greenlets et `subprocess` par une version basée sur
des « child watchers » de la boucle événementielle principale. Deux pièges en
découlent :

1. un calcul CPU dans une greenlet bloque toutes les réponses HTTP ;
2. un sous-processus (ffmpeg) lancé depuis un vrai thread système échoue avec
   « child watchers are only available on the default loop ».

On crée donc les threads de travail avec les primitives `threading`
*originales* (avant monkey-patch) ; la conversion ffmpeg utilise quant à elle
le `subprocess` original (voir audio_pipeline.py).

Pour du multi-machines, cette brique se remplace par Celery/RQ + Redis : le
schéma de la table Job et l'API REST restent identiques.
"""

import logging
import os

from flask import current_app

# Primitives de threading système, même quand gevent a monkey-patché threading.
try:
    from gevent.monkey import get_original as _get_original

    _Thread = _get_original("threading", "Thread")
    _BoundedSemaphore = _get_original("threading", "BoundedSemaphore")
    NativeLock = _get_original("threading", "Lock")
except Exception:  # environnement de développement (Werkzeug/Windows, sans gevent)
    from threading import BoundedSemaphore as _BoundedSemaphore  # type: ignore
    from threading import Lock as NativeLock  # type: ignore
    from threading import Thread as _Thread  # type: ignore

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


class JobRunner:
    def __init__(self, app, max_workers=2):
        self.app = app
        self.max_workers = max(1, int(max_workers))
        # Sémaphore système natif : limite le nombre de calculs simultanés
        # (la mémoire est la ressource critique sur les petites instances).
        self._slots = _BoundedSemaphore(self.max_workers)
        self._lock = NativeLock()
        self._stopping = False

    def submit(self, job_id, audio_path):
        """Démarre la tâche dans un vrai thread système (daemon)."""
        thread = _Thread(
            target=self._thread_entry,
            args=(job_id, audio_path),
            name=f"transcribe-{job_id[:8]}",
            daemon=True,
        )
        thread.start()

    def _thread_entry(self, job_id, audio_path):
        self._slots.acquire()
        try:
            self._run(job_id, audio_path)
        finally:
            self._slots.release()

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
                logger.warning(
                    "%d tâche(s) interrompue(s) basculée(s) en erreur", len(stale)
                )

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
        self._stopping = True
