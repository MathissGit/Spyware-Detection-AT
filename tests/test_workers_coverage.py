"""Couverture des branches manquantes de gui/workers.py."""
import os
import subprocess
import types

import xhtml2pdf
import pytest

import gui.workers as workers


class _P:
    returncode = 0
    stdout = ""
    stderr = ""

    def __init__(self, rc=0, out="", err=""):
        self.returncode = rc
        self.stdout = out
        self.stderr = err


class TestDetectSandboxBranches:
    def test_android_sandbox_success(self, monkeypatch):
        class C:
            def ensure_up(self): return True
            def detect_android(self): return True, "Android via VM", "VMIMEI"
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", C)
        found, msg, imei = workers.detect_android_device(mode="sandbox")
        assert found is True and imei == "VMIMEI"

    def test_android_ensure_up_error(self, monkeypatch):
        from gui.sandbox_client import SandboxError
        class C:
            def ensure_up(self): raise SandboxError("down")
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", C)
        found, msg, imei = workers.detect_android_device(mode="sandbox")
        assert found is False and "down" in msg

    def test_android_generic_error(self, monkeypatch):
        class C:
            def __init__(self): raise RuntimeError("ctor")
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", C)
        found, msg, imei = workers.detect_android_device(mode="sandbox")
        assert found is False and "Erreur sandbox" in msg

    def test_ios_ensure_up_error(self, monkeypatch):
        from gui.sandbox_client import SandboxError
        class C:
            def ensure_up(self): raise SandboxError("down")
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", C)
        found, msg, imei = workers.detect_ios_device(mode="sandbox")
        assert found is False

    def test_ios_generic_error(self, monkeypatch):
        class C:
            def __init__(self): raise RuntimeError("ctor")
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", C)
        found, msg, imei = workers.detect_ios_device(mode="sandbox")
        assert found is False and "Erreur sandbox" in msg


