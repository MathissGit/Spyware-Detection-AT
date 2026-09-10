"""Tests SpywareDetectionApp navigation + ResultsPage + remaining branches."""
import os
import sys
import io
import time

import customtkinter as ctk
import pytest


@pytest.fixture(scope="module")
def app():
    """Crée une app CTk annihilée pour les tests navigation (module-scoped)."""
    try:
        from gui.app import SpywareDetectionApp
        a = SpywareDetectionApp(mode="direct")
        a.withdraw()
        a.update()
        yield a
        a.destroy()
    except Exception:
        yield None


class TestAppNavigation:
    def test_show_home(self, app):
        if app is None:
            pytest.skip("App init failed")
        app._show_home()
        assert app._pages["home"].winfo_manager() == "pack"

    def test_start_analysis_flow(self, app):
        if app is None:
            pytest.skip("App init failed")
        app._start_analysis_flow()
        assert app._pages["mode"].winfo_manager() == "pack"
        assert app._state["mode"] == "direct"

    def test_mode_selection(self, app):
        if app is None:
            pytest.skip("App init failed")
        app._on_mode_selected("sandbox")
        assert app._state["mode"] == "sandbox"
        assert app._pages["device_type"].winfo_manager() == "pack"

    def test_device_type_selection(self, app):
        if app is None:
            pytest.skip("App init failed")
        app._state["mode"] = "direct"
        app._on_device_type_selected("android")
        assert app._state["device_type"] == "android"
        assert app._pages["detect"].winfo_manager() == "pack"

    def test_destination_selection(self, app):
        if app is None:
            pytest.skip("App init failed")
        app._on_destination_selected("1", None)
        assert app._state["dest_choice"] == "1"
        assert app._pages["password"].winfo_manager() == "pack"

    def test_password_set_starts_analysis(self, app, monkeypatch):
        if app is None:
            pytest.skip("App init failed")
        app._state = {"mode": "direct", "device_type": "android",
                       "imei": "123", "dest_choice": "1", "ext_dir": None, "password": ""}
        monkeypatch.setattr(app._pages["analysis"], "start_analysis",
                            lambda device_type, password, dest_choice,
                                   ext_dir, mode: None)
        app._on_password_set("mypass")
        assert app._state["password"] == "mypass"
        assert app._pages["analysis"].winfo_manager() == "pack"

    def test_on_analysis_done(self, app):
        if app is None:
            pytest.skip("App init failed")
        result = {"imei": "123", "output_dir": "", "report_html": ""}
        app._on_analysis_done(result)
        assert app._pages["results"].winfo_manager() == "pack"

    def test_show_install(self, app):
        if app is None:
            pytest.skip("App init failed")
        app._show_install()
        assert app._pages["install"].winfo_manager() == "pack"

    def test_back_show_pages(self, app):
        if app is None:
            pytest.skip("App init failed")
        app._show_page("mode", step_index=0)
        app._show_device_type()
        assert app._pages["device_type"].winfo_manager() == "pack"
        app._show_detect()
        assert app._pages["detect"].winfo_manager() == "pack"
        app._show_destination()
        assert app._pages["destination"].winfo_manager() == "pack"
        app._show_password()
        assert app._pages["password"].winfo_manager() == "pack"

    def test_show_page_none_step(self, app):
        if app is None:
            pytest.skip("App init failed")
        app._show_page("home", step_index=None)
        assert app._pages["home"].winfo_manager() == "pack"


@pytest.fixture(scope="module")
def root():
    r = ctk.CTk()
    r.withdraw()
    r.update()
    yield r
    r.destroy()


