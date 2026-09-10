"""Couverture des branches GUI restantes (app, pages, sandbox_client)."""
import builtins
import os

import customtkinter as ctk
import pytest


@pytest.fixture(scope="module")
def root():
    r = ctk.CTk()
    r.withdraw()
    r.update()
    yield r
    r.destroy()


@pytest.fixture(scope="module", autouse=True)
def icon_path_patched():
    """Les pages GUI cherchent <root>/gui/icon.png (absente) : on pointe vers la racine."""
    import os as _os
    import tkinter as _tk
    root_icon = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icon.png")
    _orig_isfile = _os.path.isfile
    try:
        _orig_photoimage = _tk.PhotoImage
    except Exception:
        yield
        return

    class _IconPhotoImage(_tk.PhotoImage):
        def __init__(self, *a, **k):
            k["file"] = root_icon
            super().__init__(*a, **k)

        def subsample(self, *a):
            return self

    _os.path.isfile = lambda p: p.endswith("icon.png") or _orig_isfile(p)
    _tk.PhotoImage = _IconPhotoImage
    try:
        yield
    finally:
        _os.path.isfile = _orig_isfile
        _tk.PhotoImage = _orig_photoimage


@pytest.fixture(scope="module")
def app():
    from gui.app import SpywareDetectionApp
    a = SpywareDetectionApp(mode="direct")
    a.withdraw()
    a.update()
    yield a
    a.destroy()


class _RaisingPhotoImage:
    """Substitut de tkinter.PhotoImage qui échoue quand on lui donne un fichier."""

    def __init__(self, *a, **k):
        if "file" in k:
            raise RuntimeError("icône indisponible")
        raise RuntimeError("PhotoImage inattendu")


def _force_icon_file(monkeypatch):
    """L'agenda PhotoImage des pages GUI ne voit que <root>/gui/icon.png."""
    import os
    _orig_isfile = os.path.isfile
    monkeypatch.setattr("os.path.isfile",
                        lambda p: p.endswith("icon.png") or _orig_isfile(p))


class TestAppCoverage:
    def test_show_mode(self, app):
        assert app._logo_img is not None
        app._show_mode()
        assert app._pages["mode"].winfo_manager() == "pack"

    def test_on_device_detected(self, app):
        app._on_device_detected("IMEI123")
        assert app._state["imei"] == "IMEI123"
        assert app._pages["destination"].winfo_manager() == "pack"

    def test_logo_photoimage_error(self, monkeypatch):
        import tkinter as tk
        _force_icon_file(monkeypatch)
        monkeypatch.setattr(tk, "PhotoImage", _RaisingPhotoImage)
        from gui.app import SpywareDetectionApp
        a = SpywareDetectionApp(mode="direct")
        a.withdraw()
        a.update()
        assert a._logo_img is None
        a.destroy()


class TestHomePageCoverage:
    def test_photoimage_error(self, root, monkeypatch):
        import tkinter as tk
        _force_icon_file(monkeypatch)
        monkeypatch.setattr(tk, "PhotoImage", _RaisingPhotoImage)
        from gui.pages.home import HomePage
        page = HomePage(root)
        assert page._home_img is None
        page.destroy()

    def test_photoimage_displayed(self, root):
        from gui.pages.home import HomePage
        page = HomePage(root)
        assert page._home_img is not None
        page.destroy()


