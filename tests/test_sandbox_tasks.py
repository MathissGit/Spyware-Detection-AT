"""Tests unitaires scripts/sandbox_tasks.py : toutes les fonctions et commandes."""
import io
import json
import os
import sys
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
try:
    import sandbox_tasks as st
finally:
    sys.path.pop(0)


class TestResultEmit:
    def test_result_output(self, capsys):
        st._result({"found": True, "imei": "123"})
        out = capsys.readouterr().out
        assert out.startswith("RESULT_JSON ")
        data = json.loads(out[len("RESULT_JSON "):].strip())
        assert data == {"found": True, "imei": "123"}

    def test_emit_output(self, capsys):
        st._emit("hello sandbox")
        assert "hello sandbox" in capsys.readouterr().out

    def test_result_json_valid(self, capsys):
        d = {"ok": True, "nested": {"a": [1, 2]}}
        st._result(d)
        line = capsys.readouterr().out.strip()
        parsed = json.loads(line[len("RESULT_JSON "):])
        assert parsed == d


class TestBinHelpers:
    def test_bin_local_priority(self, monkeypatch):
        monkeypatch.setattr(st.os.path, "exists", lambda p: p == "/usr/local/bin/foo")
        assert st._bin("foo") == "/usr/local/bin/foo"

    def test_bin_fallback(self, monkeypatch):
        monkeypatch.setattr(st.os.path, "exists", lambda p: False)
        assert st._bin("foo") == "foo"

    def test_mvt_bin_local(self, monkeypatch, tmp_path):
        venv_bin = str(tmp_path / "venv_bin")
        os.makedirs(venv_bin)
        (tmp_path / "venv_bin" / "mvt-android").touch()
        monkeypatch.setattr(st, "VENV_BIN", venv_bin)
        monkeypatch.setattr(st.os.path, "exists", lambda p: "mvt-android" in p)
        result = st._mvt_bin("mvt-android")
        assert "mvt-android" in result

    def test_mvt_bin_fallback(self, monkeypatch):
        monkeypatch.setattr(st.os.path, "exists", lambda p: False)
        monkeypatch.setattr(st, "VENV_BIN", "/nonexistent")
        assert st._mvt_bin("mvt-android") == "mvt-android"


class TestAdbDevices:
    def test_no_devices(self, monkeypatch):
        class FakeProc:
            returncode = 0
            stdout = "List of devices attached\n\n"
        monkeypatch.setattr(st, "_run", lambda *a, **kw: FakeProc())
        assert st._adb_devices() is None

    def test_device_found(self, monkeypatch):
        def fake_run(cmd, **kw):
            class P:
                pass
            p = P()
            if "devices" in cmd:
                p.stdout = "List of devices attached\nABC123\tdevice\n"
            else:
                p.stdout = ""
            p.returncode = 0
            return p
        monkeypatch.setattr(st, "_run", fake_run)
        serial = st._adb_devices()
        assert serial == "ABC123"


class TestImeiAndroid:
    def test_from_service_call(self, monkeypatch):
        def fake_run(cmd, **kw):
            class P:
                returncode = 0
                stdout = "'359485060123456'"
            return P()
        monkeypatch.setattr(st, "_run", fake_run)
        assert st._imei_android("ABC123") == "359485060123456"

    def test_fallback_serialno(self, monkeypatch):
        def fake_run(cmd, **kw):
            class P:
                returncode = 0
                stdout = "SN987654321"
            return P()
        monkeypatch.setattr(st, "_run", fake_run)
        assert st._imei_android("ABC123") == "SN987654321"

    def test_unknown_on_exception(self, monkeypatch):
        def raise_fnf(*a, **kw):
            raise FileNotFoundError()
        monkeypatch.setattr(st, "_run", raise_fnf)
        assert st._imei_android("ABC123") == "UNKNOWN"


class TestImeiIos:
    def test_found(self, monkeypatch):
        class FakeProc:
            returncode = 0
            stdout = "359485060123456\n"
        monkeypatch.setattr(st, "_run", lambda *a, **k: FakeProc())
        monkeypatch.setattr(st.os.path, "exists", lambda p: True)
        assert st._imei_ios() == "359485060123456"

    def test_unknown(self, monkeypatch):
        class FakeProc:
            returncode = 1
            stdout = ""
        monkeypatch.setattr(st, "_run", lambda *a, **k: FakeProc())
        monkeypatch.setattr(st.os.path, "exists", lambda p: False)
        assert st._imei_ios() == "UNKNOWN"


class TestIocArgs:
    def test_adds_iocs(self, monkeypatch, tmp_path):
        iocs_dir = tmp_path / "mvt_iocs"
        iocs_dir.mkdir()
        (iocs_dir / "a.stix2").write_text("{}", encoding="utf-8")
        (iocs_dir / "b.stix2").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(st, "IDENTITY_DIR", str(iocs_dir))
        cmd = ["mvt-android", "check-androidqf"]
        result_cmd, iocs = st._ioc_args(cmd)
        assert len(iocs) == 2
        assert "--iocs" in result_cmd


class TestCommandFunctions:
    def test_detect_android_no_device(self, monkeypatch, capsys):
        monkeypatch.setattr(st, "_adb_devices", lambda: None)
        st.cmd_detect_android()
        out = capsys.readouterr().out
        assert "RESULT_JSON" in out
        data = json.loads(out.strip()[len("RESULT_JSON "):])
        assert data["found"] is False

    def test_detect_android_found(self, monkeypatch, capsys):
        monkeypatch.setattr(st, "_adb_devices", lambda: "SERIAL123")
        monkeypatch.setattr(st, "_imei_android", lambda s: "IMEI123")
        st.cmd_detect_android()
        out = capsys.readouterr().out
        data = json.loads(out.strip()[len("RESULT_JSON "):])
        assert data["found"] is True
        assert data["imei"] == "IMEI123"

    def test_detect_ios_not_found(self, monkeypatch, capsys):
        class FakeProc:
            returncode = 1
            stdout = ""
        monkeypatch.setattr(st, "_run", lambda *a, **k: FakeProc())
        monkeypatch.setattr(st.os.path, "exists", lambda p: False)
        st.cmd_detect_ios()
        out = capsys.readouterr().out
        data = json.loads(out.strip()[len("RESULT_JSON "):])
        assert data["found"] is False

    def test_detect_ios_found(self, monkeypatch, capsys):
        class FakeProc:
            returncode = 0
            stdout = "359485060123456"
        monkeypatch.setattr(st, "_run", lambda *a, **k: FakeProc())
        monkeypatch.setattr(st.os.path, "exists", lambda p: True)
        st.cmd_detect_ios()
        out = capsys.readouterr().out
        data = json.loads(out.strip()[len("RESULT_JSON "):])
        assert data["found"] is True


class TestMainDispatch:
    def test_no_args(self):
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "sandbox_tasks.py")],
            capture_output=True, text=True,
        )
        assert result.returncode == 2

    def test_invalid_command(self):
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "sandbox_tasks.py"),
             "nonexistent-cmd"],
            capture_output=True, text=True,
        )
        assert result.returncode == 2


class TestGlobalCommandsDict:
    def test_all_commands_registered(self):
        expected = {"detect-android", "detect-ios",
                    "analyze-android", "analyze-ios"}
        assert set(st.COMMANDS.keys()) == expected

    def test_all_commands_callable(self):
        for name, fn in st.COMMANDS.items():
            assert callable(fn), f"{name} n'est pas callable"
