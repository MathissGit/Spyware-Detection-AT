"""Régression : la page Destination doit résoudre LOCAL_DEST_DIR."""
import gui.workers as workers
import gui.pages.destination as destination


def test_destination_imports_and_label_uses_workers_constant():
    """La page doit importer LOCAL_DEST_DIR depuis gui.workers (bug : NameError)."""
    source = open(destination.__file__, encoding="utf-8").read()
    assert "from gui.workers import LOCAL_DEST_DIR" in source
    assert "Uniquement en local ({LOCAL_DEST_DIR})" in source
    assert workers.LOCAL_DEST_DIR.endswith("results")