class TestAnalysisPageCoverage:
    def test_log_overflow(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page.after = lambda ms, cb, *a, **kw: cb()
        page._log_max_lines = 5
        page._log_box.configure(state="normal")
        for i in range(20):
            page._log_box.insert("end", f"log line {i}\n")
        page._log_box.configure(state="disabled")
        page._on_log("final line")
        content = page._log_box.get("1.0", "end-1c")
        assert "final line" in content
        page.destroy()

    def test_poll_worker_cancels_timer(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        jid = page.after(100000, lambda: None)
        page._timer_job = jid
        class FakeW:
            def is_alive(self): return False
            error = None
            result = None
        page._worker = FakeW()
        page._poll_worker()
        assert page._timer_job is None
        page.destroy()

    def test_update_timer_stops(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        page._ticking = False
        page._update_timer()
        assert page._timer_job is None
        page.destroy()

    def test_reset_cancels_timer(self, root):
        from gui.pages.analysis import AnalysisPage
        page = AnalysisPage(root)
        jid = page.after(100000, lambda: None)
        page._timer_job = jid
        page.reset()
        assert page._timer_job is None
        page.destroy()


class TestDestinationPageCoverage:
    def test_refresh_drives_found(self, root):
        from gui.pages.destination import DestinationPage
        page = DestinationPage(root)
        page._get_drives = lambda: ["/media/user/USB"]
        page._refresh_drives()
        assert page._ext_dir == "/media/user/USB"
        page.destroy()

    def test_drive_select_valid_manual(self, root, tmp_path):
        from gui.pages.destination import DestinationPage
        page = DestinationPage(root)
        page._manual_entry.insert(0, str(tmp_path))
        page._on_drive_select("/media/user/USB")
        assert page._ext_dir == str(tmp_path)
        page.destroy()

    def test_get_drives_linux(self, root, monkeypatch):
        from gui.pages.destination import DestinationPage
        page = DestinationPage(root)
        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setattr(os, "getenv", lambda k, d="": "user")
        def fake_exists(p):
            return p == "/media/user"
        monkeypatch.setattr(os.path, "exists", fake_exists)
        def fake_listdir(p):
            return ["USB1", "note.txt"] if p == "/media/user" else []
        monkeypatch.setattr(os, "listdir", fake_listdir)
        def fake_isdir(p):
            return p == "/media/user/USB1"
        monkeypatch.setattr(os.path, "isdir", fake_isdir)
        assert page._get_drives() == ["/media/user/USB1"]
        page.destroy()

    def test_get_drives_darwin(self, root, monkeypatch):
        from gui.pages.destination import DestinationPage
        page = DestinationPage(root)
        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr(os.path, "exists",
                            lambda p: p == "/Volumes")
        monkeypatch.setattr(os, "listdir",
                            lambda p: ["Macintosh HD", "ABC"])
        def fake_isdir(p):
            return str(p).startswith("/Volumes")
        monkeypatch.setattr(os.path, "isdir", fake_isdir)
        assert page._get_drives() == ["/Volumes/ABC"]
        page.destroy()


class TestDetectPageCoverage:
    def test_polling_guard(self, root):
        from gui.pages.detect import DetectPage
        page = DetectPage(root)
        page._polling = True
        page._detect()
        assert page._polling is True
        page.destroy()


class TestInstallPageCoverage:
    def test_has_tk_error(self, root, monkeypatch):
        real_import = builtins.__import__
        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "tkinter":
                raise ImportError("désactivé")
            return real_import(name, globals, locals, fromlist, level)
        monkeypatch.setattr(builtins, "__import__", fake_import)
        from gui.pages.install import InstallPage
        page = InstallPage(root, on_back=lambda: None)
        assert page._has_tk() is False
        page.destroy()

    def test_poll_worker_alive_reschedule(self, root):
        from gui.pages.install import InstallPage
        page = InstallPage(root, on_back=lambda: None)
        page.after = lambda ms, cb, *a, **kw: None
        class FakeW:
            def is_alive(self): return True
        page._worker = FakeW()
        page._poll_worker()
        page.destroy()


class TestPasswordPageCoverage:
    def test_pwd1_empty(self, root):
        from gui.pages.password import PasswordPage
        page = PasswordPage(root)
        page._pwd1.insert(0, "")
        page._pwd2.insert(0, "secret")
        page._check_match(None)
        assert page._next_btn.cget("state") == "disabled"
        page.destroy()


class TestResultsPageCoverage:
    def test_show_results_twice(self, root):
        from gui.pages.results import ResultsPage
        page = ResultsPage(root)
        page.show_results({"imei": "1", "output_dir": "", "report_html": ""})
        page.show_results({"imei": "2", "output_dir": "", "report_html": ""})
        page.update()
        page.destroy()

    def test_open_file_error(self, root, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("navigateur absent")
        monkeypatch.setattr("webbrowser.open", boom)
        from gui.pages.results import ResultsPage
        page = ResultsPage(root)
        page._open_file("/nonexistent")
        page.destroy()

    def test_reset_with_children(self, root):
        from gui.pages.results import ResultsPage
        page = ResultsPage(root)
        page.show_results({"imei": "1", "output_dir": "", "report_html": ""})
        page.update()
        page.reset()
        assert len(page._body.winfo_children()) == 0
        page.destroy()


class TestSandboxClientCoverage:
    def test_client_factory(self):
        from gui import sandbox_client
        c = sandbox_client._client()
        assert isinstance(c, sandbox_client.SandboxClient)


class TestCreateIconCoverage:
    def test_ensure_icon_write_error(self, monkeypatch, tmp_path):
        from gui import create_icon
        def boom(*a, **k):
            raise OSError("disque plein")
        monkeypatch.setattr(create_icon, "write_icon", boom)
        assert create_icon.ensure_icon(str(tmp_path)) is None