class TestDetectDirectEdgeBranches:
    def test_android_imei_read_error(self, monkeypatch):
        def fake_run(cmd, **kw):
            if "devices" in cmd:
                return _P(out="List:\nABC\tdevice\n")
            if "start-server" in cmd or "shell" in cmd:
                return _P()
            raise OSError("adb shell crash")
        monkeypatch.setattr("subprocess.run", fake_run)
        found, msg, imei = workers.detect_android_device(mode="direct")
        assert found is True and imei == "UNKNOWN"

    def test_ios_imei_info_error(self, monkeypatch):
        def fake_run(cmd, **kw):
            if "validate" in " ".join(cmd):
                return _P(rc=0)
            raise OSError("ideviceinfo crash")
        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        found, msg, imei = workers.detect_ios_device(mode="direct")
        assert found is True and imei == "UNKNOWN"

    def test_ios_run_error(self, monkeypatch):
        def boom(*a, **k): raise OSError("idevicepair")
        monkeypatch.setattr("subprocess.run", boom)
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        found, msg, imei = workers.detect_ios_device(mode="direct")
        assert found is False and "Erreur" in msg

    def test_android_no_devices(self, monkeypatch):
        monkeypatch.setattr("subprocess.run",
                            lambda *a, **k: _P(out="List of devices attached\n"))
        found, msg, imei = workers.detect_android_device(mode="direct")
        assert found is False and "Aucun appareil Android" in msg

    def test_android_imei_from_call(self, monkeypatch):
        def fake_run(cmd, **kw):
            if "devices" in cmd:
                return _P(out="List:\nXYZ\tdevice\n")
            if "service" in cmd:
                return _P(out="Result: ['1234567890123456']")
            return _P()
        monkeypatch.setattr("subprocess.run", fake_run)
        found, msg, imei = workers.detect_android_device(mode="direct")
        assert found is True and imei == "1234567890123456"

    def test_android_imei_from_getprop(self, monkeypatch):
        def fake_run(cmd, **kw):
            if "devices" in cmd:
                return _P(out="List:\nXYZ\tdevice\n")
            if "service" in cmd:
                return _P(out="Result: null")
            if "getprop" in cmd:
                return _P(out="SN12345")
            return _P()
        monkeypatch.setattr("subprocess.run", fake_run)
        found, msg, imei = workers.detect_android_device(mode="direct")
        assert found is True and imei == "SN12345"

    def test_android_imei_call_error(self, monkeypatch):
        def fake_run(cmd, **kw):
            if "devices" in cmd:
                return _P(out="List:\nXYZ\tdevice\n")
            if "service" in cmd:
                raise OSError("adb crash")
            return _P()
        monkeypatch.setattr("subprocess.run", fake_run)
        found, msg, imei = workers.detect_android_device(mode="direct")
        assert found is True and imei == "UNKNOWN"

    def test_android_adb_error(self, monkeypatch):
        def boom(*a, **k): raise OSError("adb absent")
        monkeypatch.setattr("subprocess.run", boom)
        found, msg, imei = workers.detect_android_device(mode="direct")
        assert found is False and "Erreur ADB" in msg

    def test_ios_sandbox_success(self, monkeypatch):
        class C:
            def ensure_up(self): return True
            def detect_ios(self): return True, "iOS via VM", "VMIMEI"
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", C)
        found, msg, imei = workers.detect_ios_device(mode="sandbox")
        assert found is True and imei == "VMIMEI"

    def test_ios_pair_then_validate(self, monkeypatch):
        calls = {"n": 0}
        def fake_run(cmd, **kw):
            if "validate" in " ".join(cmd):
                calls["n"] += 1
                return _P(rc=0 if calls["n"] >= 2 else 1)
            if "pair" in " ".join(cmd):
                return _P(rc=0)
            if "ideviceinfo" in " ".join(cmd):
                return _P(rc=0, out="IOSIMEI1")
            return _P()
        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        found, msg, imei = workers.detect_ios_device(mode="direct")
        assert found is True and imei == "IOSIMEI1"

    def test_ios_no_device(self, monkeypatch):
        def fake_run(cmd, **kw):
            if "validate" in " ".join(cmd):
                return _P(rc=1)
            return _P()
        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        found, msg, imei = workers.detect_ios_device(mode="direct")
        assert found is False and "Aucun appareil iOS" in msg


class TestExtractImei:
    def test_android_real_path(self, monkeypatch):
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _P())
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        assert workers._extract_imei("android") == ""

    def test_ios_real_path(self, monkeypatch):
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _P())
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        assert workers._extract_imei("ios") == "UNKNOWN"


class TestFindAndroidqf:
    def test_glob_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
        (tmp_path / "androidqf-linux").write_text("bin")
        assert workers._find_androidqf() == str(tmp_path / "androidqf-linux")

    def test_glob_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
        assert workers._find_androidqf() == str(tmp_path / "androidqf")


class TestAnalysisWorkerRunWrap:
    def test_run_generic_exception(self, monkeypatch):
        w = workers.AnalysisWorker("android", "pw", "1")
        def boom():
            raise RuntimeError("boom interne")
        monkeypatch.setattr(w, "_run_android", boom)
        logs = []
        w.set_callbacks(log_cb=logs.append)
        w.run()
        assert "boom interne" in str(w.error)
        assert any("ERREUR" in m for m in logs)


class TestEmitters:
    def test_emit_progress_with_callback(self):
        w = workers.AnalysisWorker("android", "pw", "1")
        seen = []
        w.set_callbacks(progress_cb=lambda s, st, el="": seen.append((s, st)))
        w._emit_progress(2, "active")
        assert seen == [(2, "active")]

    def test_emit_activity_with_callback(self):
        w = workers.AnalysisWorker("android", "pw", "1")
        seen = []
        w.set_callbacks(activity_cb=seen.append)
        w._emit_activity("log ligne")
        assert seen == ["log ligne"]


