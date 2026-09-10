"""Tests for main.py CLI flows: run_android, banner, Darwin drives, PDF error."""
import os
import sys
import types

import pytest

import main as cli


class _Q:
    """Questionary factice qui rejoue une séquence de réponses."""

    def __init__(self, answers):
        self._answers = list(answers)

    class _Box:
        def __init__(self, value):
            self._value = value

        def ask(self):
            return self._value

    class Choice:
        def __init__(self, title, value):
            self.title = title
            self.value = value

    @staticmethod
    def Style(*a, **k):
        return None

    def select(self, *a, **k):
        return self._Box(self._next())

    def text(self, *a, **k):
        return self._Box(self._next())

    def password(self, *a, **k):
        return self._Box(self._next())

    def _next(self):
        assert self._answers, "Plus de réponses scriptées pour questionary"
        return self._answers.pop(0)


def _fake_run_factory(tmp_path, create_dump=False):
    def fake_run(cmd, *a, **k):
        if "androidqf" in " ".join(cmd):
            if create_dump:
                (tmp_path / "dump_123").mkdir(exist_ok=True)
            else:
                raise FileNotFoundError(str(cmd))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    return fake_run


class TestShowBanner:
    def test_banner(self):
        cli.show_banner()


class TestGetExternalDrivesDarwin:
    def test_darwin(self, monkeypatch):
        monkeypatch.setattr(cli, "SYSTEM", "Darwin")
        monkeypatch.setattr(cli.os.path, "exists", lambda p: p == "/Volumes")
        monkeypatch.setattr(cli.os, "listdir",
                            lambda p: ["Macintosh HD", "ExtUSB", "Ext2"])

        def fake_isdir(p):
            return str(p).endswith(("Macintosh HD", "ExtUSB", "Ext2")) and "Macintosh HD" not in p
        monkeypatch.setattr(cli.os.path, "isdir", fake_isdir)
        drives = cli.get_external_drives()
        assert "/Volumes/ExtUSB" in drives
        assert "/Volumes/Ext2" in drives
        assert "/Volumes/Macintosh HD" not in drives


class TestRunAndroid:
    def test_success(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(cli, "extract_imei", lambda *a, **k: "123456789012345")
        monkeypatch.setattr(cli, "_find_androidqf", lambda: "androidqf")
        calls = []
        def fake_run(cmd, *a, **k):
            calls.append(" ".join(cmd))
            if "androidqf" in " ".join(cmd):
                d = tmp_path / "dump_123"
                d.mkdir(exist_ok=True)
                (d / "files.csv").write_text("#csv\n")
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        monkeypatch.setattr(cli.subprocess, "run", fake_run)

        folders, log, imei = cli.run_android()
        assert folders == ["dump_123", "dump_123_mvt_results"]
        assert log == "mvt_log.txt"
        assert imei == "123456789012345"
        assert (tmp_path / "dump_123" / "files.csv").exists()
        assert not (tmp_path / "dump_123" / "_hidden_files.csv").exists()

    def test_bin_not_found_exits(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(cli, "extract_imei", lambda *a, **k: "123")
        monkeypatch.setattr(cli, "_find_androidqf", lambda: "androidqf")
        monkeypatch.setattr(cli.subprocess, "run", _fake_run_factory(tmp_path, create_dump=False))
        with pytest.raises(SystemExit) as e:
            cli.run_android()
        assert e.value.code == 1

    def test_no_dump_dir_exits(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(cli, "extract_imei", lambda *a, **k: "123")
        monkeypatch.setattr(cli, "_find_androidqf", lambda: "androidqf")
        monkeypatch.setattr(cli.subprocess, "run",
                            lambda *a, **k: types.SimpleNamespace(
                                returncode=0, stdout="", stderr=""))
        with pytest.raises(SystemExit) as e:
            cli.run_android()
        assert e.value.code == 1


class TestGetUserInputs:
    @pytest.fixture
    def fake_q(self, monkeypatch):
        def install(answers):
            fq = _Q(answers)
            monkeypatch.setattr(cli, "questionary", fq)
            return fq
        return install

    def test_success_dest_local(self, fake_q):
        fake_q(["1", "1", "mypass", "mypass"])
        device, dest, ext, pwd = cli.get_user_inputs()
        assert (device, dest, ext, pwd) == ("1", "1", None, "mypass")

    def test_device_exit(self, fake_q):
        fake_q(["EXIT"])
        with pytest.raises(SystemExit) as e:
            cli.get_user_inputs()
        assert e.value.code == 0

    def test_device_none(self, fake_q):
        fake_q([None])
        with pytest.raises(SystemExit) as e:
            cli.get_user_inputs()
        assert e.value.code == 0

    def test_dest_none(self, fake_q):
        fake_q(["1", None])
        with pytest.raises(SystemExit) as e:
            cli.get_user_inputs()
        assert e.value.code == 0

    def test_dest_back_then_success(self, fake_q):
        fake_q(["1", "BACK", "1", "1", "pw", "pw"])
        device, dest, ext, pwd = cli.get_user_inputs()
        assert (device, dest, pwd) == ("1", "1", "pw")

    def test_manual_path_invalid_then_valid(self, fake_q, tmp_path, monkeypatch):
        valid = str(tmp_path / "usb")
        os.makedirs(valid)
        fake_q(["1", "2", "MANUAL", str(tmp_path / "nope"), valid, "pw", "pw"])
        device, dest, ext, pwd = cli.get_user_inputs()
        assert (device, dest, ext, pwd) == ("1", "2", valid, "pw")

    def test_manual_path_valid_direct(self, fake_q, tmp_path):
        valid = str(tmp_path / "usb")
        os.makedirs(valid)
        fake_q(["1", "2", "MANUAL", valid, "pw", "pw"])
        device, dest, ext, pwd = cli.get_user_inputs()
        assert (device, dest, ext, pwd) == ("1", "2", valid, "pw")

    def test_ext_back_restarts(self, fake_q):
        fake_q(["1", "3", "BACK_DEST", "1", "1", "pw", "pw"])
        device, dest, ext, pwd = cli.get_user_inputs()
        assert (device, dest, ext, pwd) == ("1", "1", None, "pw")

    def test_pwd_mismatch_then_success(self, fake_q):
        fake_q(["1", "1", "pw1", "pw2", "pwA", "pwB", "pw3", "pw3"])
        _, _, _, pwd = cli.get_user_inputs()
        assert pwd == "pw3"

    def test_pwd_empty_then_success(self, fake_q):
        fake_q(["1", "1", None, "pw", "pw"])
        _, _, _, pwd = cli.get_user_inputs()
        assert pwd == "pw"


class TestGenerateReportsPdfError:
    def test_pdf_error(self, monkeypatch, tmp_path):
        log = tmp_path / "log.txt"
        log.write_text(
            "INFO - unused\n"
            "WARNING - Found Pegasus process: pegasus_something\n"
        )
        monkeypatch.setattr(cli.pisa, "CreatePDF",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        html, pdf = cli.generate_reports(str(log), "TESTIMEI1")
        assert html and os.path.exists(html)
        assert pdf and os.path.exists(pdf)