"""Tests GUI pages : logique métier des pages (PasswordPage, DetectPage, etc.)."""
import os
import sys

import customtkinter as ctk
import pytest


@pytest.fixture
def root():
    """Racine CTk partagée pour les tests GUI."""
    r = ctk.CTk()
    r.withdraw()
    r.update()
    yield r
    r.destroy()


class TestPasswordPageLogic:
    def test_strength_empty(self, root):
        from gui.pages.password import PasswordPage
        page = PasswordPage(root)
        page.update()
        assert page._strength_bar.get() == 0
        page.destroy()

    def test_strength_weak(self, root):
        from gui.pages.password import PasswordPage
        page = PasswordPage(root)
        page._pwd1.insert(0, "abc")
        page._pwd2.insert(0, "abc")
        page._check_match()
        page.update()
        assert page._strength_bar.get() < 0.5
        page.destroy()

    def test_strength_strong(self, root):
        from gui.pages.password import PasswordPage
        page = PasswordPage(root)
        page._pwd1.insert(0, "MyS3cur3P@ss!")
        page._pwd2.insert(0, "MyS3cur3P@ss!")
        page._check_match()
        page.update()
        assert page._strength_bar.get() >= 0.6
        page.destroy()

    def test_match_enables_next(self, root):
        from gui.pages.password import PasswordPage
        called = {}
        page = PasswordPage(root, on_next=lambda p: called.update({"pw": p}))
        page._pwd1.insert(0, "password123")
        page._pwd2.insert(0, "password123")
        page._check_match()
        page.update()
        assert str(page._next_btn.cget("state")) == "normal"
        page.destroy()

    def test_mismatch_disables_next(self, root):
        from gui.pages.password import PasswordPage
        page = PasswordPage(root, on_next=lambda p: None)
        page._pwd1.insert(0, "password1")
        page._pwd2.insert(0, "password2")
        page._check_match()
        page.update()
        assert str(page._next_btn.cget("state")) == "disabled"
        page.destroy()

    def test_empty_disables_next(self, root):
        from gui.pages.password import PasswordPage
        page = PasswordPage(root)
        page.update()
        assert str(page._next_btn.cget("state")) == "disabled"
        page.destroy()

    def test_reset_clears(self, root):
        from gui.pages.password import PasswordPage
        page = PasswordPage(root)
        page._pwd1.insert(0, "test")
        page._pwd2.insert(0, "test")
        page._check_match()
        page.reset()
        page.update()
        assert page._pwd1.get() == ""
        assert str(page._next_btn.cget("state")) == "disabled"
        page.destroy()

    def test_go_next_calls_callback(self, root):
        from gui.pages.password import PasswordPage
        result = {}
        page = PasswordPage(root, on_next=lambda p: result.update({"pw": p}))
        page._pwd1.insert(0, "mypass")
        page._pwd2.insert(0, "mypass")
        page._check_match()
        page._go_next()
        assert result.get("pw") == "mypass"
        page.destroy()


class TestModePageLogic:
    def test_select_sandbox(self, root):
        from gui.pages.mode import ModePage
        result = {}
        page = ModePage(root, on_next=lambda m: result.update({"mode": m}))
        page._select("sandbox")
        page._go_next()
        page.update()
        assert result.get("mode") == "sandbox"
        assert str(page._next_btn.cget("state")) == "normal"
        page.destroy()

    def test_select_direct(self, root):
        from gui.pages.mode import ModePage
        result = {}
        page = ModePage(root, on_next=lambda m: result.update({"mode": m}))
        page._select("direct")
        page._go_next()
        page.update()
        assert result.get("mode") == "direct"
        page.destroy()

    def test_reset(self, root):
        from gui.pages.mode import ModePage
        page = ModePage(root)
        page._select("sandbox")
        page.reset()
        page.update()
        assert str(page._next_btn.cget("state")) == "disabled"
        assert page._selected is None
        page.destroy()

    def test_go_next_disabled_without_selection(self, root):
        from gui.pages.mode import ModePage
        page = ModePage(root)
        page.update()
        assert str(page._next_btn.cget("state")) == "disabled"
        page.destroy()


