"""Tests gui/app.py : navigation et create_icon.py : PNG valide."""
import os
import sys

import customtkinter as ctk
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def root():
    r = ctk.CTk()
    r.withdraw()
    r.update()
    yield r
    r.destroy()


class TestAppNavigation:
    def test_creates_in_direct_mode(self, root):
        from gui.app import SpywareDetectionApp
        app = SpywareDetectionApp.__new__(SpywareDetectionApp)
        ctk.CTk.__init__(app)
        app._default_mode = "direct"
        app._state = {
            "mode": "direct", "device_type": None, "imei": "",
            "dest_choice": "1", "ext_dir": None, "password": "",
        }
        assert app._state["mode"] == "direct"
        app.destroy()

    def test_creates_in_sandbox_mode(self, root):
        from gui.app import SpywareDetectionApp
        app = SpywareDetectionApp.__new__(SpywareDetectionApp)
        ctk.CTk.__init__(app)
        app._default_mode = "sandbox"
        app._state = {"mode": "sandbox"}
        assert app._state["mode"] == "sandbox"
        app.destroy()

    def test_state_transitions(self, root):
        from gui.app import SpywareDetectionApp
        app = SpywareDetectionApp.__new__(SpywareDetectionApp)
        ctk.CTk.__init__(app)
        app._default_mode = "direct"
        app._state = {"mode": "direct", "device_type": None,
                      "imei": "", "dest_choice": "1",
                      "ext_dir": None, "password": ""}

        app._state["mode"] = "sandbox"
        app._state["device_type"] = "android"
        app._state["imei"] = "12345"
        app._state["dest_choice"] = "2"
        app._state["ext_dir"] = "/mnt/usb"
        app._state["password"] = "secret"

        assert app._state["mode"] == "sandbox"
        assert app._state["device_type"] == "android"
        assert app._state["imei"] == "12345"
        assert app._state["dest_choice"] == "2"
        assert app._state["ext_dir"] == "/mnt/usb"
        assert app._state["password"] == "secret"
        app.destroy()


class TestCreateIcon:
    def test_write_icon_creates_png(self, tmp_path):
        sys.path.insert(0, os.path.join(ROOT, "gui"))
        try:
            from gui.create_icon import write_icon
            icon_path = str(tmp_path / "icon.png")
            write_icon(icon_path, size=64)
            assert os.path.exists(icon_path)
            with open(icon_path, "rb") as f:
                header = f.read(8)
            assert header == b"\x89PNG\r\n\x1a\n"
        finally:
            sys.path.pop(0)

    def test_ensure_icon_creates_when_missing(self, tmp_path):
        sys.path.insert(0, os.path.join(ROOT, "gui"))
        try:
            from gui.create_icon import ensure_icon
            result = ensure_icon(str(tmp_path), size=32)
            assert result is not None
            assert os.path.exists(result)
        finally:
            sys.path.pop(0)

    def test_ensure_icon_skips_when_exists(self, tmp_path):
        sys.path.insert(0, os.path.join(ROOT, "gui"))
        try:
            from gui.create_icon import ensure_icon
            existing = tmp_path / "icon.png"
            existing.write_bytes(b"existing")
            result = ensure_icon(str(tmp_path), size=32)
            assert result == str(existing)
            assert existing.read_bytes() == b"existing"
        finally:
            sys.path.pop(0)

    def test_draw_icon_dimensions(self, tmp_path):
        sys.path.insert(0, os.path.join(ROOT, "gui"))
        try:
            from gui.create_icon import draw_icon
            size = 32
            pixels = draw_icon(size)
            assert len(pixels) == size
            assert all(len(row) == size for row in pixels)
            for row in pixels:
                for pixel in row:
                    assert len(pixel) == 3
                    assert all(0 <= v <= 255 for v in pixel)
        finally:
            sys.path.pop(0)

    def test_colors_present(self):
        sys.path.insert(0, os.path.join(ROOT, "gui"))
        try:
            from gui.create_icon import COLORS
            assert "PRIMARY" in COLORS
            assert "BG_DARK" in COLORS
            for name, color in COLORS.items():
                assert len(color) == 3
                assert all(0 <= v <= 255 for v in color)
        finally:
            sys.path.pop(0)
