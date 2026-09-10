"""Tests unitaires main.py : fonctions pures et branches non couvertes."""
import io
import os
import re
import tarfile
import subprocess
import sys

import pyAesCrypt
import pytest

import main as cli


class TestPhaseTimer:
    def test_marks_and_summary(self):
        t = cli.PhaseTimer()
        t.mark("a")
        t.mark("b")
        s = t.summary()
        assert "a" in s and "b" in s and "Total" in s

    def test_total_non_negative(self):
        t = cli.PhaseTimer()
        t.mark("x")
        t.mark("y")
        t.mark("z")
        s = t.summary()
        total_line = [l for l in s.split("\n") if "Total" in l]
        assert len(total_line) == 1
        val = re.search(r"(\d+\.\d+)s", total_line[0])
        assert val and float(val.group(1)) >= 0

    def test_empty_timer(self):
        t = cli.PhaseTimer()
        s = t.summary()
        assert "Total : 0.0s" in s


class TestGetBin:
    def test_local_bin_priority(self, monkeypatch):
        def fake_exists(p):
            return p == "/usr/local/bin/mytool"
        monkeypatch.setattr(os.path, "exists", fake_exists)
        assert cli.get_bin("mytool") == "/usr/local/bin/mytool"

    def test_fallback_to_name(self, monkeypatch):
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        assert cli.get_bin("adb") == "adb"


class TestExtractImei:
    def test_android_imei_from_service_call(self, monkeypatch):
        class FakeProc:
            returncode = 0
            stdout = "Parcel(00000000 00000000 '123456789012345' ....)"
            stderr = ""
        monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeProc())
        result = cli.extract_imei("1")
        assert result == "123456789012345"

    def test_android_imei_fallback_serialno(self, monkeypatch):
        call_count = {"n": 0}
        def fake_run(cmd, **kw):
            call_count["n"] += 1
            class P:
                pass
            p = P()
            if call_count["n"] == 1:
                p.returncode = 0
                p.stdout = "nothing"
            else:
                p.returncode = 0
                p.stdout = "SN9876543210"
            return p
        monkeypatch.setattr("subprocess.run", fake_run)
        result = cli.extract_imei("1")
        assert result == "SN9876543210"

    def test_android_imei_unknown(self, monkeypatch):
        def raise_fnf(*a, **k):
            raise FileNotFoundError("adb")
        monkeypatch.setattr("subprocess.run", raise_fnf)
        result = cli.extract_imei("1")
        assert "UNKNOWN" in result

    def test_ios_imei_from_ideviceinfo(self, monkeypatch):
        class FakeProc:
            returncode = 0
            stdout = "359485060123456"
        monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeProc())
        monkeypatch.setattr(os.path, "exists", lambda p: True)
        result = cli.extract_imei("2")
        assert result == "359485060123456"

    def test_ios_imei_unknown(self, monkeypatch):
        class FakeProc:
            returncode = 1
            stdout = ""
        monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeProc())
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        result = cli.extract_imei("2")
        assert "UNKNOWN" in result


class TestGetExternalDrives:
    def test_linux_drives(self, monkeypatch):
        monkeypatch.setattr(cli, "SYSTEM", "Linux")
        monkeypatch.setenv("USER", "testuser")
        orig_exists = os.path.exists
        orig_listdir = os.listdir
        orig_isdir = os.path.isdir

        def fake_exists(p):
            if p in ("/media/testuser", "/mnt"):
                return True
            return orig_exists(p)

        def fake_listdir(p):
            if p == "/media/testuser":
                return ["USB1", "USB2"]
            return orig_listdir(p)

        def fake_isdir(p):
            if p in ("/media/testuser/USB1", "/media/testuser/USB2"):
                return True
            return orig_isdir(p)

        monkeypatch.setattr(os.path, "exists", fake_exists)
        monkeypatch.setattr(os, "listdir", fake_listdir)
        monkeypatch.setattr(os.path, "isdir", fake_isdir)
        drives = cli.get_external_drives()
        assert any("USB1" in d for d in drives)

    def test_empty_when_no_media(self, monkeypatch):
        monkeypatch.setattr(cli, "SYSTEM", "Linux")
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        drives = cli.get_external_drives()
        assert drives == []