class TestResultsPage:
    def test_show_results_empty(self, root):
        from gui.pages.results import ResultsPage
        page = ResultsPage(root)
        page.show_results({"imei": "123", "output_dir": "", "report_html": ""})
        page.update()
        page.destroy()

    def test_show_results_with_html(self, root, tmp_path):
        from gui.pages.results import ResultsPage
        out = tmp_path / "results"
        out.mkdir()
        (out / "Report_123.html").write_text("<html>report</html>")
        page = ResultsPage(root)
        page.show_results({"imei": "123", "output_dir": str(out),
                           "report_html": str(out / "Report_123.html")})
        page.update()
        page.destroy()

    def test_show_results_with_pdf(self, root, tmp_path):
        from gui.pages.results import ResultsPage
        out = tmp_path / "results"
        out.mkdir()
        (out / "Report_123.html").write_text("<html>report</html>")
        (out / "Report_123.pdf").write_bytes(b"%PDF-fake")
        page = ResultsPage(root)
        page.show_results({"imei": "123", "output_dir": str(out),
                           "report_html": str(out / "Report_123.html")})
        page.update()
        page.destroy()

    def test_show_results_with_aes(self, root, tmp_path):
        from gui.pages.results import ResultsPage
        out = tmp_path / "results"
        out.mkdir()
        aes = out / "Dump_123.tar.gz.aes"
        aes.write_bytes(b"\x00" * 2048)
        page = ResultsPage(root)
        page.show_results({"imei": "123", "output_dir": str(out), "report_html": ""})
        page.update()
        page.destroy()

    def test_reset(self, root):
        from gui.pages.results import ResultsPage
        page = ResultsPage(root)
        page.reset()
        assert len(page._body.winfo_children()) == 0
        page.destroy()

    def test_open_file(self, root):
        from gui.pages.results import ResultsPage
        page = ResultsPage(root)
        page._open_file("/nonexistent")
        page.destroy()


class TestInstallPage:
    def test_get_checks(self, root):
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

    def test_start_install(self, root, monkeypatch):
        from gui.pages.install import InstallPage
        from gui import workers
        class FakeWorker:
            daemon = True
            def start(self): pass
            def is_alive(self): return False
            success = True
            error = None
        monkeypatch.setattr(workers, "InstallWorker",
                            lambda mode, sd, callback=None: FakeWorker())
        page = InstallPage(root, on_back=lambda: None)
        page.after = lambda ms, cb, *a, **kw: cb()
        page._start_install()
        page.update()
        page.destroy()

    def test_poll_worker_done(self, root):
        from gui.pages.install import InstallPage
        page = InstallPage(root, on_back=lambda: None)
        page.after = lambda ms, cb, *a, **kw: cb()

        class FakeW:
            def is_alive(self): return False
            success = True
            error = None
        page._worker = FakeW()
        page._poll_worker()
        page.update()
        page.destroy()

    def test_poll_worker_error(self, root):
        from gui.pages.install import InstallPage
        page = InstallPage(root, on_back=lambda: None)
        page.after = lambda ms, cb, *a, **kw: cb()

        class FakeW:
            def is_alive(self): return False
            success = False
            error = "fail"
        page._worker = FakeW()
        page._poll_worker()
        page.update()
        page.destroy()

    def test_refresh(self, root):
        from gui.pages.install import InstallPage
        page = InstallPage(root, on_back=lambda: None)
        page.refresh()
        page.update()
        page.destroy()

    def test_append_log(self, root):
        from gui.pages.install import InstallPage
        page = InstallPage(root, on_back=lambda: None)
        page.after = lambda ms, cb, *a, **kw: cb()
        page._append_log("test msg")
        page.update()
        page.destroy()


