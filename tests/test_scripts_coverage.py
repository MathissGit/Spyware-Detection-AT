"""Couverture des branches restantes de scripts/build_iocs.py et scripts/sandbox_tasks.py."""
import io
import json
import os
import sys
import types

import pytest

import conftest

ROOT = conftest.PROJECT_ROOT
SCRIPTS = os.path.join(ROOT, "scripts")

sys.path.insert(0, SCRIPTS)
try:
    import build_iocs as bi
    import sandbox_tasks as st
finally:
    sys.path.pop(0)


class _Ok:
    returncode = 0
    stdout = ""
    stderr = ""


class _Rc:
    def __init__(self, rc):
        self.returncode = rc
        self.stdout = ""
        self.stderr = ""


def _last_result(output):
    for line in reversed(output.splitlines()):
        if line.startswith("RESULT_JSON "):
            return json.loads(line[len("RESULT_JSON "):])
    raise AssertionError(f"RESULT_JSON absent dans: {output!r}")


# ================================================================= build_iocs
class TestBuildStixObject:
    def test_object_without_id(self):
        obj = bi._stix_object("indicator", pattern="[domain-name:value='x']")
        assert obj["id"].startswith("indicator--")
        assert obj["type"] == "indicator"


class TestDetectType:
    def test_yaml_error_falls_back_to_stix2(self, monkeypatch):
        assert bi.detect_type({}, ":") == "stix2"

    def test_dict_without_objects_is_yaml(self):
        assert bi.detect_type({}, '{"cle": 1}') == "yaml"


class TestAllSourcesUnsafe:
    def test_loads_real_sources(self):
        sources = bi._all_sources_unsafe()
        assert isinstance(sources, list)


class TestCmdUpdate:
    def _empty_setup(self, tmp_path, monkeypatch, personal="{}"):
        monkeypatch.setattr(bi, "PERSONAL_FILE", str(tmp_path / "personal.json"))
        (tmp_path / "personal.json").write_text(personal, encoding="utf-8")
        monkeypatch.setattr(bi, "SOURCES_FILE", str(tmp_path / "sources_missing.json"))
        monkeypatch.setattr(bi, "SCRIPT_DIR", str(tmp_path))
        return tmp_path / "out"

    def test_empty_personal_dry_run(self, tmp_path, monkeypatch, capsys):
        out = self._empty_setup(tmp_path, monkeypatch)
        assert bi.cmd_update(str(out), dry_run=True) == 0
        assert "vide" in capsys.readouterr().out

    def test_bundle_none_skipped(self, tmp_path, monkeypatch):
        out = self._empty_setup(
            tmp_path, monkeypatch,
            json.dumps({"indicators": [{"name": "x"}]}))
        monkeypatch.setattr(bi, "build_stix2", lambda *a, **k: None)
        assert bi.cmd_update(str(out), dry_run=True) == 0

    def test_sources_local_and_remote(self, tmp_path, monkeypatch, capsys):
        self._empty_setup(tmp_path, monkeypatch, personal="{}")
        (tmp_path / "local.yaml").write_text(
            "- name: T1\n  domains:\n    - evil.example.com\n", encoding="utf-8")
        sources = {"sources": [
            {"name": "loc", "file": "local.yaml"},
            {"name": "rem", "url": "http://127.0.0.1/x"},
        ]}
        sources_file = tmp_path / "sources.json"
        sources_file.write_text(json.dumps(sources), encoding="utf-8")
        monkeypatch.setattr(bi, "SOURCES_FILE", str(sources_file))
        monkeypatch.setattr(
            bi, "requests",
            types.SimpleNamespace(
                get=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("réseau indisponible"))
            ),
        )
        assert bi.cmd_update(str(tmp_path / "out"), dry_run=False) == 1
        out = capsys.readouterr().out
        assert "Termine" in out
        assert "Echec rem" in out


class TestCmdCheck:
    def test_stats_and_official(self, tmp_path, monkeypatch, capsys):
        out = tmp_path / "out"
        out.mkdir()
        (out / "good.stix2").write_text(
            json.dumps({"objects": [{"type": "indicator"}, {"type": "malware"}]}),
            encoding="utf-8")
        (out / "bad.stix2").write_text("{not json", encoding="utf-8")
        (out / "notes.txt").write_text("ignoré", encoding="utf-8")
        official = tmp_path / "official"
        official.mkdir()
        (official / "mvt-official.stix2").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(bi, "DEFAULT_MVT_INDICATORS", str(official))
        assert bi.cmd_check(str(out), max_age_hours=999999) == 1
        out = capsys.readouterr().out
        assert "illisible" in out
        assert "mvt-official.stix2" in out


class TestMainDispatch:
    def test_main_update(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bi, "PERSONAL_FILE", str(tmp_path / "personal.json"))
        (tmp_path / "personal.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(bi, "SOURCES_FILE", str(tmp_path / "missing.json"))
        monkeypatch.setattr(
            sys, "argv", ["build_iocs.py", "update", "--out",
                          str(tmp_path / "out"), "--dry-run"])
        assert bi.main() == 0

    def test_main_check(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["build_iocs.py", "check", "--out", str(tmp_path / "out")])
        monkeypatch.setattr(bi, "cmd_check", lambda out, **kw: 42)
        assert bi.main() == 42


# ============================================================== sandbox_tasks
class TestRunReal:
    def test_run_body(self):
        res = st._run(["echo", "hi"], text=True)
        assert res.returncode == 0


class TestDetectIosError:
    def test_exception_emits_error(self, monkeypatch, capsys):
        def boom(*a, **k):
            raise OSError("idevicepair absent")
        monkeypatch.setattr(st, "_run", boom)
        st.cmd_detect_ios()
        data = _last_result(capsys.readouterr().out)
        assert data["found"] is False
        assert "Erreur iOS" in data["msg"]


class TestAnalyzeIosRetry:
    def test_pairing_retry_then_success(self, monkeypatch, capsys, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(st.sys, "stdin", io.StringIO("mypassword\n"))
        monkeypatch.setattr(st, "_imei_ios", lambda: "IOSIMEI")
        monkeypatch.setattr(st, "_bin", lambda n: n)
        monkeypatch.setattr(st.os, "chdir", lambda p: None)
        monkeypatch.setattr(st.subprocess, "run", lambda *a, **kw: _Ok())
        monkeypatch.setattr(st, "_sudo", lambda cmd: cmd)
        monkeypatch.setattr(st, "_mvt_bin", lambda name: name)
        monkeypatch.setattr(st, "_ioc_args",
                            lambda cmd: (cmd + ["--iocs", "x.stix2"], ["x.stix2"]))
        monkeypatch.setattr(st, "VM_ROOT", str(tmp_path))
        monkeypatch.setattr(st.time, "sleep", lambda s: None)

        calls = {"n": 0}
        def fake_run(cmd, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return _Rc(1)
            return _Ok()
        monkeypatch.setattr(st, "_run", fake_run)

        raw_dir = f"dump_IOSIMEI_{st.DATE_STR}"
        os.makedirs(tmp_path / raw_dir / "UDID123", exist_ok=True)

        st.cmd_analyze_ios()
        data = _last_result(capsys.readouterr().out)
        assert data["ok"] is True
        assert data["imei"] == "IOSIMEI"


class TestMainUsage:
    def test_invalid_command_usage(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["sandbox_tasks.py", "nope"])
        with pytest.raises(SystemExit) as exc:
            st.main()
        assert exc.value.code == 2
        assert "usage" in capsys.readouterr().err