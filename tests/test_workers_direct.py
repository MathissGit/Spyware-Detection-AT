"""Tests unitaires gui/workers.py : détection, extraction, emitters, InstallWorker."""
import io
import os
import re
import tarfile
import subprocess
import threading
import time

import pyAesCrypt
import pytest

import gui.workers as workers


class TestDetectAndroidDirect:
    def test_no_device_found(self, monkeypatch):
        class FakeProc:
            returncode = 0
            stdout = "List of devices attached\n\n"
            stderr = ""
        monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeProc())
        found, msg, imei = workers.detect_android_device(mode="direct")
        assert found is False
        assert "Aucun" in msg

    def test_device_found_with_imei(self, monkeypatch):
        def fake_run(cmd, **kw):
            class P:
                pass
            p = P()
            if cmd[0] == "adb" and "devices" in cmd:
                p.returncode = 0
                p.stdout = "List of devices attached\nABC123\tdevice\n"
                p.stderr = ""
            elif "iphonesubinfo" in cmd:
                p.returncode = 0
                p.stdout = "Parcel(...'359485060123456'...)"
                p.stderr = ""
            else:
                p.returncode = 0
                p.stdout = ""
                p.stderr = ""
            return p
        monkeypatch.setattr("subprocess.run", fake_run)
        found, msg, imei = workers.detect_android_device(mode="direct")
        assert found is True
        assert "ABC123" in msg

    def test_device_found_imei_fallback_serial(self, monkeypatch):
        def fake_run(cmd, **kw):
            class P:
                pass
            p = P()
            if "devices" in cmd:
                p.stdout = "List of devices attached\nSERIAL99\tdevice\n"
                p.stderr = ""
            elif "getprop" in cmd:
                p.stdout = "SERIAL99"
                p.stderr = ""
            else:
                p.stdout = "nothing"
                p.stderr = ""
            p.returncode = 0
            return p
        monkeypatch.setattr("subprocess.run", fake_run)
        found, msg, imei = workers.detect_android_device(mode="direct")
        assert found is True
        assert imei != ""

    def test_adb_not_installed(self, monkeypatch):
        def raise_fnf(*a, **kw):
            raise FileNotFoundError("adb")
        monkeypatch.setattr("subprocess.run", raise_fnf)
        found, msg, imei = workers.detect_android_device(mode="direct")
        assert found is False
        assert "Erreur" in msg or "ADB" in msg


class TestDetectIosDirect:
    def test_no_device(self, monkeypatch):
        class FakeProc:
            returncode = 1
            stdout = ""
        monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeProc())
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        found, msg, imei = workers.detect_ios_device(mode="direct")
        assert found is False

    def test_device_found(self, monkeypatch):
        class FakeProc:
            returncode = 0
            stdout = "359485060123456"
        monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeProc())
        monkeypatch.setattr(os.path, "exists", lambda p: True)
        found, msg, imei = workers.detect_ios_device(mode="direct")
        assert found is True


class TestDetectIosSandbox:
    def test_delegates_to_vm(self, monkeypatch):
        class FakeClient:
            def ensure_up(self): return True
            def detect_ios(self):
                return True, "iOS connecté", "111222333"
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", FakeClient)
        found, msg, imei = workers.detect_ios_device(mode="sandbox")
        assert found is True
        assert imei == "111222333"


class TestExtractImei:
    def test_android(self, monkeypatch):
        monkeypatch.setattr(workers, "detect_android_device",
                            lambda **k: (True, "", "ANDROIDIMEI"))
        assert workers._extract_imei("android") == "ANDROIDIMEI"

    def test_ios(self, monkeypatch):
        monkeypatch.setattr(workers, "detect_ios_device",
                            lambda **k: (True, "", "IOSIMEI"))
        assert workers._extract_imei("ios") == "IOSIMEI"


class TestAnalysisWorkerCallbacks:
    def test_emit_progress(self):
        w = workers.AnalysisWorker.__new__(workers.AnalysisWorker)
        results = []
        w._progress_cb = lambda *a: results.append(a)
        w._emit_progress(0, "active", "1.2s")
        assert results[0] == (0, "active", "1.2s")

    def test_emit_log(self):
        w = workers.AnalysisWorker.__new__(workers.AnalysisWorker)
        results = []
        w._log_cb = results.append
        w._emit_log("hello")
        assert results[0] == "hello"

    def test_emit_activity(self):
        w = workers.AnalysisWorker.__new__(workers.AnalysisWorker)
        results = []
        w._activity_cb = results.append
        w._emit_activity("running")
        assert results[0] == "running"

    def test_no_callbacks_no_crash(self):
        w = workers.AnalysisWorker.__new__(workers.AnalysisWorker)
        w._progress_cb = None
        w._log_cb = None
        w._activity_cb = None
        w._emit_progress(0, "done")
        w._emit_log("msg")
        w._emit_activity("act")


