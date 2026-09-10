"""Tests de non-régression pour la charte graphique (gui/theme.py)."""
import conftest
import gui.theme as theme


def test_charte_has_required_colors():
    """Les 7 couleurs de la charte doivent être présentes."""
    assert theme.PRIMARY == "#1dbfee"
    assert theme.WARNING == "#d29922"
    assert theme.SECONDARY == "#a18fff"
    assert theme.SUCCESS == "#13d3aa"
    assert theme.DANGER == "#f85149"
    assert theme.BG_LIGHT == "#fefefe"
    assert theme.BG_DARK == "#000000"


def test_color_format():
    """Toutes les couleurs doivent être au format hexadécimal #RRGGBB."""
    for name, value in [
        ("PRIMARY", theme.PRIMARY),
        ("WARNING", theme.WARNING),
        ("SECONDARY", theme.SECONDARY),
        ("SUCCESS", theme.SUCCESS),
        ("DANGER", theme.DANGER),
        ("BG_LIGHT", theme.BG_LIGHT),
        ("BG_DARK", theme.BG_DARK),
    ]:
        assert value.startswith("#"), f"{name} doit commencer par #"
        assert len(value) == 7, f"{name} doit être #RRGGBB"
        int(value[1:], 16)  # doit être parsable en hex


def test_text_contrast_ok():
    """Le texte doit être clair (#fefefe) sur fond sombre."""
    assert theme.TEXT == "#fefefe"
    assert theme.BG_MAIN.startswith("#")
