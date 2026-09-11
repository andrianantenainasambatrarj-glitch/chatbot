"""Lanceur de sous-processus natif, utilisable depuis un thread système
même quand gevent a monkey-patché ``subprocess`` et ``os.waitpid``.

Pourquoi ce module : en production (gunicorn + GeventWebSocketWorker),
gevent réserve la surveillance des processus enfants (« child watchers »)
à sa boucle événementielle principale. Les tâches de transcription
tournent dans de vrais threads système (voir ``jobs.py``) et appellent
directement ffmpeg (voir ``audio_pipeline.py``) : un ``subprocess.Popen``
classique y échoue avec « child watchers are only available on the
default loop », et le Popen natif restauré se bloque sur ``waitpid``.

On passe donc par ``os.posix_spawnp`` (sûr depuis un thread, présent sur
Python 3.8+), avec des tubes en mode non bloquant et des primitives
``os``/``time`` *originales* (avant monkey-patch). L'interface est
volontairement limitée à l'appel ffmpeg :
Popen(argv, stdin=, stdout=, stderr=) puis communicate().
"""

import os as _os

try:  # POSIS uniquement ; le module n'est jamais utilisé sous Windows (sans gevent)
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows
    _fcntl = None

try:  # production gevent
    from gevent.monkey import get_original as _get_original

    def _original(module_name, item_name):
        try:
            return _get_original(module_name, item_name)
        except Exception:  # élément non patché : version standard
            import importlib

            return getattr(importlib.import_module(module_name), item_name)
except Exception:  # développement sans gevent
    def _original(module_name, item_name):
        import importlib

        return getattr(importlib.import_module(module_name), item_name)


_pipe = _original("os", "pipe")
_close = _original("os", "close")
_read = _original("os", "read")
_write = _original("os", "write")
_kill = _original("os", "kill")
_waitpid = _original("os", "waitpid")
_posix_spawnp = _original("os", "posix_spawnp")
_sleep = _original("time", "sleep")

PIPE = -1
STDOUT = -2
DEVNULL = _os.devnull


def _set_nonblocking(fd):
    if _fcntl is None:
        return
    flags = _fcntl.fcntl(fd, _fcntl.F_GETFL)
    _fcntl.fcntl(fd, _fcntl.F_SETFL, flags | _os.O_NONBLOCK)


def _drain(fd):
    """Lit tout ce qui est disponible sur une extrémité de tube, jusqu'à EOF."""
    chunks = []
    while True:
        try:
            data = _read(fd, 65536)
        except (BlockingIOError, InterruptedError):
            return b"".join(chunks), False
        except OSError:
            return b"".join(chunks), True
        if not data:
            return b"".join(chunks), True
        chunks.append(data)