class TestAnalysisWorkerCancel:
    def test_cancel_sets_event(self):
        w = workers.AnalysisWorker("android", "pw", "1")
        w.cancel()
        assert w.cancel_event.is_set()

    def test_cancel_stops_run_sandbox(self, monkeypatch):
        class FakeClient:
            def ensure_up(self): return True
            def detect_ios(self):
                return True, "iOS", "111"
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", FakeClient)
        w = workers.AnalysisWorker("android", "pw", "1", mode="sandbox")
        w.cancel()
        w.run()
        assert w.result is None


class TestAnalysisWorkerProperties:
    def test_result_and_error_initially_none(self):
        w = workers.AnalysisWorker("android", "pw", "1")
        assert w.result is None
        assert w.error is None

    def test_set_callbacks(self):
        w = workers.AnalysisWorker("android", "pw", "1")
        w.set_callbacks(progress_cb=lambda *a: None,
                        log_cb=lambda m: None,
                        activity_cb=lambda m: None)
        assert w._progress_cb is not None
        assert w._log_cb is not None
        assert w._activity_cb is not None


class TestAnalysisWorkerRunAndroid:
    def test_run_android_success(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setattr(workers, "LOCAL_DEST_DIR", str(tmp_path / "results"))

        dump_dir = tmp_path / "dump_real"
        mvt_dir = tmp_path / "dump_real_mvt_results"
        mvt_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "mvt_log.txt").write_text("no IoC found\n")

        call_count = {"n": 0}
        def fake_run(cmd, **kw):
            class P:
                returncode = 0
                stdout = ""
                stderr = ""
            if "androidqf" in " ".join(cmd):
                dump_dir.mkdir(exist_ok=True)
            return P()
        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr(workers, "_find_androidqf",
                            lambda: str(tmp_path / "androidqf"))
        monkeypatch.setattr(workers, "_extract_imei", lambda *a, **k: "ANDROIDIMEI")

        w = workers.AnalysisWorker("android", "pw", "1")
        logs = []
        w.set_callbacks(log_cb=logs.append)
        w.run()
        assert w.error is None, w.error
        assert w.result is not None
        assert w.result["imei"] == "ANDROIDIMEI"