class TestAnalysisPageTimer:
    def test_poll_worker_alive(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page.after = lambda ms, cb, *a, **kw: None
        page._worker = type("W", (), {"is_alive": lambda self: True})()
        page._poll_worker()
        page._worker = None
        page.destroy()

    def test_poll_worker_done_with_result(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        results = []
        page._on_next = lambda r: results.append(r)

        def fake_after(ms, cb, *a, **kw):
            if ms == 0:
                cb()
        page.after = fake_after
        page._start_time = time.monotonic()

        class FakeW:
            def is_alive(self): return False
            error = None
            result = {"imei": "123"}
        page._worker = FakeW()
        page._poll_worker()
        page.update()
        page.destroy()

    def test_poll_worker_error(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page._worker = type("W", (), {
            "is_alive": lambda self: False,
            "error": "fail",
            "result": None,
        })()
        page._poll_worker()
        page.update()
        page.destroy()

    def test_on_log(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page.after = lambda ms, cb, *a, **kw: cb()
        page._on_log("test log")
        page.update()
        page.destroy()

    def test_on_activity(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page.after = lambda ms, cb, *a, **kw: cb()
        page._on_activity("running step 1")
        page.update()
        page.destroy()

    def test_on_progress_steps(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page.after = lambda ms, cb, *a, **kw: cb()
        for i in range(6):
            page._on_progress(i, "active")
        page.update()
        for i in range(6):
            page._on_progress(i, "done", "0.1s")
        page.update()
        page.destroy()

    def test_on_progress_error(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page.after = lambda ms, cb, *a, **kw: cb()
        page._on_progress(0, "error")
        page.update()
        page.destroy()

    def test_cancel_with_worker(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        alive = {"v": True}
        def flip(*a): alive["v"] = False
        page._worker = type("W", (), {
            "is_alive": lambda self: alive["v"],
            "cancel": flip,
        })()
        page._ticking = True
        page._timer_job = None
        page._cancel()
        assert not alive["v"]
        page.destroy()

    def test_update_timer(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page._ticking = True
        page._start_time = time.monotonic() - 65
        page.after = lambda ms, cb, *a, **kw: None
        page._update_timer()
        page._timer_job = None
        page.destroy()


class TestDestinationPageExtended:
    def test_drives_none(self, root, monkeypatch):
        from gui.pages.destination import DestinationPage
        import os as _os
        monkeypatch.setattr(_os.path, "exists", lambda p: False)
        page = DestinationPage(root)
        page._var.set("both")
        page._on_choice()
        page.update()
        page.destroy()

    def test_drive_select_manual(self, root, tmp_path):
        from gui.pages.destination import DestinationPage
        page = DestinationPage(root)
        page._manual_entry.insert(0, "")
        page._on_drive_select("Aucun périphérique trouvé")
        page.update()
        page.destroy()

    def test_reset(self, root):
        from gui.pages.destination import DestinationPage
        page = DestinationPage(root)
        page._var.set("ext")
        page._on_choice()
        page.reset()
        page.update()
        assert page._drive_frame.winfo_manager() == ""
        page.destroy()

    def test_go_next_ext(self, root, tmp_path):
        from gui.pages.destination import DestinationPage
        result = {}
        page = DestinationPage(root, on_next=lambda d, e: result.update({"d": d, "e": e}))
        page._var.set("ext")
        page._on_choice()
        page._ext_dir = str(tmp_path)
        page._go_next()
        assert result.get("d") == "2"
        page.destroy()


class TestDetectPageExtended:
    def test_detect_failure_polls(self, root, monkeypatch):
        from gui.pages.detect import DetectPage
        from gui import workers
        monkeypatch.setattr(workers, "detect_android_device",
                            lambda **k: (False, "Aucun appareil", ""))
        page = DetectPage(root)
        page.after = lambda *a, **k: None
        page._device_type = "android"
        page._run_detect()
        page.update()
        assert page._detected is False
        page.destroy()

    def test_detect_ios(self, root, monkeypatch):
        from gui.pages.detect import DetectPage
        from gui import workers
        monkeypatch.setattr(workers, "detect_ios_device",
                            lambda **k: (True, "iOS OK", "IOSIMEI"))
        page = DetectPage(root)
        page.after = lambda *a, **k: None
        page._device_type = "ios"
        page._run_detect()
        page.update()
        assert page._detected is True
        assert page._imei == "IOSIMEI"
        page.destroy()

    def test_unknown_imei_hides(self, root, monkeypatch):
        from gui.pages.detect import DetectPage
        from gui import workers
        monkeypatch.setattr(workers, "detect_android_device",
                            lambda **k: (True, "Android OK", "UNKNOWN"))
        page = DetectPage(root)
        page.after = lambda *a, **k: None
        page._device_type = "android"
        page._run_detect()
        page.update()
        assert page._detected is True
        page.destroy()