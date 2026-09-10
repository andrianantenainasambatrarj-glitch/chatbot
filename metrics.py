"""Métriques Prometheus minimalistes, sans dépendance externe.

Exposées sur /metrics, protégées par METRICS_TOKEN (en-tête
Authorization: Bearer <token>). Compteurs en mémoire, suffisants pour un
premier niveau d'observabilité.
"""

import threading
import time


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.started_at = time.time()
        self.counters = {
            "transcriptions_total": 0,
            "transcription_errors_total": 0,
            "jobs_total": 0,
            "jobs_failed_total": 0,
            "audio_seconds_total": 0.0,
        }

    def incr(self, name, amount=1):
        with self._lock:
            self.counters[name] = self.counters.get(name, 0) + amount

    def render(self):
        lines = [
            "# HELP chatbot_uptime_seconds Temps écoulé depuis le démarrage",
            "# TYPE chatbot_uptime_seconds gauge",
            f"chatbot_uptime_seconds {int(time.time() - self.started_at)}",
        ]
        mapping = {
            "transcriptions_total": ("Nombre de transcriptions réussies", "counter"),
            "transcription_errors_total": ("Erreurs de transcription", "counter"),
            "jobs_total": ("Tâches asynchrones terminées", "counter"),
            "jobs_failed_total": ("Tâches asynchrones en échec", "counter"),
            "audio_seconds_total": ("Secondes audio transcrites", "counter"),
        }
        with self._lock:
            for name, value in self.counters.items():
                help_text, metric_type = mapping.get(name, (name, "counter"))
                lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} {metric_type}")
                lines.append(f"{name} {value}")
        return "\n".join(lines) + "\n"