class TestDeviceTypePageLogic:
    def test_select_android(self, root):
        from gui.pages.device_type import DeviceTypePage
        result = {}
        page = DeviceTypePage(root, on_next=lambda d: result.update({"dtype": d}))
        page._select("android")
        page._go_next()
        page.update()
        assert result.get("dtype") == "android"
        assert str(page._next_btn.cget("state")) == "normal"
        page.destroy()

    def test_select_ios(self, root):
        from gui.pages.device_type import DeviceTypePage
        result = {}
        page = DeviceTypePage(root, on_next=lambda d: result.update({"dtype": d}))
        page._select("ios")
        page._go_next()
        page.update()
        assert result.get("dtype") == "ios"
        page.destroy()

    def test_reset(self, root):
        from gui.pages.device_type import DeviceTypePage
        page = DeviceTypePage(root)
        page._select("android")
        page.reset()
        page.update()
        assert str(page._next_btn.cget("state")) == "disabled"
        page.destroy()


class TestDetectPageLogic:
    def test_set_mode(self, root):
        from gui.pages.detect import DetectPage
        page = DetectPage(root)
        page.set_mode("sandbox")
        assert page._mode == "sandbox"
        page.destroy()

    def test_set_device_type(self, root):
        from gui.pages.detect import DetectPage
        page = DetectPage(root)
        page.set_device_type("ios")
        assert page._device_type == "ios"
        assert page._detected is False
        page.destroy()

    def test_reset(self, root):
        from gui.pages.detect import DetectPage
        page = DetectPage(root)
        page._detected = True
        page._imei = "12345"
        page.reset()
        page.update()
        assert page._detected is False
        assert page._imei == ""
        assert str(page._next_btn.cget("state")) == "disabled"
        page.destroy()

    def test_detect_success_enables_next(self, root, monkeypatch):
        from gui.pages.detect import DetectPage
        from gui import workers
        monkeypatch.setattr(workers, "detect_android_device",
                            lambda **k: (True, "Android OK", "IMEI123"))
        page = DetectPage(root)
        page.after = lambda ms, cb, *a, **k: cb(*a, **k)
        page.set_device_type("android")
        page.update()
        assert page._detected is True
        assert page._imei == "IMEI123"
        page.destroy()

    def test_detect_failure_keeps_disabled(self, root, monkeypatch):
        from gui.pages.detect import DetectPage
        from gui import workers
        monkeypatch.setattr(workers, "detect_android_device",
                            lambda **k: (False, "Aucun appareil", ""))
        page = DetectPage(root)
        page._polling = False
        page._device_type = "android"
        page._run_detect()
        page.update()
        assert page._detected is False
        assert str(page._next_btn.cget("state")) == "disabled"
        page.destroy()

    def test_go_next_with_detected(self, root):
        from gui.pages.detect import DetectPage
        result = {}
        page = DetectPage(root, on_next=lambda imei: result.update({"imei": imei}))
        page._detected = True
        page._imei = "TESTIMEI"
        page._go_next()
        assert result.get("imei") == "TESTIMEI"
        page.destroy()

    def test_go_next_without_detected(self, root):
        from gui.pages.detect import DetectPage
        result = {}
        page = DetectPage(root, on_next=lambda imei: result.update({"imei": imei}))
        page._detected = False
        page._go_next()
        assert "imei" not in result
        page.destroy()


