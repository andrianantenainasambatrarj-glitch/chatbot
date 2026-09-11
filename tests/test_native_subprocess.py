"""Lanceur de sous-processus natif (utilisé avec gevent en production)."""

import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="native_subprocess ne sert que sous gevent/Linux"
)

np = pytest.importorskip("native_subprocess")


def test_capture_sortie_standard_et_erreur():
    proc = np.Popen(
        [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)"],
        stdout=np.PIPE,
        stderr=np.PIPE,
    )
    out, err = proc.communicate()
    assert out.strip() == b"out"
    assert err.strip() == b"err"
    assert proc.returncode == 0


def test_envoi_donnees_par_stdin():
    proc = np.Popen(
        [
            sys.executable,
            "-c",
            "import sys; data = sys.stdin.buffer.read(); "
            "sys.stdout.buffer.write(str(len(data)).encode())",
        ],
        stdin=np.PIPE,
        stdout=np.PIPE,
        stderr=np.PIPE,
    )
    out, _err = proc.communicate(input=b"a" * 200_000)
    assert out == b"200000"
    assert proc.returncode == 0


def test_code_de_retour_propage():
    proc = np.Popen(
        [sys.executable, "-c", "import sys; print('boom', file=sys.stderr); sys.exit(3)"],
        stdout=np.PIPE,
        stderr=np.PIPE,
    )
    _out, err = proc.communicate()
    assert proc.returncode == 3
    assert b"boom" in err


def test_lecture_concurrente_deux_tubes():
    # Les deux tubes se remplissent en même temps : pas de blocage de canal.
    proc = np.Popen(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "for _ in range(2000): print('x' * 1000)\n"
            "for _ in range(1000): print('y', file=sys.stderr)",
        ],
        stdout=np.PIPE,
        stderr=np.PIPE,
    )
    out, err = proc.communicate(timeout=30)
    assert len(out) > 1_000_000
    assert len(err) > 500
    assert proc.returncode == 0
