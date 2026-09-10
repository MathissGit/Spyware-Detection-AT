"""Tests unitaires gui/sandbox_client.py : toutes les branches."""
import io
import json
import subprocess
import threading

import pytest

from gui.sandbox_client import SandboxClient, SandboxError


class TestEnsureUp:
    def test_vm_running(self, monkeypatch):
        class FakeProc:
            returncode = 0
            stdout = "12345,,state,running\n"
            stderr = ""
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeProc())
        client = SandboxClient(root="/tmp")
        assert client.ensure_up() is True

    def test_vagrant_not_found(self, monkeypatch):
        def raise_fnf(*a, **kw):
            raise FileNotFoundError("vagrant")
        monkeypatch.setattr(subprocess, "run", raise_fnf)
        client = SandboxClient(root="/tmp")
        with pytest.raises(SandboxError, match="introuvable"):
            client.ensure_up()

    def test_vagrant_timeout(self, monkeypatch):
        def raise_to(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="vagrant", timeout=30)
        monkeypatch.setattr(subprocess, "run", raise_to)
        client = SandboxClient(root="/tmp")
        with pytest.raises(SandboxError, match="timeout"):
            client.ensure_up()

    def test_non_zero_rc(self, monkeypatch):
        class FakeProc:
            returncode = 1
            stdout = ""
            stderr = "error"
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeProc())
        client = SandboxClient(root="/tmp")
        with pytest.raises(SandboxError, match="échoué"):
            client.ensure_up()

    def test_not_running(self, monkeypatch):
        class FakeProc:
            returncode = 0
            stdout = "12345,,state,stopped\n"
            stderr = ""
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeProc())
        client = SandboxClient(root="/tmp")
        with pytest.raises(SandboxError, match="pas démarrée"):
            client.ensure_up()


class TestLastJson:
    def test_valid_json(self):
        out = "line1\nRESULT_JSON {\"ok\": true}\n"
        data = SandboxClient.last_json(out)
        assert data["ok"] is True

    def test_json_with_extra(self):
        out = "RESULT_JSON {\"ok\": false, \"error\": \"fail\"}\n"
        data = SandboxClient.last_json(out)
        assert data["ok"] is False
        assert data["error"] == "fail"

    def test_no_json(self):
        out = "some output\nno json here\n"
        assert SandboxClient.last_json(out) is None

    def test_invalid_json(self):
        out = "RESULT_JSON {invalid json}\n"
        assert SandboxClient.last_json(out) is None

    def test_empty_string(self):
        assert SandboxClient.last_json("") is None

    def test_multiple_json_last_wins(self):
        out = "RESULT_JSON {\"a\": 1}\nRESULT_JSON {\"b\": 2}\n"
        data = SandboxClient.last_json(out)
        assert data["b"] == 2


class TestDetectAndroid:
    def test_found(self, monkeypatch):
        result_json = json.dumps({"found": True, "msg": "OK", "imei": "123"})
        monkeypatch.setattr(
            SandboxClient, "run",
            lambda self, sub, **kw: (0, f"RESULT_JSON {result_json}"))
        client = SandboxClient(root="/tmp")
        found, msg, imei = client.detect_android()
        assert found is True
        assert imei == "123"

    def test_not_found(self, monkeypatch):
        result_json = json.dumps({"found": False, "msg": "Aucun"})
        monkeypatch.setattr(
            SandboxClient, "run",
            lambda self, sub, **kw: (0, f"RESULT_JSON {result_json}"))
        client = SandboxClient(root="/tmp")
        found, msg, imei = client.detect_android()
        assert found is False
        assert "Aucun" in msg


class TestDetectIos:
    def test_found(self, monkeypatch):
        result_json = json.dumps({"found": True, "msg": "iOS OK", "imei": "999"})
        monkeypatch.setattr(
            SandboxClient, "run",
            lambda self, sub, **kw: (0, f"RESULT_JSON {result_json}"))
        client = SandboxClient(root="/tmp")
        found, msg, imei = client.detect_ios()
        assert found is True
        assert imei == "999"

    def test_not_found(self, monkeypatch):
        result_json = json.dumps({"found": False, "msg": "Rien"})
        monkeypatch.setattr(
            SandboxClient, "run",
            lambda self, sub, **kw: (0, f"RESULT_JSON {result_json}"))
        client = SandboxClient(root="/tmp")
        found, msg, imei = client.detect_ios()
        assert found is False


