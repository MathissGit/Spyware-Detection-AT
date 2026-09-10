"""Tests du mécanisme d'auto-skip des tests d'intégration réels (matériel)."""
import types

import pytest

import conftest


class TestDeviceDetection:
    def test_android_device_present(self, monkeypatch):
        fake = types.SimpleNamespace(
            stdout="List of devices attached\n0123456789abcdef\tdevice\n"
        )
        monkeypatch.setattr(conftest, "_ADB", "/bin/true")
        monkeypatch.setattr(conftest.subprocess, "run", lambda *a, **k: fake)
        assert conftest.android_device_present() is True

    def test_android_device_absent(self, monkeypatch):
        fake = types.SimpleNamespace(stdout="List of devices attached\n")
        monkeypatch.setattr(conftest, "_ADB", "/bin/true")
        monkeypatch.setattr(conftest.subprocess, "run", lambda *a, **k: fake)
        assert conftest.android_device_present() is False

    def test_android_binary_missing(self, monkeypatch):
        def boom(*a, **k):
            raise OSError("adb absent")
        monkeypatch.setattr(conftest.subprocess, "run", boom)
        assert conftest.android_device_present() is False

    def test_ios_device_present(self, monkeypatch):
        fake = types.SimpleNamespace(stdout="00008101-0000000000000000\n")
        monkeypatch.setattr(conftest, "_IDEVICE_ID", "/bin/true")
        monkeypatch.setattr(conftest.subprocess, "run", lambda *a, **k: fake)
        assert conftest.ios_device_present() is True

    def test_ios_device_absent(self, monkeypatch):
        fake = types.SimpleNamespace(stdout="")
        monkeypatch.setattr(conftest, "_IDEVICE_ID", "/bin/true")
        monkeypatch.setattr(conftest.subprocess, "run", lambda *a, **k: fake)
        assert conftest.ios_device_present() is False


class TestModifyItems:
    def _mk_item(self, *markers):
        class _Item:
            def __init__(self):
                self._markers = [pytest.mark.__getattr__(m)() if hasattr(
                    pytest.mark, m) else None for m in markers]
            def get_closest_marker(self, name):
                for m in self._markers:
                    if m is not None and m.name == name:
                        return m
                return None
            def add_marker(self, marker):
                self._added = marker
        return _Item()

    def test_skips_real_android_when_no_device(self, monkeypatch):
        monkeypatch.setattr(conftest, "android_device_present", lambda: False)
        monkeypatch.setattr(conftest, "ios_device_present", lambda: True)
        items = [self._mk_item("real_android"), self._mk_item("real_ios"),
                 self._mk_item("parametrize")]
        conftest.pytest_collection_modifyitems(None, items)
        assert hasattr(items[0], "_added")
        assert not hasattr(items[1], "_added")
        assert not hasattr(items[2], "_added")

    def test_no_skip_when_devices_present(self, monkeypatch):
        monkeypatch.setattr(conftest, "android_device_present", lambda: True)
        monkeypatch.setattr(conftest, "ios_device_present", lambda: True)
        items = [self._mk_item("real_android"), self._mk_item("real_ios")]
        conftest.pytest_collection_modifyitems(None, items)
        assert not hasattr(items[0], "_added")
        assert not hasattr(items[1], "_added")