def _inject_cancel_at(w, step):
    """Annule le worker quand l'étape 'step' passe à 'done'."""
    real = w._emit_progress
    def injected(s, state, elapsed=""):
        if s == step and state == "done":
            w.cancel_event.set()
        real(s, state, elapsed)
    w._emit_progress = injected


class TestRunSandboxBranches:
    def _sig(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setattr(workers, "LOCAL_DEST_DIR", str(tmp_path / "results"))
        (tmp_path / "mvt_log.txt").write_text("no IoC found\n")

    def _client(self, monkeypatch, w, analyze_result=None, error=None, set_cancel=False):
        class C:
            def __init__(self, **kw): pass
            def ensure_up(self): return True
            def analyze(self, *a, **kw):
                if set_cancel:
                    w.cancel_event.set()
                if error:
                    raise error
                return analyze_result
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", C)

    def test_analyze_error(self, monkeypatch, tmp_path):
        from gui.sandbox_client import SandboxError
        self._sig(monkeypatch, tmp_path)
        w = workers.AnalysisWorker("android", "pw", "1", mode="sandbox")
        self._client(monkeypatch, w, error=SandboxError("analyse échouée"))
        w.run()
        assert "analyse échouée" in str(w.error)

    def test_cancel_after_analyze(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        w = workers.AnalysisWorker("android", "pw", "1", mode="sandbox")
        self._client(monkeypatch, w,
                     analyze_result={"imei": "I", "log_file": "mvt_log.txt",
                                     "dump_dir": "d", "mvt_out": "m",
                                     "raw_dir": "r"},
                     set_cancel=True)
        w.run()
        assert w.result is None and w.error is None

    def test_cancel_after_extraction(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        w = workers.AnalysisWorker("android", "pw", "1", mode="sandbox")
        self._client(monkeypatch, w,
                     analyze_result={"imei": "I", "log_file": "mvt_log.txt",
                                     "dump_dir": "d", "mvt_out": "m",
                                     "raw_dir": "r"})
        _inject_cancel_at(w, 1)
        w.run()
        assert w.result is None and w.error is None

    def test_cancel_at_step2(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        w = workers.AnalysisWorker("android", "pw", "1", mode="sandbox")
        self._client(monkeypatch, w,
                     analyze_result={"imei": "I", "log_file": "mvt_log.txt",
                                     "dump_dir": "d", "mvt_out": "m",
                                     "raw_dir": "r"})
        _inject_cancel_at(w, 2)
        w.run()
        assert w.result is None

    def test_cancel_after_reports(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        w = workers.AnalysisWorker("android", "pw", "1", mode="sandbox")
        self._client(monkeypatch, w,
                     analyze_result={"imei": "I", "log_file": "mvt_log.txt",
                                     "dump_dir": "d", "mvt_out": "m",
                                     "raw_dir": "r"})
        _inject_cancel_at(w, 3)
        w.run()
        assert w.result is None

    def test_ensure_up_error(self, monkeypatch, tmp_path):
        from gui.sandbox_client import SandboxError
        self._sig(monkeypatch, tmp_path)
        class C:
            def __init__(self, **kw): pass
            def ensure_up(self): raise SandboxError("vm down")
            def analyze(self, *a, **kw): raise AssertionError("must not run")
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", C)
        logs = []
        w = workers.AnalysisWorker("android", "pw", "1", mode="sandbox",
                                   ext_dir=None)
        w._emit_log = logs.append
        w.run()
        assert "vm down" in str(w.error)
        assert w.result is None

    def test_cancel_before_ensure_up(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        class C:
            def __init__(self, **kw): pass
            def ensure_up(self): return True
            def analyze(self, *a, **kw): raise AssertionError("must not run")
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", C)
        w = workers.AnalysisWorker("android", "pw", "1", mode="sandbox")
        w.cancel()
        w.run()
        assert w.result is None and w.error is None

    def _sandbox_success(self, monkeypatch, tmp_path, device):
        self._sig(monkeypatch, tmp_path)
        folders = {}
        if device == "android":
            folders = {"dump_dir": "dump_x", "mvt_out": "android_mvt_results"}
        else:
            folders = {"raw_dir": "raw_x", "mvt_out": "ios_mvt_results"}
        for d in folders.values():
            (tmp_path / d).mkdir(exist_ok=True)
        (tmp_path / "mvt_log.txt").write_text("no IoC found\n")
        activity = []

        class C:
            def __init__(self, **kw): pass
            def ensure_up(self): return True
            def analyze(self, *a, **kw):
                kw["live_cb"]("message sandbox")
                return dict(folders, imei="SBOXIMEI", log_file="mvt_log.txt")
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", C)

        progress = []
        logs = []
        w = workers.AnalysisWorker(device, "pw", "1", mode="sandbox")
        w._emit_progress = lambda s, st, el="": progress.append((s, st))
        w._emit_log = logs.append
        w._emit_activity = activity.append
        w.run()
        assert w.error is None, w.error
        assert w.result["imei"] == "SBOXIMEI"
        return w, progress, logs, activity

    def test_sandbox_success_android(self, monkeypatch, tmp_path):
        w, progress, logs, activity = self._sandbox_success(
            monkeypatch, tmp_path, "android")
        assert any(p[0] == 5 and p[1] == "done" for p in progress)

    def test_sandbox_success_ios(self, monkeypatch, tmp_path):
        w, progress, logs, activity = self._sandbox_success(
            monkeypatch, tmp_path, "ios")
        assert any(p[0] == 5 and p[1] == "done" for p in progress)
        assert "message sandbox" in activity


class TestRunAndroidBranches:
    def _sig(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setattr(workers, "LOCAL_DEST_DIR", str(tmp_path / "results"))
        monkeypatch.setattr(workers, "_find_androidqf",
                            lambda: str(tmp_path / "androidqf"))
        (tmp_path / "mvt_log.txt").write_text("no IoC found\n")
        return tmp_path

    def test_cancel_after_adb(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _P())
        w = workers.AnalysisWorker("android", "pw", "1")
        w.cancel()
        w.run()
        assert w.result is None and w.error is None

    def test_androidqf_missing(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        def fake_run(cmd, **kw):
            if "androidqf" in " ".join(cmd):
                raise FileNotFoundError("androidqf")
            return _P()
        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr(workers, "_extract_imei", lambda d: "IMEI")
        w = workers.AnalysisWorker("android", "pw", "1")
        w.run()
        assert "introuvable" in str(w.error)

    def test_no_dump_generated(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _P())
        monkeypatch.setattr(workers, "_extract_imei", lambda d: "IMEI")
        w = workers.AnalysisWorker("android", "pw", "1")
        w.run()
        assert "Aucun dossier" in str(w.error)

    def test_imei_unknown_then_resolved(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        def fake_run(cmd, **kw):
            if "androidqf" in " ".join(cmd):
                (tmp_path / "dump_new").mkdir(exist_ok=True)
            return _P()
        monkeypatch.setattr("subprocess.run", fake_run)
        calls = {"n": 0}
        def fake_extract(dtype):
            calls["n"] += 1
            return "UNKNOWN" if calls["n"] == 1 else "REALIMEI"
        monkeypatch.setattr(workers, "_extract_imei", fake_extract)
        w = workers.AnalysisWorker("android", "pw", "1")
        w.run()
        assert w.result["imei"] == "REALIMEI"
        assert calls["n"] == 2

    def test_files_csv_moved(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        dump = tmp_path / "dump_csv"
        def fake_run(cmd, **kw):
            if "androidqf" in " ".join(cmd):
                dump.mkdir(exist_ok=True)
                (dump / "files.csv").write_text("#csv\n")
            return _P()
        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr(workers, "_extract_imei", lambda d: "IMEI")
        w = workers.AnalysisWorker("android", "pw", "1")
        w.run()
        assert w.error is None, w.error

    def test_cancel_after_extraction(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        def fake_run(cmd, **kw):
            if "androidqf" in " ".join(cmd):
                (tmp_path / "dump_c").mkdir(exist_ok=True)
            return _P()
        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr(workers, "_extract_imei", lambda d: "IMEI")
        w = workers.AnalysisWorker("android", "pw", "1")
        _inject_cancel_at(w, 1)
        w.run()
        assert w.result is None and w.error is None

    def test_cancel_after_mvt(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        def fake_run(cmd, **kw):
            if "androidqf" in " ".join(cmd):
                (tmp_path / "dump_m").mkdir(exist_ok=True)
            return _P()
        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr(workers, "_extract_imei", lambda d: "IMEI")
        w = workers.AnalysisWorker("android", "pw", "1")
        _inject_cancel_at(w, 2)
        w.run()
        assert w.result is None

    def test_cancel_after_reports(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        def fake_run(cmd, **kw):
            if "androidqf" in " ".join(cmd):
                (tmp_path / "dump_r").mkdir(exist_ok=True)
            return _P()
        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr(workers, "_extract_imei", lambda d: "IMEI")
        w = workers.AnalysisWorker("android", "pw", "1")
        _inject_cancel_at(w, 3)
        w.run()
        assert w.result is None


class TestRunIosBranches:
    def _sig(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setattr(workers, "LOCAL_DEST_DIR", str(tmp_path / "results"))
        monkeypatch.setattr(workers, "DATE_STR", "2026-01-01_12-00-00")
        monkeypatch.setattr(workers, "_extract_imei", lambda d: "IOSIMEI")
        (tmp_path / "mvt_log.txt").write_text("no IoC found\n")

    def test_cancel_in_pairing(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _P())
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        w = workers.AnalysisWorker("ios", "pw", "1")
        w.cancel()
        w.run()
        assert w.result is None and w.error is None

    def test_pairing_timeout(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        vals = iter([1.0, 2.0, 3.0, 1000.0])
        monkeypatch.setattr(workers.time, "monotonic", lambda: next(vals))
        monkeypatch.setattr(workers.time, "sleep", lambda s: None)
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _P(rc=1))
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        w = workers.AnalysisWorker("ios", "pw", "1")
        w.run()
        assert "120" in str(w.error)

    def test_cancel_after_pairing(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _P())
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        w = workers.AnalysisWorker("ios", "pw", "1")
        _inject_cancel_at(w, 0)
        w.run()
        assert w.result is None

    def test_encryption_error(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        def fake_run(cmd, **kw):
            if "validate" in " ".join(cmd):
                return _P(rc=0)
            if "encryption" in " ".join(cmd):
                return _P(rc=1, err="FAILED")
            return _P()
        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        w = workers.AnalysisWorker("ios", "pw", "1")
        w.run()
        assert "chiffrement" in str(w.error)

    def test_backup_fail(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        def fake_run(cmd, **kw):
            if "validate" in " ".join(cmd):
                return _P(rc=0)
            if "backup" in " ".join(cmd) and "encryption" not in " ".join(cmd):
                raise subprocess.CalledProcessError(3, "backup")
            return _P()
        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        w = workers.AnalysisWorker("ios", "pw", "1")
        w.run()
        assert w.error is not None

    def test_udid_missing(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        raw = tmp_path / f"dump_IOSIMEI_2026-01-01_12-00-00"
        raw.mkdir()
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _P())
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        w = workers.AnalysisWorker("ios", "pw", "1")
        w.run()
        assert "UDID" in str(w.error)

    def test_cancel_after_backup(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        raw = tmp_path / f"dump_IOSIMEI_2026-01-01_12-00-00"
        raw.mkdir()
        (raw / "UDID001").mkdir()
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _P())
        w = workers.AnalysisWorker("ios", "pw", "1")
        _inject_cancel_at(w, 1)
        w.run()
        assert w.result is None

    def test_cancel_after_mvt(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        raw = tmp_path / f"dump_IOSIMEI_2026-01-01_12-00-00"
        raw.mkdir()
        (raw / "UDID002").mkdir()
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _P())
        w = workers.AnalysisWorker("ios", "pw", "1")
        _inject_cancel_at(w, 2)
        w.run()
        assert w.result is None

    def test_cancel_after_reports(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        raw = tmp_path / f"dump_IOSIMEI_2026-01-01_12-00-00"
        raw.mkdir()
        (raw / "UDID003").mkdir()
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _P())
        w = workers.AnalysisWorker("ios", "pw", "1")
        _inject_cancel_at(w, 3)
        w.run()
        assert w.result is None

    def test_full_ios_success(self, monkeypatch, tmp_path):
        self._sig(monkeypatch, tmp_path)
        raw = tmp_path / f"dump_IOSIMEI_2026-01-01_12-00-00"
        raw.mkdir()
        (raw / "UDID001").mkdir()
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _P())
        w = workers.AnalysisWorker("ios", "pw", "1")
        w.run()
        assert w.error is None, w.error
        assert w.result["imei"] == "IOSIMEI"
        assert os.path.exists(
            os.path.join(w.result["output_dir"],
                         f"Dump_IOSIMEI_2026-01-01_12-00-00.tar.gz.aes"))


class TestGenerateReportsCoverage:
    def test_short_line_skipped(self, tmp_path):
        log = tmp_path / "mvt_log.txt"
        log.write_text("short\nCRITICAL: match found for pegasus\n", encoding="utf-8")
        html, _ = workers.AnalysisWorker._generate_reports(object(), str(log), "IMEI")
        assert os.path.exists(html)

    def test_missing_log(self, tmp_path):
        html, pdf = workers.AnalysisWorker._generate_reports(
            object(), str(tmp_path / "absent.log"), "IMEI")
        assert os.path.exists(html)
        assert pdf is not None

    def test_pdf_error_swallowed(self, tmp_path, monkeypatch):
        log = tmp_path / "mvt_log.txt"
        log.write_text("CRITICAL: match found for pegasus\n", encoding="utf-8")
        def boom(*a, **k):
            raise RuntimeError("pisa")
        monkeypatch.setattr(xhtml2pdf.pisa, "CreatePDF", boom)
        html, pdf = workers.AnalysisWorker._generate_reports(object(), str(log), "IMEI")
        assert os.path.exists(html)
        assert os.path.exists(pdf)

    def test_warning_in_other_category(self, tmp_path):
        log = tmp_path / "mvt_log.txt"
        log.write_text("INFO: matched stix2 indicator for some exotic thing\n",
                       encoding="utf-8")
        html, _ = workers.AnalysisWorker._generate_reports(object(), str(log), "IMEI")
        content = open(html, encoding="utf-8").read()
        assert "MENACES POTENTIELLES" in content
        assert "Autres Indicateurs STIX2" in content


class TestSecurePackagingCoverage:
    def test_dest_external_only(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "f.txt").write_text("x")
        ext = tmp_path / "ext"
        html = tmp_path / "Report_ext.html"
        html.write_text("<html>x</html>")
        pdf = tmp_path / "Report_ext.pdf"
        pdf.write_bytes(b"%PDF")
        w = object.__new__(workers.AnalysisWorker)
        w.password = "secret"
        w.dest_choice = "2"
        w.ext_dir = str(ext)
        primary = workers.AnalysisWorker._secure_packaging(
            w, [str(src)], "ABC", str(html), str(pdf), str(tmp_path / "log.txt"))
        assert str(ext) in primary
        assert os.path.exists(os.path.join(
            primary, f"Dump_ABC_{workers.DATE_STR}.tar.gz.aes"))

    def test_dest_primary_plus_extension(self, tmp_path, monkeypatch):
        monkeypatch.setattr(workers, "LOCAL_DEST_DIR", str(tmp_path / "local"))
        src = tmp_path / "src3"
        src.mkdir()
        (src / "f.txt").write_text("x")
        ext = tmp_path / "ext3"
        html = tmp_path / "Report_3.html"
        html.write_text("<html>x</html>")
        pdf = tmp_path / "Report_3.pdf"
        pdf.write_bytes(b"%PDF")
        w = object.__new__(workers.AnalysisWorker)
        w.password = "secret"
        w.dest_choice = "3"
        w.ext_dir = str(ext)
        primary = workers.AnalysisWorker._secure_packaging(
            w, [str(src)], "ABC", str(html), str(pdf), str(tmp_path / "log.log"))
        assert "local" in primary
        ext_session = os.path.join(ext, "results",
                                   os.path.basename(primary))
        assert os.path.exists(ext_session)


class TestInstallWorkerCoverage:
    def _setup_script(self, tmp_path):
        setup = tmp_path / "Setup"
        setup.mkdir(exist_ok=True)
        (setup / "setup.sh").write_text("#!/bin/bash\necho ok\n")

    def test_popen_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SYSTEM", "Linux")
        self._setup_script(tmp_path)
        def boom(*a, **k): raise OSError("popen")
        monkeypatch.setattr(workers.subprocess, "Popen", boom)
        msgs = []
        w = workers.InstallWorker("sandbox", str(tmp_path), callback=msgs.append)
        w.run()
        assert w.success is False
        assert any("ERREUR" in m for m in msgs)

    class _FakeOut:
        def __init__(self, lines):
            self._lines = list(lines)
        def readline(self):
            return self._lines.pop(0) if self._lines else ""

    class _FakeProc:
        def __init__(self, rc):
            self.stdin = types.SimpleNamespace(
                write=lambda s: None, flush=lambda: None)
            self.stdout = TestInstallWorkerCoverage._FakeOut(["line1\n", "line2\n"])
            self._rc = rc
        @property
        def returncode(self):
            return self._rc
        def wait(self):
            return None

    def _run_linux(self, monkeypatch, tmp_path, mode, rc):
        monkeypatch.setattr(workers, "SYSTEM", "Linux")
        self._setup_script(tmp_path)
        monkeypatch.setattr(workers.subprocess, "Popen",
                            lambda *a, **k: self._FakeProc(rc))
        msgs = []
        w = workers.InstallWorker(mode, str(tmp_path), callback=msgs.append)
        w.run()
        return w, msgs

    def test_linux_sandbox_success(self, monkeypatch, tmp_path):
        w, msgs = self._run_linux(monkeypatch, tmp_path, "sandbox", 0)
        assert w.success is True
        assert any("Exécution" in m for m in msgs)

    def test_linux_direct_success(self, monkeypatch, tmp_path):
        w, msgs = self._run_linux(monkeypatch, tmp_path, "direct", 0)
        assert w.success is True

    def test_linux_failure(self, monkeypatch, tmp_path):
        w, msgs = self._run_linux(monkeypatch, tmp_path, "sandbox", 3)
        assert w.success is False
        assert "3" in str(w.error)

    def test_windows_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SYSTEM", "Windows")
        msgs = []
        w = workers.InstallWorker("direct", str(tmp_path), callback=msgs.append)
        w.run()
        assert w.success is False
        assert "WSL" in str(w.error)

    def test_missing_setup_script(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SYSTEM", "Linux")
        w = workers.InstallWorker("sandbox", str(tmp_path))
        w.run()
        assert w.success is False
        assert "introuvable" in str(w.error)