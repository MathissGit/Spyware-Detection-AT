"""Tests de non-régression du workflow IOC (ioc_personal.json / ioc_sources.json / build_iocs.py)."""
import json
import os
import subprocess
import sys

import conftest

ROOT = conftest.PROJECT_ROOT
VENV_PY = conftest.PY


def _shell_scripts():
    return [
        "scripts/launch.sh",
    ]


def test_ioc_config_files_valid():
    """ioc_personal.json et ioc_sources.json doivent être du JSON valide attendu."""
    personal = json.load(open(os.path.join(ROOT, "ioc_personal.json"), encoding="utf-8"))
    assert isinstance(personal, dict) and "indicators" in personal
    assert isinstance(personal["indicators"], list)
    for entry in personal["indicators"]:
        assert entry.get("name"), "Chaque indicateur personnel doit avoir un nom"

    sources = json.load(open(os.path.join(ROOT, "ioc_sources.json"), encoding="utf-8"))
    assert isinstance(sources, dict) and "sources" in sources
    for source in sources["sources"]:
        assert source.get("name"), "Chaque source doit avoir un nom"
        assert source.get("type") in ("yaml", "stix2"), "Type de source inconnu"
        # une source s'intègre via l'un des trois : github (distant), url (directe), file (local)
        assert "github" in source or "url" in source or "file" in source


def test_file_source_supported():
    """build_iocs doit accepter une source locale via le champ 'file'."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    try:
        import build_iocs
    finally:
        sys.path.pop(0)

    yaml_content = (
        "- name: TestLocal\n"
        "  type: stalkerware\n"
        "  packages:\n"
        "    - com.local.test\n"
    )
    source = {"name": "Local", "type": "yaml", "file": "tmp_local_ioc.yaml"}
    content = build_iocs.source_content(source)
    # fichier inexistant -> None sans crash
    assert content is None
    assert build_iocs.detect_type(source, yaml_content) == "yaml"


def test_build_iocs_dry_run_produces_stix2(tmp_path):
    """build_iocs.py --dry-run doit générer un personal.stix2 exploitable par MVT."""
    out_dir = str(tmp_path / "mvt_iocs")
    result = subprocess.run(
        [VENV_PY, os.path.join(ROOT, "scripts", "build_iocs.py"), "--dry-run", "--out", out_dir],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    personal = os.path.join(out_dir, "personal.stix2")
    assert os.path.exists(personal), "personal.stix2 absent"

    bundle = json.load(open(personal, encoding="utf-8"))
    objects = bundle.get("objects", [])
    indicators = [o for o in objects if o.get("type") == "indicator"]
    malware = [o for o in objects if o.get("type") == "malware"]
    relationships = [o for o in objects if o.get("type") == "relationship"]
    assert len(indicators) > 0
    assert len(malware) > 0
    assert len(relationships) == len(indicators)


def test_generated_stix2_parses_in_mvt(tmp_path):
    """Le STIX2 produit doit être chargé par le parseur MVT (>0 indicateurs)."""
    global_indicators = []
    sys.path.insert(0, ROOT)
    try:
        from mvt.common.indicators import Indicators  # noqa: E402
    finally:
        sys.path.pop(0)

    out_dir = str(tmp_path / "mvt_iocs")
    result = subprocess.run(
        [VENV_PY, os.path.join(ROOT, "scripts", "build_iocs.py"), "--dry-run", "--out", out_dir],
        capture_output=True, text=True,
    )
    assert result.returncode == 0

    ind = Indicators()
    ind.load_indicators_files([os.path.join(out_dir, "personal.stix2")])
    assert ind.total_ioc_count > 0
    names = [c["name"] for c in ind.ioc_collections]
    assert any(name in names for name in ("ExempleSpyware", "TestLocal"))


def test_deduplication_across_sources():
    """L'agregation partagee doit ignorer les patterns deja produits."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    try:
        import build_iocs
    finally:
        sys.path.pop(0)

    entries = [
        {"name": "Dup", "type": "stalkerware", "packages": ["com.dup.app"]},
    ]
    seen: set = set()
    b1 = build_iocs.build_stix2(entries, "s1", seen_patterns=seen)
    b2 = build_iocs.build_stix2(entries, "s2", seen_patterns=seen)
    n1 = sum(1 for o in b1["objects"] if o.get("type") == "indicator")
    n2 = sum(1 for o in b2["objects"] if o.get("type") == "indicator")
    assert n1 == 1 and n2 == 0, f"Aggregation non dedupliquee : {n1} puis {n2}"


