"""Tests d'intégration mockés : flux complets Android/iOS direct et sandbox."""
import json
import os
import subprocess
import tarfile

import pyAesCrypt
import pytest

import main as cli
import gui.workers as workers


class TestIntegrationDirectAndroid:
    def test_full_android_flow(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        dump_dir = tmp_path / "dump_abc"
        dump_dir.mkdir()
        mvt_dir = tmp_path / "dump_abc_mvt_results"
        mvt_dir.mkdir()
        log_file = tmp_path / "mvt_log.txt"
        log_file.write_text(
            "CRITICAL: match found for pegasus indicator\n"
            "matched indicator for stalkerware app\n"
        )

        monkeypatch.setattr(cli, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setattr(cli, "LOCAL_DEST_DIR", str(tmp_path / "results"))
        monkeypatch.setattr(cli, "IOCS_DIR", str(tmp_path / "mvt_iocs"))
        monkeypatch.setattr(cli, "IOC_FILES", [])
        monkeypatch.setattr(cli, "AES_BUFFER_SIZE", 64 * 1024)
        monkeypatch.setattr(cli, "DATE_STR", "2026-01-01_00-00-00")

        def fake_run_android():
            imei = "ANDROIDIMEI123"
            return [str(dump_dir), str(mvt_dir)], str(log_file), imei
        monkeypatch.setattr(cli, "run_android", fake_run_android)

        folders, log, imei = cli.run_android()
        html, pdf = cli.generate_reports(log, imei)
        assert os.path.exists(html)
        with open(html, encoding="utf-8") as f:
            content = f.read()
        assert "COMPROMIS" in content.upper()
        assert "ANDROIDIMEI123" in content

        monkeypatch.setattr(cli, "AES_BUFFER_SIZE", 64 * 1024)
        cli.secure_direct_packaging(
            folders_to_archive=folders[:2],
            password="testpwd",
            dest_choice="1",
            ext_dir=None,
            imei=imei,
            folders_to_delete=folders,
            log_file=str(log),
            html_rep=html,
            pdf_rep=pdf,
        )

        results = list((tmp_path / "results").rglob("*.aes"))
        assert len(results) == 1
        assert not log_file.exists()


class TestIntegrationDirectIos:
    def test_full_ios_flow(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        raw_dir = tmp_path / "dump_ios"
        raw_dir.mkdir()
        mvt_dir = tmp_path / "ios_mvt_results"
        mvt_dir.mkdir()
        log_file = tmp_path / "mvt_log.txt"
        log_file.write_text("matched indicator for sms message\n")

        monkeypatch.setattr(cli, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setattr(cli, "LOCAL_DEST_DIR", str(tmp_path / "results"))
        monkeypatch.setattr(cli, "IOCS_DIR", str(tmp_path / "mvt_iocs"))
        monkeypatch.setattr(cli, "IOC_FILES", [])
        monkeypatch.setattr(cli, "AES_BUFFER_SIZE", 64 * 1024)
        monkeypatch.setattr(cli, "DATE_STR", "2026-01-01_00-00-00")

        def fake_run_ios(password):
            return [str(raw_dir), str(mvt_dir)], str(log_file), "IOSIMEI456"
        monkeypatch.setattr(cli, "run_ios", fake_run_ios)

        folders, log, imei = cli.run_ios("mypass")
        html, pdf = cli.generate_reports(log, imei)
        assert os.path.exists(html)
        with open(html, encoding="utf-8") as f:
            content = f.read()
        assert "IOSIMEI456" in content

        cli.secure_direct_packaging(
            folders_to_archive=folders[:2],
            password="mypass",
            dest_choice="1",
            ext_dir=None,
            imei=imei,
            folders_to_delete=folders,
            log_file=str(log),
            html_rep=html,
            pdf_rep=pdf,
        )

        results = list((tmp_path / "results").rglob("*.aes"))
        assert len(results) == 1


class TestIntegrationSandboxAndroid:
    def test_full_sandbox_flow(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setattr(workers, "LOCAL_DEST_DIR", str(tmp_path / "results"))

        dump = tmp_path / "dump_sb"
        dump.mkdir()
        mvt = tmp_path / "dump_sb_mvt"
        mvt.mkdir()
        log_file = tmp_path / "mvt_log.txt"
        log_file.write_text(
            "CRITICAL: match found for predator\n"
            "matched stix2 malicious domain evil.com\n"
        )

        class FakeClient:
            def __init__(self, **kw): pass
            def ensure_up(self): return True
            def analyze(self, *a, **kw):
                return {"ok": True, "imei": "SBANDROID",
                        "dump_dir": "dump_sb",
                        "mvt_out": "dump_sb_mvt",
                        "log_file": "mvt_log.txt"}
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", FakeClient)

        w = workers.AnalysisWorker("android", "pw", "1", mode="sandbox")
        logs = []
        w.set_callbacks(log_cb=logs.append)
        w.run()

        assert w.error is None, w.error
        assert w.result is not None
        assert w.result["imei"] == "SBANDROID"

        results_dir = tmp_path / "results"
        aes_files = list(results_dir.rglob("*.aes"))
        assert len(aes_files) == 1
        assert not dump.exists()


class TestIntegrationSandboxIos:
    def test_full_sandbox_ios_flow(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setattr(workers, "LOCAL_DEST_DIR", str(tmp_path / "results"))

        raw = tmp_path / "dump_ios_sb"
        raw.mkdir()
        mvt = tmp_path / "ios_mvt_sb"
        mvt.mkdir()
        log_file = tmp_path / "mvt_log.txt"
        log_file.write_text("matched indicator for stalkerware app\n")

        class FakeClient:
            def __init__(self, **kw): pass
            def ensure_up(self): return True
            def analyze(self, *a, **kw):
                return {"ok": True, "imei": "SBIOS",
                        "raw_dir": "dump_ios_sb",
                        "mvt_out": "ios_mvt_sb",
                        "log_file": "mvt_log.txt"}
        monkeypatch.setattr("gui.sandbox_client.SandboxClient", FakeClient)

        w = workers.AnalysisWorker("ios", "mypass", "1", mode="sandbox")
        w.run()

        assert w.error is None, w.error
        assert w.result["imei"] == "SBIOS"
        aes_files = list((tmp_path / "results").rglob("*.aes"))
        assert len(aes_files) == 1


class TestIntegrationIocWorkflow:
    def test_dry_run_then_load_mvt(self, tmp_path):
        out_dir = str(tmp_path / "mvt_iocs")
        result = subprocess.run(
            [os.path.join(ROOT, ".venv_tests", "bin", "python"),
             os.path.join(ROOT, "scripts", "build_iocs.py"),
             "--dry-run", "--out", out_dir],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        personal = os.path.join(out_dir, "personal.stix2")
        assert os.path.exists(personal)

        bundle = json.load(open(personal, encoding="utf-8"))
        objects = bundle.get("objects", [])
        indicators = [o for o in objects if o.get("type") == "indicator"]
        malware = [o for o in objects if o.get("type") == "malware"]
        rels = [o for o in objects if o.get("type") == "relationship"]
        assert len(indicators) > 0
        assert len(malware) > 0
        assert len(rels) == len(indicators)

        from mvt.common.indicators import Indicators
        ind = Indicators()
        ind.load_indicators_files([personal])
        assert ind.total_ioc_count > 0

    def test_check_stale(self, tmp_path):
        out_dir = str(tmp_path / "mvt_iocs")
        os.makedirs(out_dir, exist_ok=True)
        bundle = {"type": "bundle", "objects": [
            {"type": "indicator", "pattern": "[x='y']"},
        ]}
        with open(os.path.join(out_dir, "old.stix2"), "w") as f:
            json.dump(bundle, f)
        result = subprocess.run(
            [os.path.join(ROOT, ".venv_tests", "bin", "python"),
             os.path.join(ROOT, "scripts", "build_iocs.py"),
             "check", "--out", out_dir],
            capture_output=True, text=True,
        )
        assert result.returncode == 0


class TestIntegrationGuiWorkerFlow:
    def test_android_worker_generates_reports_and_packages(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "SCRIPT_DIR", str(tmp_path))
        monkeypatch.setattr(workers, "LOCAL_DEST_DIR", str(tmp_path / "results"))

        dump = tmp_path / "dump_integration"
        mvt = tmp_path / "dump_integration_mvt"
        mvt.mkdir(parents=True, exist_ok=True)
        log = tmp_path / "mvt_log.txt"
        log.write_text(
            "WARNING: matched stix2 for domain evil.com\n"
            "CRITICAL: match found for pegasus\n"
        )

        def fake_run(cmd, **kw):
            if "androidqf" in " ".join(cmd):
                dump.mkdir(exist_ok=True)
            class P:
                returncode = 0
                stdout = ""
                stderr = ""
            return P()
        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr(workers, "_find_androidqf",
                            lambda: str(tmp_path / "androidqf"))
        monkeypatch.setattr(workers, "_extract_imei", lambda *a, **k: "INTEGIMEI")

        w = workers.AnalysisWorker("android", "integpw", "1")
        w.run()

        assert w.error is None, w.error
        assert w.result["imei"] == "INTEGIMEI"

        html_path = w.result.get("report_html", "")
        if html_path and os.path.exists(html_path):
            with open(html_path, encoding="utf-8") as f:
                content = f.read()
            assert "COMPROMIS" in content.upper()

        results_dir = tmp_path / "results"
        aes_files = list(results_dir.rglob("*.aes"))
        assert len(aes_files) == 1


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