class TestAnalysisWorkerRunIos:
    def test_run_ios_success(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setattr(workers, "LOCAL_DEST_DIR", str(tmp_path / "results"))
        monkeypatch.setattr(workers, "DATE_STR", "2026-01-01_12-00-00")

        imei_ios = "IOSIMEI123"
        raw_dir = tmp_path / f"dump_{imei_ios}_2026-01-01_12-00-00"
        raw_dir.mkdir()
        udid_dir = raw_dir / "UDID123"
        udid_dir.mkdir()

        def fake_run(cmd, **kw):
            class P:
                returncode = 0
                stdout = ""
                stderr = ""
            return P()
        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr(workers, "_extract_imei", lambda *a, **k: imei_ios)

        w = workers.AnalysisWorker("ios", "mypass", "1")
        logs = []
        w.set_callbacks(log_cb=logs.append)
        w.run()
        assert w.error is None, w.error
        assert w.result is not None
        assert w.result["imei"] == imei_ios


class TestAnalysisWorkerRunSandbox:
    def test_sandbox_success(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setattr(workers, "LOCAL_DEST_DIR", str(tmp_path / "results"))

        dump = tmp_path / "dump_x"
        dump.mkdir()
        mvt = tmp_path / "dump_x_mvt_results"
        mvt.mkdir()
        (tmp_path / "mvt_log.txt").write_text("no IoC found\n")

        class FakeClient:
            def __init__(self, **kw): pass
            def ensure_up(self): return True
            def analyze(self, *a, **kw):
                return {"ok": True, "imei": "SANDBOXIMEI",
                        "dump_dir": "dump_x", "mvt_out": "dump_x_mvt_results",
                        "log_file": "mvt_log.txt"}
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", FakeClient)

        w = workers.AnalysisWorker("android", "pw", "1", mode="sandbox")
        logs = []
        w.set_callbacks(log_cb=logs.append)
        w.run()
        assert w.error is None, w.error
        assert w.result["imei"] == "SANDBOXIMEI"
        assert not dump.exists()

    def test_sandbox_vm_down(self, monkeypatch):
        from gui.sandbox_client import SandboxError
        class FakeClient:
            def __init__(self, **kw): pass
            def ensure_up(self):
                raise SandboxError("VM hors ligne")
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", FakeClient)
        w = workers.AnalysisWorker("android", "pw", "1", mode="sandbox")
        w.run()
        assert w.error is not None
        assert "hors ligne" in w.error


class TestGenerateReportsWorkers:
    def test_no_match(self, tmp_path):
        log = tmp_path / "mvt_log.txt"
        log.write_text("INFO: no issues\n", encoding="utf-8")
        html, pdf = workers.AnalysisWorker._generate_reports(
            object(), str(log), "123456789012345")
        assert os.path.exists(html)
        assert os.path.getsize(html) > 0

    def test_pegasus_critical(self, tmp_path):
        log = tmp_path / "mvt_log.txt"
        log.write_text("CRITICAL: match found for pegasus indicator\n", encoding="utf-8")
        html, _ = workers.AnalysisWorker._generate_reports(
            object(), str(log), "ABC123")
        with open(html, encoding="utf-8") as f:
            content = f.read()
        assert "COMPROMIS" in content.upper()
        assert "Logiciels Espions Ciblés" in content

    def test_warning_only(self, tmp_path):
        log = tmp_path / "mvt_log.txt"
        log.write_text("WARNING: matched stix2 for some domain\n", encoding="utf-8")
        html, _ = workers.AnalysisWorker._generate_reports(
            object(), str(log), "IMEI")
        with open(html, encoding="utf-8") as f:
            content = f.read()
        assert "Domaines & Serveurs C2" in content

    def test_all_categories(self, tmp_path):
        lines = [
            "CRITICAL: match found for pegasus",
            "matched indicator for stalkerware app package",
            "matched stix2 malicious domain url",
            "match found for file hash abc123",
            "matched indicator for sms message",
            "indicator match: unknown ioc type",
        ]
        log = tmp_path / "mvt_log.txt"
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        html, _ = workers.AnalysisWorker._generate_reports(
            object(), str(log), "FULLTEST")
        with open(html, encoding="utf-8") as f:
            content = f.read()
        assert "COMPROMIS" in content.upper()


class TestSecurePackaging:
    def test_creates_aes_and_moves_reports(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "file.txt").write_text("data", encoding="utf-8")
        html = tmp_path / "Report_test.html"
        pdf = tmp_path / "Report_test.pdf"
        html.write_text("<html>report</html>", encoding="utf-8")
        pdf.write_bytes(b"%PDF-1.4 fake")
        workers.LOCAL_DEST_DIR = str(tmp_path / "results")

        w = object.__new__(workers.AnalysisWorker)
        w.password = "secret"
        w.dest_choice = "1"
        w.ext_dir = None

        primary = workers.AnalysisWorker._secure_packaging(
            w, [str(src)], "1234", str(html), str(pdf),
            str(tmp_path / "mvt_log.txt"))
        aes_files = [f for f in os.listdir(primary) if f.endswith(".aes")]
        assert len(aes_files) == 1
        assert os.path.exists(os.path.join(primary, os.path.basename(html)))
        assert os.path.exists(os.path.join(primary, os.path.basename(pdf)))

    def test_external_copy(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "f.txt").write_text("x", encoding="utf-8")
        ext = tmp_path / "ext"
        ext.mkdir()
        html = tmp_path / "Report_ext.html"
        pdf = tmp_path / "Report_ext.pdf"
        html.write_text("<html></html>", encoding="utf-8")
        pdf.write_bytes(b"%PDF-fake")
        workers.LOCAL_DEST_DIR = str(tmp_path / "local")

        w = object.__new__(workers.AnalysisWorker)
        w.password = "secret"
        w.dest_choice = "3"
        w.ext_dir = str(ext)

        primary = workers.AnalysisWorker._secure_packaging(
            w, [str(src)], "ABC", str(html), str(pdf),
            str(tmp_path / "log.txt"))
        ext_aes = [f for _, _, files in os.walk(str(ext)) for f in files
                   if f.endswith(".aes")]
        assert len(ext_aes) == 1
        assert os.path.exists(primary)


class TestInstallWorker:
    def test_windows_unsupported(self, monkeypatch):
        monkeypatch.setattr(workers, "SYSTEM", "Windows")
        w = workers.InstallWorker("sandbox", "/tmp")
        w.run()
        assert w.error is not None
        assert "Windows" in w.error

    def test_script_not_found(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SYSTEM", "Linux")
        w = workers.InstallWorker("sandbox", str(tmp_path))
        w.run()
        assert w.error is not None
        assert "introuvable" in w.error

    def test_callback_receives_messages(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SYSTEM", "Linux")
        messages = []
        w = workers.InstallWorker("sandbox", "/nonexistent", callback=messages.append)
        w._emit("test message")
        assert "test message" in messages


class TestFindAndroidqf:
    def test_finds_binary(self, monkeypatch, tmp_path):
        (tmp_path / "androidqf_linux").touch()
        monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setattr(workers.os.path, "join", os.path.join)
        result = workers._find_androidqf()
        assert "androidqf" in result

    def test_fallback(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setattr(workers.glob, "glob", lambda p: [])
        result = workers._find_androidqf()
        assert "androidqf" in result
