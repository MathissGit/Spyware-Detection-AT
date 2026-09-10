"""Tests de non-régression structurels : syntaxe shell et présence des fichiers clés."""
import os
import subprocess
import sys
import conftest

ROOT = conftest.PROJECT_ROOT

SHELL_SCRIPTS = [
    "scripts/launch.sh",
    "scripts/update_iocs.sh",
    "scripts/setup_hook.sh",
    "setup.sh",
]


def test_python_files_compile():
    """Tous les fichiers Python doivent compiler sans erreur de syntaxe."""
    skip_dirs = {".venv_forensics", ".venv_tests", ".git", "__pycache__"}
    py_files = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(base, f))
    assert len(py_files) > 0, "Aucun fichier Python trouvé"
    for f in py_files:
        subprocess.run([sys.executable, "-m", "py_compile", f],
                       check=True, capture_output=True)


def test_shell_scripts_syntax():
    """Les scripts bash doivent passer bash -n (vérification syntaxe)."""
    bash_scripts = [s for s in SHELL_SCRIPTS if s.endswith(".sh")]
    for script in bash_scripts:
        path = os.path.join(ROOT, script)
        if not os.path.exists(path):
            continue
        result = subprocess.run(["bash", "-n", path], capture_output=True)
        assert result.returncode == 0, f"Erreur de syntaxe dans {script}:\n{result.stderr.decode()}"


def test_core_files_exist():
    """Les fichiers essentiels du projet doivent être présents."""
    required = [
        "main.py",
        "gui.py",
        "gui/app.py",
        "gui/theme.py",
        "gui/workers.py",
        "gui/sandbox_client.py",
        "scripts/sandbox_tasks.py",
        "Vagrantfile",
        "scripts/launch.sh",
        "ioc_personal.json",
        "ioc_sources.json",
    ]
    for f in required:
        assert os.path.exists(os.path.join(ROOT, f)), f"Fichier manquant : {f}"


def test_legacy_files_removed():
    """Les anciens scripts unifiés et fichiers temporaires doivent être absents."""
    removed = [
        "direct_env.sh",
        "direct_env_gui.sh",
        "sandbox_env.sh",
        "sandbox_env_gui.sh",
        "setup_hook.sh",
        "todo.txt",
        "install.md",
        "docs",
        "Setup",
    ]
    for f in removed:
        assert not os.path.exists(os.path.join(ROOT, f)), f"Fichier obsolète encore présent : {f}"


def test_gui_pages_exist():
    """Toutes les pages de l'IHM doivent être présentes."""
    pages = [
        "home.py", "install.py", "mode.py", "device_type.py",
        "detect.py", "destination.py", "password.py",
        "analysis.py", "results.py",
    ]
    for p in pages:
        assert os.path.exists(os.path.join(ROOT, "gui", "pages", p)), f"Page manquante : {p}"


def test_precommit_hook_source_exists():
    """Le hook pre-commit (version committée) doit exister et être exécutable."""
    hook = os.path.join(ROOT, ".githooks", "pre-commit")
    assert os.path.exists(hook), "Hook pre-commit manquant dans .githooks"
    assert os.access(hook, os.X_OK), "Le hook pre-commit doit être exécutable"


def test_precommit_hook_installed():
    """Le hook pre-commit doit être installé localement dans .git/hooks."""
    hook = os.path.join(ROOT, ".git", "hooks", "pre-commit")
    assert os.path.exists(hook), "Hook pre-commit non installé. Lancez : ./scripts/setup_hook.sh"


def test_setup_hook_script_exists():
    """Le script d'installation du hook doit exister dans scripts/."""
    hook = os.path.join(ROOT, "scripts", "setup_hook.sh")
    assert os.path.exists(hook), "scripts/setup_hook.sh manquant"


def test_readme_at_root():
    """Le README principal doit être présent à la racine du projet."""
    readme = os.path.join(ROOT, "README.md")
    assert os.path.exists(readme), "README.md manquant à la racine"