class TestAnalyze:
    def test_not_ok_raises(self, monkeypatch):
        result_json = json.dumps({"ok": False, "error": "VM crash"})
        monkeypatch.setattr(
            SandboxClient, "run",
            lambda self, sub, **kw: (1, f"RESULT_JSON {result_json}"))
        client = SandboxClient(root="/tmp")
        with pytest.raises(SandboxError, match="VM crash"):
            client.analyze("android", "pw")

    def test_ok_returns_data(self, monkeypatch):
        result_json = json.dumps({"ok": True, "imei": "789", "dump_dir": "dump",
                                  "mvt_out": "mvt", "log_file": "log.txt"})
        monkeypatch.setattr(
            SandboxClient, "run",
            lambda self, sub, **kw: (0, f"RESULT_JSON {result_json}"))
        client = SandboxClient(root="/tmp")
        result = client.analyze("android", "pw")
        assert result["ok"] is True
        assert result["imei"] == "789"

    def test_ios_passes_password(self, monkeypatch):
        captured = {}
        result_json = json.dumps({"ok": True, "imei": "x", "raw_dir": "r",
                                  "mvt_out": "m", "log_file": "l"})
        def fake_run(self, sub, password=None, **kw):
            captured["sub"] = sub
            captured["pwd"] = password
            return 0, f"RESULT_JSON {result_json}"
        monkeypatch.setattr(SandboxClient, "run", fake_run)
        client = SandboxClient(root="/tmp")
        client.analyze("ios", "mypassword")
        assert captured["sub"] == "analyze-ios"
        assert captured["pwd"] == "mypassword"

    def test_android_no_password(self, monkeypatch):
        captured = {}
        result_json = json.dumps({"ok": True, "imei": "x", "dump_dir": "d",
                                  "mvt_out": "m", "log_file": "l"})
        def fake_run(self, sub, password=None, **kw):
            captured["pwd"] = password
            return 0, f"RESULT_JSON {result_json}"
        monkeypatch.setattr(SandboxClient, "run", fake_run)
        client = SandboxClient(root="/tmp")
        client.analyze("android", "pw")
        assert captured["pwd"] is None

    def test_no_json_raises(self, monkeypatch):
        monkeypatch.setattr(
            SandboxClient, "run",
            lambda self, sub, **kw: (0, "no json here\n"))
        client = SandboxClient(root="/tmp")
        with pytest.raises(SandboxError, match="invalide"):
            client.analyze("android", "pw")


class TestRun:
    def test_basic_command(self, monkeypatch):
        class FakeProc:
            stdin = None
            returncode = 0
            stdout = io.StringIO("RESULT_JSON {\"ok\": true}\n")

            def wait(self, timeout=None):
                pass

        def fake_popen(cmd, **kw):
            return FakeProc()

        monkeypatch.setattr(subprocess, "Popen", fake_popen)
        client = SandboxClient(root="/tmp")
        rc, out = client.run("detect-android")
        assert rc == 0
        assert "RESULT_JSON" in out

    def test_stop_event_terminates(self, monkeypatch):
        stop = threading.Event()

        class FakeProc:
            returncode = 0
            stdout_lines = iter(["line1\n", "line2\n", "line3\n"])

            def __init__(self, **kw):
                self.stdin = None
                self.stdout = self
                self.returncode = 0

            def __iter__(self):
                return self

            def __next__(self):
                return next(self.stdout_lines)

            def wait(self, timeout=None):
                pass

            def terminate(self):
                self.returncode = -1

        def fake_popen(cmd, **kw):
            return FakeProc()

        monkeypatch.setattr(subprocess, "Popen", fake_popen)
        client = SandboxClient(root="/tmp")
        rc, out = client.run("detect-android", stop_event=stop)
        assert rc == 0

    def test_timeout_raises(self, monkeypatch):
        waits = {"n": 0}

        class FakeProc:
            stdin = None

            def __init__(self, **kw):
                self.returncode = 0
                self.stdout = iter(["ok\n"])

            def __iter__(self):
                return self.stdout

            def __next__(self):
                return next(self.stdout)

            def wait(self, timeout=None):
                waits["n"] += 1
                if waits["n"] == 1:
                    raise subprocess.TimeoutExpired(cmd="vagrant", timeout=timeout)
                self.returncode = 0

            def terminate(self):
                pass

            def communicate(self):
                return "", ""

        def fake_popen(cmd, **kw):
            return FakeProc()

        monkeypatch.setattr(subprocess, "Popen", fake_popen)
        client = SandboxClient(root="/tmp")
        with pytest.raises(SandboxError, match="timeout"):
            client.run("analyze-android", timeout=1)

    def test_live_cb(self, monkeypatch):
        lines = []
        class FakeProc:
            stdin = None

            def __init__(self, **kw):
                self.returncode = 0
                self.stdout = iter(["line1\n", "line2\n"])

            def __iter__(self):
                return self.stdout

            def __next__(self):
                return next(self.stdout)

            def wait(self, timeout=None):
                pass

        def fake_popen(cmd, **kw):
            return FakeProc()

        monkeypatch.setattr(subprocess, "Popen", fake_popen)
        client = SandboxClient(root="/tmp")
        rc, out = client.run("detect-android", live_cb=lines.append)
        assert "line1" in lines
        assert "line2" in lines

    def test_password_written(self, monkeypatch):
        written = []
        class FakePipe:
            def write(self, data):
                written.append(data)
            def close(self):
                pass

        class FakeProc:
            returncode = 0

            def __init__(self, **kw):
                self.stdin = FakePipe() if kw.get("stdin") == subprocess.PIPE else None
                self.stdout = iter(["ok\n"])

            def __iter__(self):
                return self.stdout

            def __next__(self):
                return next(self.stdout)

            def wait(self, timeout=None):
                pass

        def fake_popen(cmd, **kw):
            return FakeProc(**kw)

        monkeypatch.setattr(subprocess, "Popen", fake_popen)
        client = SandboxClient(root="/tmp")
        rc, out = client.run("analyze-ios", password="secret")
        assert any("secret" in w for w in written)