class Popen:
    """Sous-ensemble de l'API ``subprocess.Popen`` suffisant pour pydub."""

    def __init__(self, args, stdin=None, stdout=None, stderr=None, **_ignored):
        self.args = list(args)
        self.returncode = None
        self._stdin_fd = None
        actions = []
        parent_close = []

        # Entrée standard
        if stdin == PIPE:
            read_fd, write_fd = _pipe()
            actions.append((_os.POSIX_SPAWN_DUP2, read_fd, 0))
            actions.append((_os.POSIX_SPAWN_CLOSE, read_fd))
            parent_close.append(read_fd)
            self._stdin_fd = write_fd
            _set_nonblocking(write_fd)
        elif hasattr(stdin, "fileno"):
            actions.append((_os.POSIX_SPAWN_DUP2, stdin.fileno(), 0))

        # Sortie standard
        self._stdout_fd = None
        if stdout == PIPE:
            read_fd, write_fd = _pipe()
            actions.append((_os.POSIX_SPAWN_DUP2, write_fd, 1))
            actions.append((_os.POSIX_SPAWN_CLOSE, write_fd))
            parent_close.append(write_fd)
            self._stdout_fd = read_fd
            _set_nonblocking(read_fd)
        elif hasattr(stdout, "fileno"):
            actions.append((_os.POSIX_SPAWN_DUP2, stdout.fileno(), 1))

        # Sortie d'erreur
        self._stderr_fd = None
        if stderr == STDOUT:
            actions.append((_os.POSIX_SPAWN_DUP2, 1, 2))
        elif stderr == PIPE:
            read_fd, write_fd = _pipe()
            actions.append((_os.POSIX_SPAWN_DUP2, write_fd, 2))
            actions.append((_os.POSIX_SPAWN_CLOSE, write_fd))
            parent_close.append(write_fd)
            self._stderr_fd = read_fd
            _set_nonblocking(read_fd)
        elif hasattr(stderr, "fileno"):
            actions.append((_os.POSIX_SPAWN_DUP2, stderr.fileno(), 2))

        file_actions = actions if actions else None
        env = {key: str(value) for key, value in _os.environ.items()}
        # Les tubes sont créés avec O_CLOEXEC ; les actions dup2+close sont
        # résolues côté enfant. Les extrémités inutiles au parent ne sont
        # fermées qu'APRÈS le spawn (elles doivent exister à ce moment-là).
        self.pid = _posix_spawnp(
            self.args[0], [str(a) for a in self.args], env,
            file_actions=file_actions,
        )
        for fd in parent_close:
            try:
                _close(fd)
            except OSError:
                pass

    def communicate(self, input=None, timeout=None):  # noqa: A002, ARG002
        want_stdout = self._stdout_fd is not None
        want_stderr = self._stderr_fd is not None
        stdin_view = memoryview(input) if input else memoryview(b"")
        stdout_chunks, stderr_chunks = [], []
        stdout_done = not want_stdout
        stderr_done = not want_stderr
        stdin_done = self._stdin_fd is None
        stall = 0

        while not (stdout_done and stderr_done and stdin_done):
            if not stdin_done and self._stdin_fd is not None:
                try:
                    if stdin_view:
                        written = _write(self._stdin_fd, stdin_view)
                        stdin_view = stdin_view[written:]
                    if not stdin_view:
                        _close(self._stdin_fd)
                        self._stdin_fd = None
                        stdin_done = True
                except (BlockingIOError, InterruptedError):
                    pass
                except OSError:
                    try:
                        _close(self._stdin_fd)
                    except OSError:
                        pass
                    self._stdin_fd = None
                    stdin_done = True

            if not stdout_done:
                data, closed = _drain(self._stdout_fd)
                if data:
                    stdout_chunks.append(data)
                if closed:
                    self._stdout_fd = None
                    stdout_done = True

            if not stderr_done:
                data, closed = _drain(self._stderr_fd)
                if data:
                    stderr_chunks.append(data)
                if closed:
                    self._stderr_fd = None
                    stderr_done = True

            if stdout_done and stderr_done and stdin_done:
                break
            # Garde-fou : ~10 min sans aucune progression
            stall += 1
            if timeout is not None and stall > timeout / 0.02:
                break
            _sleep(0.02)

        self.wait()
        return (
            b"".join(stdout_chunks) if want_stdout else None,
            b"".join(stderr_chunks) if want_stderr else None,
        )

    def wait(self):
        if self.returncode is None:
            _pid, status = _waitpid(self.pid, 0)
            if _os.WIFEXITED(status):
                self.returncode = _os.WEXITSTATUS(status)
            elif _os.WIFSIGNALED(status):
                self.returncode = -_os.WTERMSIG(status)
            else:
                self.returncode = status
        return self.returncode

    def poll(self):
        if self.returncode is None:
            try:
                _pid, status = _waitpid(self.pid, _os.WNOHANG)
                if _pid == 0:
                    return None
                if _os.WIFEXITED(status):
                    self.returncode = _os.WEXITSTATUS(status)
                elif _os.WIFSIGNALED(status):
                    self.returncode = -_os.WTERMSIG(status)
            except ChildProcessError:
                self.returncode = -1
        return self.returncode

    def _signal(self, sig):
        try:
            _kill(self.pid, sig)
        except OSError:
            pass

    def terminate(self):
        self._signal(_os.SIGTERM)

    def kill(self):
        self._signal(_os.SIGKILL)