class TestDestinationPageLogic:
    def test_select_local(self, root):
        from gui.pages.destination import DestinationPage
        result = {}
        page = DestinationPage(root, on_next=lambda d, e: result.update({"d": d, "e": e}))
        page._var.set("local")
        page._on_choice()
        page.update()
        assert str(page._next_btn.cget("state")) == "normal"
        page.destroy()

    def test_select_ext(self, root):
        from gui.pages.destination import DestinationPage
        page = DestinationPage(root)
        page._var.set("ext")
        page._on_choice()
        page.update()
        assert page._drive_frame.winfo_manager() == "pack"
        page.destroy()

    def test_go_next_local(self, root):
        from gui.pages.destination import DestinationPage
        result = {}
        page = DestinationPage(root, on_next=lambda d, e: result.update({"d": d, "e": e}))
        page._var.set("local")
        page._go_next()
        assert result.get("d") == "1"
        assert result.get("e") is None
        page.destroy()

    def test_reset(self, root):
        from gui.pages.destination import DestinationPage
        page = DestinationPage(root)
        page._var.set("ext")
        page._on_choice()
        page.reset()
        page.update()
        assert page._var.get() == "local"
        assert str(page._next_btn.cget("state")) == "disabled"
        page.destroy()


class TestResultsPageLogic:
    def test_show_results(self, root, tmp_path):
        from gui.pages.results import ResultsPage
        page = ResultsPage(root)
        result = {"imei": "12345", "output_dir": str(tmp_path),
                  "report_html": "", "report_pdf": ""}
        page.show_results(result)
        page.update()
        assert len(page._body.winfo_children()) > 0
        page.destroy()

    def test_reset(self, root):
        from gui.pages.results import ResultsPage
        page = ResultsPage(root)
        page._body.winfo_children  # ensure exists
        page.reset()
        page.update()
        page.destroy()


class TestAnalysisPageLogic:
    def test_steps_constant(self):
        from gui.pages.analysis import AnalysisPage
        assert len(AnalysisPage.STEPS) == 6
        assert "Connexion" in AnalysisPage.STEPS[0]
        assert "Finalisation" in AnalysisPage.STEPS[-1]

    def test_on_progress_updates_state(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page._on_progress(0, "active", "1.0s")
        page.update()
        assert page._steps[0].state == "active"
        page.destroy()

    def test_on_progress_done(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page._on_progress(0, "done", "2.0s")
        page.update()
        assert page._steps[0].state == "done"
        page.destroy()

    def test_on_progress_error(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page._on_progress(0, "error", "")
        page.update()
        assert page._steps[0].state == "error"
        page.destroy()

    def test_on_log_adds_to_box(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page._on_log("test log message")
        page.update()
        content = page._log_box.get("1.0", "end")
        assert "test log message" in content
        page.destroy()

    def test_on_activity(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page._on_activity("running step 1")
        page.update()
        assert "running step 1" in str(page._activity_label.cget("text"))
        page.destroy()

    def test_cancel_no_worker(self, root):
        from gui.pages.analysis import AnalysisPage
        called = {}
        page = AnalysisPage(root, on_back=lambda: called.update({"back": True}))
        page._worker = None
        page._cancel()
        assert called.get("back") is True
        page.destroy()

    def test_retry_calls_on_back(self, root):
        from gui.pages.analysis import AnalysisPage
        called = {}
        page = AnalysisPage(root, on_back=lambda: called.update({"back": True}))
        page._retry()
        assert called.get("back") is True
        page.destroy()

    def test_reset(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page._on_progress(0, "active")
        page.update()
        assert page._steps[0].state == "active"
        page.reset()
        page.update()
        assert page._steps[0].state == "pending"
        page.destroy()


class TestInstallPageChecks:
    def test_get_checks_returns_list(self, root):
        from gui.pages.install import InstallPage
        page = InstallPage(root, on_back=lambda: None)
        checks = page._get_checks()
        assert isinstance(checks, list)
        assert len(checks) >= 6
        page.destroy()

    def test_has_tk(self, root):
        from gui.pages.install import InstallPage
        page = InstallPage(root, on_back=lambda: None)
        assert page._has_tk() is True
        page.destroy()


class TestHomePageUI:
    def test_creates(self, root):
        from gui.pages.home import HomePage
        page = HomePage(root)
        page.update()
        assert page.winfo_exists()
        page.destroy()
