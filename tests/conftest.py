import os
import sys
import subprocess
import json
import shutil
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.join(PROJECT_ROOT, ".venv_tests", "bin", "python")
FALLBACK_PY = sys.executable


def _running_python():
    """Interpréteur à utiliser pour lancer les exécutables du projet."""
    candidates = [
        VENV_PY,
        os.path.join(PROJECT_ROOT, ".venv_forensics", "bin", "python"),
        FALLBACK_PY,
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return cand
    return FALLBACK_PY


PY = _running_python()


def write_temp_json(tmp_path, data):
    p = tmp_path / "data.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture(scope="session", autouse=True)
def stable_ctk():
    """Évite la récursion update_idletasks de CTkScrollbar sous les tests GUI."""
    try:
        from customtkinter.windows.widgets.ctk_scrollbar import CTkScrollbar
    except Exception:
        yield
        return
    orig_draw = CTkScrollbar._draw
    CTkScrollbar._draw = lambda self: None
    try:
        yield
    finally:
        CTkScrollbar._draw = orig_draw


@pytest.fixture(scope="session")
def ctk_root():
    """Racine CTk partagée pour les tests GUI (DISPLAY=:0 requis)."""
    import customtkinter as ctk
    root = ctk.CTk()
    root.withdraw()
    root.update()
    yield root
    root.destroy()


@pytest.fixture
def patch_subprocess(monkeypatch):
    """Renvoie un helper pour mock subprocess.run leicht."""
    def _patch(returncode=0, stdout="", stderr="", side_effect=None):
        class FakeProc:
            returncode = returncode
            stdout = stdout
            stderr = stderr
        if side_effect:
            monkeypatch.setattr("subprocess.run", side_effect)
        else:
            monkeypatch.setattr("subprocess.run",
                                lambda *a, **k: FakeProc())
    return _patch


# ==========================================================
# Détection de matériel pour les tests d'intégration réels.
# Les tests marqués @pytest.mark.real_android / real_ios sont
# automatiquement ignorés quand aucun appareil n'est branché,
# afin que la suite reste 100 % verte à chaque modification.
# ==========================================================

_ADB = shutil.which("adb") or "adb"
_IDEVICE_ID = shutil.which("idevice_id") or "idevice_id"


def android_device_present():
    """Renvoie True si au moins un appareil Android est branché."""
    try:
        res = subprocess.run(
            [_ADB, "devices"], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return False
    for line in res.stdout.splitlines()[1:]:
        if line.strip() and "\tdevice" in line:
            return True
    return False


def ios_device_present():
    """Renvoie True si au moins un appareil iOS est branché."""
    try:
        res = subprocess.run(
            [_IDEVICE_ID, "-l"], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(res.stdout.strip())


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    """Auto-skip des tests d'intégration réels sans matériel branché."""
    skip_android = not android_device_present()
    skip_ios = not ios_device_present()
    if not (skip_android or skip_ios):
        return
    for item in items:
        if skip_android and item.get_closest_marker("real_android"):
            item.add_marker(
                pytest.mark.skipif(
                    True, reason="Aucun appareil Android branché"
                )
            )
        if skip_ios and item.get_closest_marker("real_ios"):
            item.add_marker(
                pytest.mark.skipif(
                    True, reason="Aucun appareil iOS branché"
                )
            )