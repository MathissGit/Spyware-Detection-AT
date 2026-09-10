"""Tests de non-régression pour la séparation hôte / VM (mode sandbox)."""
import io
import os
import pytest
import conftest
import gui.workers as workers
from gui.sandbox_client import SandboxClient, SandboxError


def test_last_json_parsing():
    """La dernière ligne RESULT_JSON doit être extraite et parsée."""
    out = "ligne journal\nRESULT_JSON {\"found\": true, \"imei\": \"123\"}\n"
    data = SandboxClient.last_json(out)
    assert data == {"found": True, "imei": "123"}


def test_last_json_no_result():
    """Sans RESULT_JSON, last_json doit renvoyer None."""
    assert SandboxClient.last_json("rien du tout\n") is None


def test_last_json_invalid():
    """Un RESULT_JSON invalide doit être ignoré proprement."""
    out = "RESULT_JSON {pas du json\n"
    assert SandboxClient.last_json(out) is None


class _FakeClientDown:
    def __init__(self, root=None):
        pass

    def ensure_up(self):
        raise SandboxError("La VM sandbox n'est pas démarrée.")


class _FakeClientUp:
    def __init__(self, root=None):
        self.ensure_called = False

    def ensure_up(self):
        self.ensure_called = True
        return True

    def detect_ios(self):
        return True, "iOS/Appareil connecté", "999999999999999"


def test_detect_android_sandbox_vm_down(monkeypatch):
    """VM arrêtée -> détection Android sandbox doit renvoyer un message clair."""
    monkeypatch.setattr("gui.sandbox_client.SandboxClient", _FakeClientDown)
    found, msg, imei = workers.detect_android_device(mode="sandbox")
    assert found is False
    assert "pas démarrée" in msg
    assert imei == ""


def test_detect_ios_sandbox_uses_vm(monkeypatch):
    """VM opérationnelle -> la détection iOS est déléguée à la VM."""
    monkeypatch.setattr("gui.sandbox_client.SandboxClient", _FakeClientUp)
    found, msg, imei = workers.detect_ios_device(mode="sandbox")
    assert found is True
    assert imei == "999999999999999"


def test_detect_android_default_direct(monkeypatch):
    """Sans mode sandbox, la détection reste locale (adb hôte)."""
    found, msg, imei = workers.detect_android_device(mode="direct")
    assert isinstance(found, bool)


def test_analysis_worker_sandbox_vm_down(monkeypatch):
    """VM non démarrée -> l'analyse sandbox échoue proprement."""
    monkeypatch.setattr("gui.sandbox_client.SandboxClient", _FakeClientDown)
    w = workers.AnalysisWorker("android", "pw", "1", mode="sandbox")
    logs = []
    w.set_callbacks(log_cb=logs.append)
    w.run()
    assert w.error is not None
    assert "pas démarrée" in w.error


def test_analysis_worker_sandbox_full_flow(monkeypatch, tmp_path):
    """Mode sandbox : extraction/MVT simulés dans la VM, rapport et archive
    AES produits côté hôte."""
    dump = tmp_path / "dump_x"
    mvt = tmp_path / "dump_x_mvt_results"
    dump.mkdir()
    mvt.mkdir()
    (tmp_path / "mvt_log.txt").write_text("INFO: no ioC found\n", encoding="utf-8")
    results_dir = tmp_path / "results"

    class _FakeClientAnalyze:
        def __init__(self, root=None):
            pass

        def ensure_up(self):
            return True

        def analyze(self, device_type, password, live_cb=None, stop_event=None,
                    timeout=None):
            if live_cb:
                live_cb("[sandbox] extraction simulée...")
            return {"ok": True, "imei": "12345", "dump_dir": "dump_x",
                    "mvt_out": "dump_x_mvt_results", "log_file": "mvt_log.txt"}

    monkeypatch.setattr("gui.sandbox_client.SandboxClient", _FakeClientAnalyze)
    monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
    monkeypatch.setattr(workers, "LOCAL_DEST_DIR", str(results_dir))

    w = workers.AnalysisWorker("android", "pw", "1", mode="sandbox")
    logs = []
    w.set_callbacks(log_cb=logs.append)
    w.run()
    assert w.error is None, w.error
    assert w.result is not None
    assert w.result["imei"] == "12345"
    # Archive AES produite dans results/ côté hôte
    aes_files = []
    for root, _, files in os.walk(str(results_dir)):
        aes_files += [f for f in files if f.endswith(".aes")]
    assert len(aes_files) == 1
    # Les dossiers bruts ont été purgés après packaging
    assert not dump.exists()
    assert not mvt.exists()


def test_run_remote_command_uses_venv_python_directly(monkeypatch):
    """La VM exécute l'interpréteur venv en premier, sans préfixe `python3`
    (sinon SyntaxError: Non-UTF-8 code starting with '\\x80' sur bin/python)."""
    captured = {}

    class _FakeProc:
        def __init__(self, argv=None, stdin=None, **kwargs):
            captured["argv"] = argv
            self.returncode = 0
            self.stdin = io.StringIO() if isinstance(stdin, int) else stdin

        @property
        def stdout(self):
            return iter(["RESULT_JSON {\"found\": false, \"msg\": \"x\", \"imei\": \"\"}\n"])

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: _FakeProc(*a, **k))
    client = SandboxClient(root="/tmp")
    rc, out = client.run("detect-ios")

    ssh_argv = captured["argv"]
    assert ssh_argv[0] == "vagrant" and ssh_argv[1] == "ssh"
    command = ssh_argv[ssh_argv.index("-c") + 1]
    # Interpréteur venv exécuté directement, pas en argument d'un `python3`.
    assert command.startswith("cd /vagrant &&")
    assert "'/opt/venv_forensics/bin/python' '/vagrant/scripts/sandbox_tasks.py' 'detect-ios'" in command
    assert "python3 " not in command
    assert rc == 0
    assert "RESULT_JSON" in out


def test_run_sends_password_on_first_stdin_line(monkeypatch):
    """Le mot de passe iOS passe par stdin (première ligne), jamais dans la
    commande ssh (invisible dans un listing de processus)."""
    captured = {}

    class _CaptureStdin:
        """Capture les écritures ; run() ferme le stdin en fin de tâche."""
        def __init__(self):
            self.writes = []

        def write(self, s):
            self.writes.append(s)

        def close(self):
            pass

    class _FakeProc:
        def __init__(self, argv=None, stdin=None, **kwargs):
            captured["argv"] = argv
            self.returncode = 0
            self.stdin = _CaptureStdin() if isinstance(stdin, int) else stdin
            captured["stdin"] = self.stdin

        @property
        def stdout(self):
            return iter([])

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: _FakeProc(*a, **k))
    client = SandboxClient(root="/tmp")
    client.run("analyze-ios", password="s3cret")

    ssh_argv = captured["argv"]
    command = ssh_argv[ssh_argv.index("-c") + 1]
    assert command.startswith("cd /vagrant &&")
    assert "'/opt/venv_forensics/bin/python' '/vagrant/scripts/sandbox_tasks.py' 'analyze-ios'" in command
    assert "s3cret" not in command
    assert captured["stdin"].writes == ["s3cret\n"]