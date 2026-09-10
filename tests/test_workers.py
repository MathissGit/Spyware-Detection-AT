"""Tests de non-régression pour gui/workers.py"""
import os
import tarfile
import glob
import pytest
import conftest
import gui.workers as workers


@pytest.fixture(autouse=True)
def _cleanup_reports():
    """Nettoie les fichiers de rapport générés dans SCRIPT_DIR après chaque test."""
    yield
    for pat in ("Report_*.html", "Report_*.pdf", "mvt_log*.txt"):
        for f in glob.glob(os.path.join(workers.SCRIPT_DIR, pat)):
            try:
                os.remove(f)
            except OSError:
                pass


def test_generate_reports_no_match(tmp_path):
    """Un log MVT vide ne doit produire aucun serveur et un rapport vide."""
    log = tmp_path / "mvt_log.txt"
    log.write_text("INFO: starting analysis\nINFO: no ioC found\n", encoding="utf-8")
    html, pdf = workers.AnalysisWorker._generate_reports(object(), str(log), "123456789012345")
    assert os.path.exists(html)
    assert os.path.exists(pdf)
    assert os.path.getsize(html) > 0


def test_generate_reports_pegasus_critical(tmp_path):
    """Une ligne Pegasus critique doit être classée et produire un rapport non vide."""
    log = tmp_path / "mvt_log.txt"
    log.write_text(
        "CRITICAL: match found for pegasus indicator\n",
        encoding="utf-8",
    )
    html, pdf = workers.AnalysisWorker._generate_reports(object(), str(log), "ABC123")
    content = ""
    with open(html, encoding="utf-8") as f:
        content = f.read()
    # Le statut doit être "compromis" (critique)
    assert "STATUT : APPAR" in content.upper() or "COMPROMIS" in content.upper()
    assert "Logiciels Espions Ciblés" in content


def test_generate_reports_warning_only(tmp_path):
    """Un IoC non critique doit produire un état 'menaces potentielles'."""
    log = tmp_path / "mvt_log.txt"
    log.write_text(
        "WARNING: matched stix2 for some domain\n",
        encoding="utf-8",
    )
    html, pdf = workers.AnalysisWorker._generate_reports(object(), str(log), "IMEI")
    with open(html, encoding="utf-8") as f:
        content = f.read()
    assert "Domaines & Serveurs C2" in content


def _make_reports(tmp_path):
    """Crée de faux rapports html/pdf pour tester le packaging."""
    html = tmp_path / "Report_test.html"
    pdf = tmp_path / "Report_test.pdf"
    html.write_text("<html>report</html>", encoding="utf-8")
    pdf.write_bytes(b"%PDF-1.4 fake")
    return str(html), str(pdf)


def test_secure_packaging_creates_encrypted_archive(tmp_path):
    """Le packaging doit créer une archive AES chiffrée et supprimer les raws."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "file.txt").write_text("data", encoding="utf-8")
    html, pdf = _make_reports(tmp_path)
    workers.LOCAL_DEST_DIR = str(tmp_path / "results")

    w = object.__new__(workers.AnalysisWorker)
    w.password = "secret"
    w.dest_choice = "1"
    w.ext_dir = None

    primary = workers.AnalysisWorker._secure_packaging(
        w, [str(src)], "1234", html, pdf, str(tmp_path / "mvt_log.txt")
    )
    aes_files = [f for f in os.listdir(primary) if f.endswith(".aes")]
    assert len(aes_files) == 1
    # L'archive temporaire non chiffrée doit avoir été supprimée
    assert not any(f.endswith(".tar.gz") and not f.endswith(".aes") for f in os.listdir(primary))
    # Les rapports sont déplacés dans le dossier de sortie
    assert os.path.exists(os.path.join(primary, os.path.basename(html)))
    assert os.path.exists(os.path.join(primary, os.path.basename(pdf)))


def test_secure_packaging_external_copy(tmp_path):
    """Destination '3' (les deux) doit copier vers le stockage externe."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "f.txt").write_text("x", encoding="utf-8")
    ext = tmp_path / "ext"
    ext.mkdir()
    html, pdf = _make_reports(tmp_path)
    workers.LOCAL_DEST_DIR = str(tmp_path / "local")

    w = object.__new__(workers.AnalysisWorker)
    w.password = "secret"
    w.dest_choice = "3"
    w.ext_dir = str(ext)

    primary = workers.AnalysisWorker._secure_packaging(
        w, [str(src)], "ABC", html, pdf, str(tmp_path / "log.txt")
    )
    # Copie externe présente
    assert any(f.endswith(".aes") for _, _, files in os.walk(str(ext)) for f in files)
    assert os.path.exists(primary)
