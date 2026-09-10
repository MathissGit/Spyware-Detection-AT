"""Tests des optimisations MVT : parallélisme, helpers, benchmark."""
import os
import re
import subprocess
import sys
import threading

import pytest

import gui.workers as workers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
try:
    from benchmark_mvt import main as benchmark_main
finally:
    sys.path.pop(0)


class _Proc:
    returncode = 0
    stdout = ""
    stderr = ""


class TestIntSetting:
    def test_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("MVT_TAR_LEVEL", raising=False)
        assert workers._int_setting("MVT_TAR_LEVEL", 1) == 1

    def test_parses_int(self, monkeypatch):
        monkeypatch.setenv("MVT_TAR_LEVEL", "7")
        assert workers._int_setting("MVT_TAR_LEVEL", 1) == 7

    def test_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("MVT_TAR_LEVEL", "abc")
        assert workers._int_setting("MVT_TAR_LEVEL", 1) == 1


class TestIocArgs:
    def test_empty(self):
        assert workers._ioc_args([]) == []

    def test_many(self):
        args = workers._ioc_args(["a.stix2", "b.stix2"])
        assert args == ["--iocs", "a.stix2", "--iocs", "b.stix2"]


class TestParseModules:
    def test_no_match(self):
        assert workers._parse_mvt_modules("nothing here") == []

    def test_parses(self):
        out = " - Modules from MVT: sms, geolocation, whatsapp\n"
        assert workers._parse_mvt_modules(out) == ["sms", "geolocation", "whatsapp"]

    def test_blank_parts_skipped(self):
        out = " - Modules from MVT: ,ab,, c ,\n"
        assert workers._parse_mvt_modules(out) == ["ab", "c"]


def _fake_listing(modules="sms, whatsapp, geolocation"):
    p = _Proc()
    p.stdout = f" - Modules from bundles: {modules}\n"
    return p


class TestRunMvtParallel:
    @pytest.mark.parametrize("exc", [
        FileNotFoundError("mvt"),
        subprocess.TimeoutExpired("mvt", timeout=60),
    ])
    def test_listing_error(self, monkeypatch, tmp_path, exc):
        def boom(cmd, **kw):
            raise exc
        monkeypatch.setattr(subprocess, "run", boom)
        assert workers._run_mvt_parallel(
            ["mvt", "check"], [], str(tmp_path), str(tmp_path / "l.txt"),
            60, 2, None) is None

    def test_listing_nonzero(self, monkeypatch, tmp_path):
        p = _Proc()
        p.returncode = 3
        monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: p)
        assert workers._run_mvt_parallel(
            ["mvt", "check"], [], str(tmp_path), str(tmp_path / "l.txt"),
            60, 2, None) is None

    def test_no_modules(self, monkeypatch, tmp_path):
        monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _Proc())
        assert workers._run_mvt_parallel(
            ["mvt", "check"], [], str(tmp_path), str(tmp_path / "l.txt"),
            60, 2, None) is None

    def test_single_worker_no_parallel(self, monkeypatch, tmp_path):
        monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _fake_listing())
        assert workers._run_mvt_parallel(
            ["mvt", "check"], [], str(tmp_path), str(tmp_path / "l.txt"),
            60, 1, None) is None

    def test_success_merges(self, monkeypatch, tmp_path):
        listing = _fake_listing()

        def fake_run(cmd, **kw):
            if "--list-modules" in cmd:
                return listing
            out = kw.get("stdout")
            if out:
                out.write("module ran\n")
            for i, tok in enumerate(cmd):
                if tok == "--output":
                    wdir = cmd[i + 1]
                    with open(os.path.join(wdir, cmd[i + 3] + ".txt"), "w") as f:
                        f.write("ok\n")
            return _Proc()

        monkeypatch.setattr(subprocess, "run", fake_run)
        output_dir = str(tmp_path / "mvt")
        os.makedirs(output_dir)
        log = str(tmp_path / "l.txt")
        status = workers._run_mvt_parallel(
            ["mvt", "check"], [], output_dir, log, 60, 2, None)
        assert status is True
        for name in ("sms.txt", "whatsapp.txt", "geolocation.txt"):
            assert os.path.exists(os.path.join(output_dir, name))
        with open(log) as f:
            assert f.read().count("module ran") == 3
        leftovers = {n for n in os.listdir(output_dir) if re.match(r"^w\d+$", n)}
        assert leftovers == set()

    def test_cancelled_cleans(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            subprocess, "run",
            lambda cmd, **kw: _fake_listing() if "--list-modules" in cmd else _Proc())
        cancel = threading.Event()
        cancel.set()
        output_dir = str(tmp_path / "mvt")
        os.makedirs(output_dir)
        log = str(tmp_path / "l.txt")
        status = workers._run_mvt_parallel(
            ["mvt", "check"], [], output_dir, log, 60, 2, cancel)
        assert status is False
        assert not os.path.exists(log)
        assert not os.listdir(output_dir)

    def test_module_failure_branch(self, monkeypatch, tmp_path):
        def fake_run(cmd, **kw):
            if "--list-modules" in cmd:
                return _fake_listing()
            r = _Proc()
            r.returncode = 2
            return r
        monkeypatch.setattr(subprocess, "run", fake_run)
        output_dir = str(tmp_path / "mvt")
        log = str(tmp_path / "l.txt")
        status = workers._run_mvt_parallel(
            ["mvt", "check"], [], output_dir, log, 60, 2, None)
        assert status is True


