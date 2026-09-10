"""Traitement asynchrone des gros fichiers audio.

Un exécuteur en threads (ThreadPoolExecutor) traite les tâches en arrière-plan
avec suivi de progression dans la base. Pour un déploiement multi-processus,
cette brique se remplace par Celery/RQ + Redis (le schéma de la table Job et
l'API REST restent identiques).
"""

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from models import (
    JOB_DONE,
    JOB_ERROR,
    JOB_PROCESSING,
    Job,
    db,
)
from services import transcribe_file

logger = logging.getLogger("chatbot-vocal")


class JobRunner:
    def __init__(self, app, max_workers=2):
        self.app = app
        self._executor = ThreadPoolExecutor(max_workers=max_workers,
                                            thread_name_prefix="transcribe")
        self._lock = threading.Lock()

    def submit(self, job_id, audio_path):
        self._executor.submit(self._run, job_id, audio_path)

    def _run(self, job_id, audio_path):
        with self.app.app_context():
            job = db.session.get(Job, job_id)
            if job is None:
                return
            job.status = JOB_PROCESSING
            job.progress = 1
            job.message = "Conversion et reconnaissance en cours..."
            db.session.commit()

            def progress(percent):
                # Évite des commit trop fréquents
                with self._lock:
                    if percent - (job.progress or 0) >= 5 or percent >= 100:
                        job.progress = percent
                        db.session.commit()

            try:
                transcription = transcribe_file(
                    user_id=job.user_id,
                    audio_path=audio_path,
                    engine=job.engine,
                    language=job.language,
                    progress=progress,
                )
                job.status = JOB_DONE
                job.progress = 100
                job.message = "Terminée"
                job.transcription_id = transcription.id
                db.session.commit()
                logger.info("Tâche %s terminée", job_id)
            except Exception as exc:  # noqa: BLE001 - on veut tracer toute erreur de tâche
                db.session.rollback()
                job = db.session.get(Job, job_id)
                job.status = JOB_ERROR
                job.error = str(exc)
                job.message = "Échec de la transcription"
                db.session.commit()
                logger.exception("Tâche %s en échec", job_id)
            finally:
                if audio_path and os.path.exists(audio_path):
                    os.unlink(audio_path)

    def shutdown(self):
        self._executor.shutdown(wait=False, cancel_futures=True)
