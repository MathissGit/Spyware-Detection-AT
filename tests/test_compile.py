"""Tests de compilation globaux : syntaxe Python/Shell, exécutabilité, shebangs, imports."""
import glob
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv_tests", "bin", "python")

EXCLUDE_DIRS = {
    ".venv_forensics", ".venv_tests", ".git", ".vagrant",
    "__pycache__", "mvt_iocs", ".pytest_cache",
}


def _py_files():
    files = []
    for base, dirs, fnames in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in fnames:
            if f.endswith(".py"):
                files.append(os.path.join(base, f))
    return files


def _sh_files():
    files = []
    for base, dirs, fnames in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in fnames:
            if f.endswith(".sh"):
                files.append(os.path.join(base, f))
    return files


def _all_python_modules():
    """Liste les modules Python importables du projet."""
    modules = [
        "main", "gui", "gui.app", "gui.theme", "gui.workers",
        "gui.sandbox_client", "gui.create_icon",
        "gui.pages", "gui.pages.home", "gui.pages.install",
        "gui.pages.mode", "gui.pages.device_type", "gui.pages.detect",
        "gui.pages.destination", "gui.pages.password",
        "gui.pages.analysis", "gui.pages.results",
        "gui.widgets", "gui.widgets.step_indicator",
        "gui.widgets.progress_step", "gui.widgets.device_card",
        "gui.widgets.toast",
        "scripts.build_iocs", "scripts.sandbox_tasks",
    ]
    return modules


class TestPythonCompilation:
    """Tous les fichiers .py du projet doivent compiler."""

    @pytest.mark.parametrize("pyfile", _py_files(), ids=lambda p: os.path.relpath(p, ROOT))
    def test_py_compile_venv(self, pyfile):
        result = subprocess.run(
            [PY, "-m", "py_compile", pyfile],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"Erreur compilation {os.path.relpath(pyfile, ROOT)}:\n{result.stderr}"
        )

    def test_count_py_files(self):
        files = _py_files()
        assert len(files) > 20, f"Seulement {len(files)} fichiers Python trouvés"


