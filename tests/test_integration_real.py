"""Tests d'intégration réels sans matériel : build_iocs, MVT, scripts shell,
create_icon, imports, instanciation des pages GUI.
Ces tests s'exécutent dans la suite par défaut. Les tests nécessitant un
appareil branché sont marqués @pytest.mark.real_android / real_ios et sont
auto-skippés par tests/conftest.py quand aucun appareil n'est présent.
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PY = os.path.join(ROOT, ".venv_tests", "bin", "python")


class TestBuildIocsReal:
    def test_dry_run_produces_stix2(self, tmp_path):
        result = subprocess.run(
            [VENV_PY, os.path.join(ROOT, "scripts", "build_iocs.py"),
             "--dry-run", "--out", str(tmp_path / "mvt_iocs")],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        personal = os.path.join(str(tmp_path / "mvt_iocs"), "personal.stix2")
        assert os.path.exists(personal)

    def test_stix2_loads_in_mvt(self, tmp_path):
        mvt_indicators = pytest.importorskip("mvt.common.indicators")
        out_dir = str(tmp_path / "mvt_iocs")
        subprocess.run(
            [VENV_PY, os.path.join(ROOT, "scripts", "build_iocs.py"),
             "--dry-run", "--out", out_dir],
            capture_output=True, text=True,
        )
        from mvt.common.indicators import Indicators
        ind = Indicators()
        ind.load_indicators_files([os.path.join(out_dir, "personal.stix2")])
        assert ind.total_ioc_count > 0

    def test_check_returns_zero_for_fresh(self, tmp_path):
        out_dir = str(tmp_path / "mvt_iocs")
        os.makedirs(out_dir, exist_ok=True)
        bundle = {"type": "bundle", "objects": [
            {"type": "indicator", "pattern": "[domain-name:value='test.io']"},
        ]}
        with open(os.path.join(out_dir, "test.stix2"), "w") as f:
            json.dump(bundle, f)
        result = subprocess.run(
            [VENV_PY, os.path.join(ROOT, "scripts", "build_iocs.py"),
             "check", "--out", out_dir],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_check_returns_one_for_empty(self, tmp_path):
        result = subprocess.run(
            [VENV_PY, os.path.join(ROOT, "scripts", "build_iocs.py"),
             "check", "--out", str(tmp_path / "empty")],
            capture_output=True, text=True,
        )
        assert result.returncode == 1


class TestShellSyntax:
    def test_all_sh_syntax(self):
        for base, _, files in os.walk(ROOT):
            if ".git" in base or ".venv" in base or ".vagrant" in base:
                continue
            for f in files:
                if f.endswith(".sh"):
                    path = os.path.join(base, f)
                    result = subprocess.run(["bash", "-n", path], capture_output=True)
                    assert result.returncode == 0, f"Erreur syntaxe: {path}"

    def test_vagrantfile_syntax(self):
        import os
        path = os.path.join(ROOT, "Vagrantfile")
        if not os.path.exists(path):
            pytest.skip("Vagrantfile absent")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Vagrant.configure" in content
        assert len(content) > 50

    def test_launch_sh_executable(self):
        path = os.path.join(ROOT, "scripts", "launch.sh")
        assert os.access(path, os.X_OK)

    def test_setup_sh_executable(self):
        path = os.path.join(ROOT, "setup.sh")
        assert os.access(path, os.X_OK)


class TestCreateIconReal:
    def test_generates_valid_png(self, tmp_path):
        sys.path.insert(0, os.path.join(ROOT, "gui"))
        try:
            from gui.create_icon import write_icon
            icon = str(tmp_path / "icon.png")
            write_icon(icon, size=64)
            with open(icon, "rb") as f:
                header = f.read(8)
            assert header == b"\x89PNG\r\n\x1a\n"
            assert os.path.getsize(icon) > 100
        finally:
            sys.path.pop(0)

    def test_ensure_icon_creates(self, tmp_path):
        sys.path.insert(0, os.path.join(ROOT, "gui"))
        try:
            from gui.create_icon import ensure_icon
            result = ensure_icon(str(tmp_path), size=64)
            assert result is not None
            assert os.path.exists(result)
        finally:
            sys.path.pop(0)


class TestGuiImports:
    def test_all_modules_importable(self):
        modules = [
            "gui.app", "gui.workers", "gui.sandbox_client",
            "gui.theme", "gui.create_icon",
            "gui.pages.home", "gui.pages.install", "gui.pages.mode",
            "gui.pages.device_type", "gui.pages.detect",
            "gui.pages.destination", "gui.pages.password",
            "gui.pages.analysis", "gui.pages.results",
            "gui.widgets.step_indicator", "gui.widgets.progress_step",
            "gui.widgets.device_card", "gui.widgets.toast",
            "main",
            "scripts.build_iocs", "scripts.sandbox_tasks",
        ]
        for mod in modules:
            __import__(mod)


class TestGuiPagesInstantiate:
    def test_all_pages_instantiate(self):
        import customtkinter as ctk
        root = ctk.CTk()
        root.withdraw()
        root.update()

        from gui.pages.home import HomePage
        from gui.pages.mode import ModePage
        from gui.pages.device_type import DeviceTypePage
        from gui.pages.detect import DetectPage
        from gui.pages.destination import DestinationPage
        from gui.pages.password import PasswordPage
        from gui.pages.analysis import AnalysisPage
        from gui.pages.results import ResultsPage

        pages = [
            lambda: HomePage(root),
            lambda: ModePage(root),
            lambda: DeviceTypePage(root),
            lambda: DetectPage(root),
            lambda: DestinationPage(root),
            lambda: PasswordPage(root),
            lambda: AnalysisPage(root),
            lambda: ResultsPage(root),
        ]

        for factory in pages:
            page = factory()
            page.update()
            page.destroy()

        root.destroy()