class TestRunMvtCheck:
    def test_sequential(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "MVT_PARALLEL", 0)
        output_dir = str(tmp_path / "seq")
        log = str(tmp_path / "seq.txt")

        def fake_run(cmd, **kw):
            out = kw.get("stdout")
            if out:
                out.write("ran\n")
            return _Proc()
        monkeypatch.setattr(subprocess, "run", fake_run)
        assert workers.run_mvt_check(["mvt", "check"], [], output_dir, log) is True
        with open(log) as f:
            assert "ran" in f.read()

    def test_parallel_success(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "MVT_PARALLEL", 2)
        def fake_run(cmd, **kw):
            if "--list-modules" in cmd:
                return _fake_listing()
            return _Proc()
        monkeypatch.setattr(subprocess, "run", fake_run)
        output_dir = str(tmp_path / "par")
        log = str(tmp_path / "par.txt")
        cancel = threading.Event()
        ok = workers.run_mvt_check(
            ["mvt", "check"], ["ioc.stix2"], output_dir, log,
            timeout=60, cancel_event=cancel)
        assert ok is True

    def test_parallel_fallback_sequential(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "MVT_PARALLEL", 2)
        calls = {"n": 0}

        def fake_run(cmd, **kw):
            calls["n"] += 1
            if "--list-modules" in cmd:
                raise FileNotFoundError("mvt")
            out = kw.get("stdout")
            if out:
                out.write("fallback\n")
            return _Proc()
        monkeypatch.setattr(subprocess, "run", fake_run)
        log = str(tmp_path / "fb.txt")
        output_dir = str(tmp_path / "fb_mvt")
        assert workers.run_mvt_check(["mvt", "check"], [], output_dir, log) is True
        with open(log) as f:
            assert "fallback" in f.read()

    def test_parallel_cancelled(self, monkeypatch, tmp_path):
        monkeypatch.setattr(workers, "MVT_PARALLEL", 2)
        monkeypatch.setattr(
            subprocess, "run",
            lambda cmd, **kw: _fake_listing() if "--list-modules" in cmd else _Proc())
        cancel = threading.Event()
        cancel.set()
        log = str(tmp_path / "c.txt")
        ok = workers.run_mvt_check(
            ["mvt", "check"], [], str(tmp_path / "c_mvt"), log,
            timeout=60, cancel_event=cancel)
        assert ok is False
        assert not os.path.exists(log)


class TestBenchmark:
    @pytest.mark.parametrize("mode,target", [("android", "/x"), ("ios", "/y")])
    def test_main_loop(self, monkeypatch, tmp_path, capsys, mode, target):
        monkeypatch.setattr(workers, "MVT_PARALLEL", 0)
        prefix = str(tmp_path / "bench")

        def fake_check(cmd_base, ioc_files, output_dir, log_file, timeout=None,
                       cancel_event=None):
            os.makedirs(output_dir, exist_ok=True)
            with open(log_file, "w") as f:
                f.write("ok\n")
            return True

        monkeypatch.setattr(workers, "run_mvt_check", fake_check)
        sys.argv = ["benchmark_mvt.py", mode, target,
                    "--output-prefix", prefix]
        benchmark_main()
        out = capsys.readouterr().out
        assert "ok=True" in out
        assert not os.path.exists(prefix + "_p0")