class TestShellCompilation:
    """Tous les scripts .sh + le Vagrantfile doivent passer bash -n."""

    def test_shell_scripts_syntax(self):
        sh_files = _sh_files()
        assert len(sh_files) >= 4, f"Seulement {len(sh_files)} scripts shell trouvés"
        for sh in sh_files:
            result = subprocess.run(
                ["bash", "-n", sh], capture_output=True, text=True,
            )
            assert result.returncode == 0, (
                f"Erreur syntaxe {os.path.relpath(sh, ROOT)}:\n{result.stderr}"
            )

    def test_vagrantfile_syntax(self):
        vagrant = os.path.join(ROOT, "Vagrantfile")
        if not os.path.exists(vagrant):
            pytest.skip("Vagrantfile absent")
        with open(vagrant, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Vagrant.configure" in content, "Vagrantfile ne contient pas Vagrant.configure"
        assert len(content) > 50, "Vagrantfile trop court"


class TestExecutability:
    """Les scripts et entrées exécutables doivent avoir les bons attributs."""

    PYTHON_EXECUTABLES = [
        "scripts/build_iocs.py", "scripts/sandbox_tasks.py",
    ]
    PYTHON_MODULES = [
        "main.py", "gui.py", "gui/create_icon.py",
    ]
    SHELL_EXECUTABLES = [
        "scripts/launch.sh", "scripts/setup_hook.sh",
        "scripts/update_iocs.sh", "setup.sh", "start_analysis.sh",
        ".githooks/pre-commit",
    ]

    @pytest.mark.parametrize("relpath", PYTHON_EXECUTABLES)
    def test_python_executable_or_shebang(self, relpath):
        path = os.path.join(ROOT, relpath)
        if not os.path.exists(path):
            pytest.skip(f"{relpath} absent")
        with open(path, "r", encoding="utf-8") as f:
            first = f.readline().strip()
        has_shebang = first.startswith("#!")
        is_exec = os.access(path, os.X_OK)
        assert has_shebang or is_exec, (
            f"{relpath} n'est ni exécutable ni shebang: {first}"
        )

    @pytest.mark.parametrize("relpath", PYTHON_MODULES)
    def test_python_module_valid(self, relpath):
        path = os.path.join(ROOT, relpath)
        if not os.path.exists(path):
            pytest.skip(f"{relpath} absent")
        result = subprocess.run(
            [PY, "-m", "py_compile", path],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"Erreur compilation {relpath}:\n{result.stderr}"
        )

    @pytest.mark.parametrize("relpath", SHELL_EXECUTABLES)
    def test_shell_executable(self, relpath):
        path = os.path.join(ROOT, relpath)
        if not os.path.exists(path):
            pytest.skip(f"{relpath} absent")
        assert os.access(path, os.X_OK), f"{relpath} n'est pas exécutable"
        with open(path, "r", encoding="utf-8") as f:
            first = f.readline().strip()
        assert first.startswith("#!/"), f"{relpath} n'a pas de shebang: {first}"


class TestScriptLaunch:
    """Les scripts Python doivent se lancer sans crash d'import."""

    def test_gui_help(self):
        result = subprocess.run(
            [PY, os.path.join(ROOT, "gui.py"), "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"gui.py --help a échoué:\n{result.stderr}"
        assert "mode" in result.stdout.lower()

    def test_build_iocs_check_empty(self, tmp_path):
        out = tmp_path / "mvt_iocs"
        result = subprocess.run(
            [PY, os.path.join(ROOT, "scripts", "build_iocs.py"),
             "check", "--out", str(out)],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 1, (
            f"build_iocs.py check devrait retourner 1 (aucun .stix2):\n{result.stdout}"
        )

    def test_sandbox_tasks_usage(self):
        result = subprocess.run(
            [PY, os.path.join(ROOT, "scripts", "sandbox_tasks.py")],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 2, (
            f"sandbox_tasks.py sans arg devrait retourner 2 (usage):\n{result.stdout}"
        )
        assert "usage" in result.stderr.lower() or "usage" in result.stdout.lower()

    def test_build_iocs_usage(self):
        result = subprocess.run(
            [PY, os.path.join(ROOT, "scripts", "build_iocs.py"), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, (
            f"build_iocs.py --help a échoué:\n{result.stderr}"
        )


class TestModuleImports:
    """Tous les modules du projet doivent s'importer sans erreur."""

    @pytest.mark.parametrize("mod", _all_python_modules(),
                             ids=lambda m: m.split(".")[-1])
    def test_import_module(self, mod):
        __import__(mod)


class TestAssetsValidation:
    """Les fichiers de config/assets doivent être valides."""

    def test_ioc_personal_valid_json(self):
        path = os.path.join(ROOT, "ioc_personal.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert "indicators" in data
        assert isinstance(data["indicators"], list)

    def test_ioc_sources_valid_json(self):
        path = os.path.join(ROOT, "ioc_sources.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_icon_png_exists(self):
        path = os.path.join(ROOT, "icon.png")
        assert os.path.exists(path), "icon.png manquant"

    def test_icon_png_valid_header(self):
        path = os.path.join(ROOT, "icon.png")
        with open(path, "rb") as f:
            header = f.read(8)
        assert header == b"\x89PNG\r\n\x1a\n", "icon.png n'est pas un PNG valide"

    def test_mvt_iocs_contains_stix2(self):
        iocs_dir = os.path.join(ROOT, "mvt_iocs")
        if not os.path.isdir(iocs_dir):
            pytest.skip("mvt_iocs absent")
        files = [f for f in os.listdir(iocs_dir) if f.endswith(".stix2")]
        assert len(files) > 0, "Aucun fichier .stix2 dans mvt_iocs/"

    def test_githooks_precommit_exists(self):
        path = os.path.join(ROOT, ".githooks", "pre-commit")
        assert os.path.exists(path)
        assert os.access(path, os.X_OK)

    def test_setup_hook_script_exists(self):
        path = os.path.join(ROOT, "scripts", "setup_hook.sh")
        assert os.path.exists(path)