class TestFindAndroidqf:
    def test_finds_androidqf(self, monkeypatch, tmp_path):
        import glob as g
        monkeypatch.setattr(g, "glob", lambda p: [str(tmp_path / "androidqf_linux")])
        monkeypatch.setattr(cli, "glob", g)
        result = cli._find_androidqf()
        assert "androidqf" in result

    def test_fallback(self, monkeypatch):
        import glob as g
        monkeypatch.setattr(g, "glob", lambda p: [])
        monkeypatch.setattr(cli, "glob", g)
        result = cli._find_androidqf()
        assert result == "./androidqf"


class TestGenerateReports:
    def test_empty_log_produces_clean_report(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        log = tmp_path / "mvt_log.txt"
        log.write_text("INFO: no issues\n", encoding="utf-8")
        html, pdf = cli.generate_reports(str(log), "TESTIMEI123")
        assert os.path.exists(html)
        with open(html, encoding="utf-8") as f:
            content = f.read()
        assert "Aucune trace" in content
        assert "TESTIMEI123" in content

    @pytest.mark.parametrize("line,expected_cat", [
        ("CRITICAL: match found for pegasus", "Logiciels Espions Ciblés"),
        ("matched indicator for stalkerware app package", "Stalkerwares & Applications Espionnes"),
        ("matched stix2 malicious domain url", "Domaines & Serveurs de Contrôle (C2)"),
        ("match found for file hash", "Fichiers & Processus Compromis"),
        ("matched indicator for sms message", "Communications Malveillantes"),
        ("indicator match: some unknown type", "Autres Indicateurs STIX2"),
    ])
    def test_classification_all_categories(self, tmp_path, monkeypatch, line, expected_cat):
        monkeypatch.chdir(tmp_path)
        log = tmp_path / "mvt_log.txt"
        log.write_text(line + "\n", encoding="utf-8")
        html, _ = cli.generate_reports(str(log), "IMEI")
        with open(html, encoding="utf-8") as f:
            content = f.read()
        assert expected_cat in content

    def test_critical_status(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        log = tmp_path / "mvt_log.txt"
        log.write_text("CRITICAL: match found for predator\n", encoding="utf-8")
        html, _ = cli.generate_reports(str(log), "IMEI")
        with open(html, encoding="utf-8") as f:
            content = f.read()
        assert "COMPROMIS" in content.upper()

    def test_warning_only_status(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        log = tmp_path / "mvt_log.txt"
        log.write_text("WARNING: matched stix2 domain\n", encoding="utf-8")
        html, _ = cli.generate_reports(str(log), "IMEI")
        with open(html, encoding="utf-8") as f:
            content = f.read()
        assert "MENACES POTENTIELLES" in content.upper()


class TestSecureDirectPackaging:
    def test_local_dest_creates_aes(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "dump"
        src.mkdir()
        (src / "data.csv").write_text("test", encoding="utf-8")
        html_path = tmp_path / "Report_test.html"
        pdf_path = tmp_path / "Report_test.pdf"
        html_path.write_text("<html></html>", encoding="utf-8")
        pdf_path.write_bytes(b"%PDF-fake")
        log_path = tmp_path / "mvt_log.txt"
        log_path.write_text("log", encoding="utf-8")

        monkeypatch.setattr(cli, "LOCAL_DEST_DIR", str(tmp_path / "results"))
        monkeypatch.setattr(cli, "AES_BUFFER_SIZE", 64 * 1024)

        cli.secure_direct_packaging(
            folders_to_archive=[str(src)],
            password="testpwd",
            dest_choice="1",
            ext_dir=None,
            imei="TESTIMEI",
            folders_to_delete=[str(src)],
            log_file=str(log_path),
            html_rep=str(html_path),
            pdf_rep=str(pdf_path),
        )

        results = list((tmp_path / "results").rglob("*.aes"))
        assert len(results) == 1
        assert not src.exists()

    def test_ext_dest_creates_aes(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "dump2"
        src.mkdir()
        (src / "f.txt").write_text("x", encoding="utf-8")
        html_path = tmp_path / "Report_ext.html"
        pdf_path = tmp_path / "Report_ext.pdf"
        html_path.write_text("<html></html>", encoding="utf-8")
        pdf_path.write_bytes(b"%PDF-fake")
        log_path = tmp_path / "mvt_log.txt"
        log_path.write_text("log", encoding="utf-8")
        ext = tmp_path / "ext"
        ext.mkdir()

        monkeypatch.setattr(cli, "LOCAL_DEST_DIR", str(tmp_path / "results"))
        monkeypatch.setattr(cli, "AES_BUFFER_SIZE", 64 * 1024)

        cli.secure_direct_packaging(
            folders_to_archive=[str(src)],
            password="testpwd",
            dest_choice="2",
            ext_dir=str(ext),
            imei="TESTIMEI",
            folders_to_delete=[str(src)],
            log_file=str(log_path),
            html_rep=str(html_path),
            pdf_rep=str(pdf_path),
        )

        aes_files = list(ext.rglob("*.aes"))
        assert len(aes_files) == 1

    def test_both_dest_copies(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "dump3"
        src.mkdir()
        (src / "f.txt").write_text("x", encoding="utf-8")
        html_path = tmp_path / "Report_both.html"
        pdf_path = tmp_path / "Report_both.pdf"
        html_path.write_text("<html></html>", encoding="utf-8")
        pdf_path.write_bytes(b"%PDF-fake")
        log_path = tmp_path / "mvt_log.txt"
        log_path.write_text("log", encoding="utf-8")
        ext = tmp_path / "ext2"
        ext.mkdir()

        monkeypatch.setattr(cli, "LOCAL_DEST_DIR", str(tmp_path / "results"))
        monkeypatch.setattr(cli, "AES_BUFFER_SIZE", 64 * 1024)

        cli.secure_direct_packaging(
            folders_to_archive=[str(src)],
            password="testpwd",
            dest_choice="3",
            ext_dir=str(ext),
            imei="IMEI3",
            folders_to_delete=[str(src)],
            log_file=str(log_path),
            html_rep=str(html_path),
            pdf_rep=str(pdf_path),
        )

        local_aes = list((tmp_path / "results").rglob("*.aes"))
        ext_aes = list(ext.rglob("*.aes"))
        assert len(local_aes) == 1
        assert len(ext_aes) == 1

    def test_logs_and_tmp_purged(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "dump4"
        src.mkdir()
        (src / "f.txt").write_text("x", encoding="utf-8")
        html_path = tmp_path / "Report_purge.html"
        pdf_path = tmp_path / "Report_purge.pdf"
        html_path.write_text("<html></html>", encoding="utf-8")
        pdf_path.write_bytes(b"%PDF-fake")
        log_path = tmp_path / "mvt_log.txt"
        log_path.write_text("log", encoding="utf-8")

        monkeypatch.setattr(cli, "LOCAL_DEST_DIR", str(tmp_path / "results"))
        monkeypatch.setattr(cli, "AES_BUFFER_SIZE", 64 * 1024)

        cli.secure_direct_packaging(
            folders_to_archive=[str(src)],
            password="testpwd",
            dest_choice="1",
            ext_dir=None,
            imei="IMEI4",
            folders_to_delete=[str(src)],
            log_file=str(log_path),
            html_rep=str(html_path),
            pdf_rep=str(pdf_path),
        )

        assert not log_path.exists()
        assert not src.exists()
