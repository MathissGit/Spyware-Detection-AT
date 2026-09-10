"""Tests unitaires des commandes analyze de scripts/sandbox_tasks.py."""
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


class _Ok:
    returncode = 0
    stdout = ""
    stderr = ""


def _last_result(output):
    for line in reversed(output.splitlines()):
        if line.startswith("RESULT_JSON "):
            return json.loads(line[len("RESULT_JSON "):])
    raise AssertionError(f"RESULT_JSON absent dans: {output!r}")


class TestAnalyzeAndroid:
    def test_androidqf_missing(self, monkeypatch, capsys):
        monkeypatch.setattr(st, "_adb_devices", lambda: "SER")
        monkeypatch.setattr(st, "_imei_android", lambda s: "IMEI")
        monkeypatch.setattr(st.glob, "glob", lambda p: [])
        st.cmd_analyze_android()
        data = _last_result(capsys.readouterr().out)
        assert data["ok"] is False
        assert "AndroidQF" in data["error"]

    def test_androidqf_fail(self, monkeypatch, capsys, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(st, "_adb_devices", lambda: "SER")
        monkeypatch.setattr(st, "_imei_android", lambda s: "IMEI")
        monkeypatch.setattr(st.glob, "glob", lambda p: ["androidqf_linux"])
        monkeypatch.setattr(st.os, "chdir", lambda p: None)
        monkeypatch.setattr(st, "VM_ROOT", str(tmp_path))

        def fake_run(*a, **kw):
            raise subprocess.CalledProcessError(1, a[0])
        monkeypatch.setattr(st.subprocess, "run", fake_run)
        monkeypatch.setattr(st, "_sudo", lambda cmd: cmd)
        st.cmd_analyze_android()
        data = _last_result(capsys.readouterr().out)
        assert data["ok"] is False
        assert "AndroidQF" in data["error"]

    def test_no_dump_dir(self, monkeypatch, capsys, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(st, "_adb_devices", lambda: "SER")
        monkeypatch.setattr(st, "_imei_android", lambda s: "IMEI")
        monkeypatch.setattr(st.glob, "glob", lambda p: ["androidqf_linux"])
        monkeypatch.setattr(st.os, "chdir", lambda p: None)
        monkeypatch.setattr(st, "VM_ROOT", str(tmp_path))
        monkeypatch.setattr(st.subprocess, "run", lambda *a, **kw: _Ok())
        monkeypatch.setattr(st, "_sudo", lambda cmd: cmd)
        monkeypatch.setattr(st.os, "walk", lambda p: iter([(".", ["pre_existing"], [])]))
        st.cmd_analyze_android()
        data = _last_result(capsys.readouterr().out)
        assert data["ok"] is False
        assert "dump" in data["error"]

    def test_success(self, monkeypatch, capsys, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(st, "_adb_devices", lambda: "SER")
        monkeypatch.setattr(st, "_imei_android", lambda s: "IMEI123")
        monkeypatch.setattr(st.glob, "glob", lambda p: ["androidqf_linux"])
        monkeypatch.setattr(st.os, "chdir", lambda p: None)
        monkeypatch.setattr(st, "VM_ROOT", str(tmp_path))
        monkeypatch.setattr(st.subprocess, "run", lambda *a, **kw: _Ok())
        monkeypatch.setattr(st, "_sudo", lambda cmd: cmd)
        monkeypatch.setattr(st, "_mvt_bin", lambda name: name)
        monkeypatch.setattr(
            st, "_ioc_args",
            lambda cmd: (cmd + ["--iocs", "x.stix2"], ["x.stix2"]))

        os.makedirs(tmp_path / "dump_x", exist_ok=True)
        (tmp_path / "dump_x" / "files.csv").write_text("a,b\n", encoding="utf-8")

        walk_calls = {"n": 0}
        def fake_walk(path):
            walk_calls["n"] += 1
            if walk_calls["n"] == 1:
                yield ".", [], []
            else:
                yield ".", ["dump_x"], []
        monkeypatch.setattr(st.os, "walk", fake_walk)

        st.cmd_analyze_android()
        data = _last_result(capsys.readouterr().out)
        assert data["ok"] is True
        assert data["imei"] == "IMEI123"
        assert data["dump_dir"] == "dump_x"


class TestAnalyzeIos:
    def test_pairing_timeout(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(st.sys, "stdin", io.StringIO("mypassword\n"))

        class FakeProc:
            returncode = 1
            stdout = ""
        monkeypatch.setattr(st, "_run", lambda *a, **k: FakeProc())
        monkeypatch.setattr(st, "_imei_ios", lambda: "UNKNOWN")
        monkeypatch.setattr(st, "_bin", lambda n: n)
        vals = {"n": 0}
        def fake_monotonic():
            vals["n"] += 1
            return 1.0 if vals["n"] == 1 else 100000.0
        monkeypatch.setattr(st.time, "monotonic", fake_monotonic)
        monkeypatch.setattr(st.time, "sleep", lambda s: None)
        st.cmd_analyze_ios()
        data = _last_result(capsys.readouterr().out)
        assert data["ok"] is False
        assert "120" in data["error"]

    def test_encryption_error(self, monkeypatch, capsys, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(st.sys, "stdin", io.StringIO("mypassword\n"))

        calls = {"n": 0}
        class FakeProc:
            returncode = 1
            stdout = ""
            stderr = ""
        class NiceProc:
            returncode = 0
            stdout = ""
            stderr = ""
        def fake_run(cmd, **kw):
            calls["n"] += 1
            if calls["n"] <= 1:
                return NiceProc()
            return FakeProc()

        monkeypatch.setattr(st, "_run", fake_run)
        monkeypatch.setattr(st.time, "sleep", lambda s: None)
        monkeypatch.setattr(st, "_imei_ios", lambda: "IMEI")
        monkeypatch.setattr(st, "_bin", lambda n: n)
        monkeypatch.setattr(st, "VM_ROOT", str(tmp_path))
        monkeypatch.setattr(st.os, "chdir", lambda p: None)
        st.cmd_analyze_ios()
        data = _last_result(capsys.readouterr().out)
        assert data["ok"] is False
        assert "chiffrement" in data["error"]

    def test_backup_fail(self, monkeypatch, capsys, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(st.sys, "stdin", io.StringIO("mypassword\n"))
        monkeypatch.setattr(st, "_run", lambda *a, **k: _Ok())
        monkeypatch.setattr(st, "_imei_ios", lambda: "IMEI")
        monkeypatch.setattr(st, "_bin", lambda n: n)
        monkeypatch.setattr(st.os, "chdir", lambda p: None)

        def fake_run(*a, **kw):
            raise subprocess.CalledProcessError(5, a[0])
        monkeypatch.setattr(st.subprocess, "run", fake_run)
        monkeypatch.setattr(st, "_sudo", lambda cmd: cmd)
        st.cmd_analyze_ios()
        data = _last_result(capsys.readouterr().out)
        assert data["ok"] is False
        assert "sauvegarde" in data["error"]

    def test_udid_missing(self, monkeypatch, capsys, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(st.sys, "stdin", io.StringIO("mypassword\n"))
        monkeypatch.setattr(st, "_run", lambda *a, **k: _Ok())
        monkeypatch.setattr(st, "_imei_ios", lambda: "SERIES9IMEI")
        monkeypatch.setattr(st, "_bin", lambda n: n)
        monkeypatch.setattr(st.os, "chdir", lambda p: None)
        monkeypatch.setattr(st.subprocess, "run", lambda *a, **kw: _Ok())
        monkeypatch.setattr(st, "_sudo", lambda cmd: cmd)
        monkeypatch.setattr(st.os, "walk", lambda p: iter([]))
        st.DATE_STR = "2026-01-01_00-00-00"
        st.cmd_analyze_ios()
        data = _last_result(capsys.readouterr().out)
        assert data["ok"] is False
        assert "UDID" in data["error"]

    def test_success(self, monkeypatch, capsys, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(st.sys, "stdin", io.StringIO("mypassword\n"))
        monkeypatch.setattr(st, "_run", lambda *a, **k: _Ok())
        monkeypatch.setattr(st, "_imei_ios", lambda: "IOSIMEI")
        monkeypatch.setattr(st, "_bin", lambda n: n)
        monkeypatch.setattr(st.os, "chdir", lambda p: None)
        monkeypatch.setattr(st.subprocess, "run", lambda *a, **kw: _Ok())
        monkeypatch.setattr(st, "_sudo", lambda cmd: cmd)
        monkeypatch.setattr(st, "_mvt_bin", lambda name: name)
        monkeypatch.setattr(
            st, "_ioc_args",
            lambda cmd: (cmd + ["--iocs", "x.stix2"], ["x.stix2"]))

        raw_dir = f"dump_IOSIMEI_{st.DATE_STR}"
        os.makedirs(tmp_path / raw_dir / "UDID123", exist_ok=True)

        st.cmd_analyze_ios()
        data = _last_result(capsys.readouterr().out)
        assert data["ok"] is True
        assert data["imei"] == "IOSIMEI"


class TestMainErrorPath:
    def test_command_exception_emits_error(self, monkeypatch, capsys):
        def boom():
            raise RuntimeError("kaboom")
        monkeypatch.setitem(st.COMMANDS, "detect-android", boom)
        monkeypatch.setattr(sys, "argv", ["sandbox_tasks.py", "detect-android"])
        with pytest.raises(SystemExit) as exc:
            st.main()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        data = _last_result(out)
        assert data["ok"] is False
        assert "kaboom" in data["error"]

    def test_valid_command_no_error(self, monkeypatch, capsys):
        called = {"n": 0}
        def ok():
            called["n"] += 1
        monkeypatch.setitem(st.COMMANDS, "detect-android", ok)
        monkeypatch.setattr(sys, "argv", ["sandbox_tasks.py", "detect-android"])
        st.main()
        assert called["n"] == 1