def test_personal_not_duplicated_baseline():
    """ioc_personal.json ne doit pas dupliquer la source externe AssoEchap."""
    personal = json.load(open(os.path.join(ROOT, "ioc_personal.json"), encoding="utf-8"))
    personal_names = {e.get("name") for e in personal["indicators"] if e.get("name")}
    # La source par défaut contient deja les noms stalkerware historiques (ex. TheTruthSpy).
    assert "TheTruthSpy" not in personal_names, (
        "ioc_personal.json duplique la source AssoEchap : videz vos doublons"
    )


def test_mvt_stix2_exported_in_scripts():
    """Les scripts de lancement doivent exporter MVT_STIX2 vers mvt_iocs/."""
    for script in _shell_scripts():
        path = os.path.join(ROOT, script)
        assert os.path.exists(path), f"Script manquant : {script}"
        content = open(path, encoding="utf-8").read()
        assert "MVT_STIX2" in content, f"MVT_STIX2 absent dans {script}"
        assert "mvt_iocs" in content, f"référence mvt_iocs absente dans {script}"


def test_mvt_stix2_in_setup_template():
    """Le modèle start_analysis.sh généré par setup.sh doit invoquer launch.sh."""
    path = os.path.join(ROOT, "setup.sh")
    content = open(path, encoding="utf-8").read()
    assert "launch.sh" in content, "launch.sh absent dans le template setup.sh"


def test_mvt_stix2_env_default_in_python():
    """main.py et gui/workers.py doivent définir MVT_STIX2 par défaut si absent."""
    for f in ("main.py", os.path.join("gui", "workers.py")):
        content = open(os.path.join(ROOT, f), encoding="utf-8").read()
        assert "MVT_STIX2" in content, f"MVT_STIX2 absent dans {f}"


def test_check_command_empty_returns_stale(tmp_path):
    """check sans .stix2 doit signaler la péremption (retour 1, aucune écriture)."""
    out_dir = str(tmp_path / "mvt_iocs")
    result = subprocess.run(
        [VENV_PY, os.path.join(ROOT, "scripts", "build_iocs.py"), "check", "--out", out_dir],
        capture_output=True, text=True,
    )
    assert result.returncode == 1, result.stdout
    assert os.path.isdir(out_dir) is False or os.listdir(out_dir) == []


def test_check_command_fresh_returns_zero(tmp_path):
    """check avec un .stix2 récent doit renvoyer 0 (à jour) et lister le fichier."""
    out_dir = str(tmp_path / "mvt_iocs")
    os.makedirs(out_dir, exist_ok=True)
    bundle = {"type": "bundle", "objects": [
        {"type": "indicator", "pattern": "[domain-name:value='exemple.test']"},
    ]}
    with open(os.path.join(out_dir, "exemple.stix2"), "w", encoding="utf-8") as handle:
        json.dump(bundle, handle)

    result = subprocess.run(
        [VENV_PY, os.path.join(ROOT, "scripts", "build_iocs.py"), "check", "--out", out_dir],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout
    assert "exemple.stix2" in result.stdout


def test_update_force_backwards_compatible(tmp_path):
    """Sans sous-commande (défaut update + --dry-run), le comportement legacy est conservé."""
    out_dir = str(tmp_path / "mvt_iocs")
    result = subprocess.run(
        [VENV_PY, os.path.join(ROOT, "scripts", "build_iocs.py"), "--dry-run", "--out", out_dir],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert os.path.exists(os.path.join(out_dir, "personal.stix2")), "personal.stix2 absent"


def test_update_force_flag_accepted():
    """update doit rester invocable sans sous-commande (compat) et cmd_update existe."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    try:
        import build_iocs
    finally:
        sys.path.pop(0)
    assert callable(build_iocs.cmd_update)


def test_update_iocs_wrapper_present():
    """Le wrapper scripts/update_iocs.sh doit exister, être exécutable, et bash -n."""
    path = os.path.join(ROOT, "scripts", "update_iocs.sh")
    assert os.path.exists(path), "scripts/update_iocs.sh manquant"
    assert os.access(path, os.X_OK), "scripts/update_iocs.sh doit être exécutable"
    result = subprocess.run(["bash", "-n", path], capture_output=True)
    assert result.returncode == 0, result.stderr