"""Tests de non-régression pour main.py (CLI)."""
import os
import conftest
import pytest

import main as cli


def test_phase_timer_marks_and_summary():
    """PhaseTimer doit enregistrer les temps et produire un résumé."""
    timer = cli.PhaseTimer()
    timer.mark("étape 1")
    timer.mark("étape 2")
    summary = timer.summary()
    assert "étape 1" in summary
    assert "étape 2" in summary
    assert "Total" in summary


@pytest.mark.parametrize("line,expected_cat", [
    ("CRITICAL: match found for pegasus", "Logiciels Espions Ciblés"),
    ("matched indicator for stalkerware app package", "Stalkerwares & Applications Espionnes"),
    ("matched stix2 malicious domain url", "Domaines & Serveurs de Contrôle (C2)"),
])
def test_report_classification(tmp_path, monkeypatch, line, expected_cat):
    """Une ligne MVT doit être classée dans la bonne catégorie."""
    monkeypatch.chdir(tmp_path)
    log = tmp_path / "mvt_log.txt"
    log.write_text(line + "\n", encoding="utf-8")
    html, pdf = cli.generate_reports(str(log), "TESTIMEI")
    with open(html, encoding="utf-8") as f:
        content = f.read()
    # La catégorie doit apparaître dans le rapport (avec au moins 1 alerte)
    assert expected_cat in content
    assert "1 alertes" in content or "1 alerte" in content


def test_report_clean_state(tmp_path, monkeypatch):
    """Aucun IoC -> statut vert / 'Aucune trace'."""
    monkeypatch.chdir(tmp_path)
    log = tmp_path / "mvt_log.txt"
    log.write_text("INFO: no issues\n", encoding="utf-8")
    html, pdf = cli.generate_reports(str(log), "IMEI")
    with open(html, encoding="utf-8") as f:
        content = f.read()
    assert "Aucune trace" in content
    assert "IOC est vierge" in content
