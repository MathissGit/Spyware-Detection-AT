import customtkinter as ctk
import tkinter as _tk
from gui.theme import *
from gui.widgets.step_indicator import StepIndicator
from gui.pages.home import HomePage
from gui.pages.install import InstallPage
from gui.pages.mode import ModePage
from gui.pages.device_type import DeviceTypePage
from gui.pages.detect import DetectPage
from gui.pages.destination import DestinationPage
from gui.pages.password import PasswordPage
from gui.pages.analysis import AnalysisPage
from gui.pages.results import ResultsPage


ANALYSIS_STEPS = [
    "Mode d'analyse",
    "Type d'appareil",
    "Détection",
    "Destination",
    "Chiffrement",
    "Analyse",
    "Résultats",
]


class SpywareDetectionApp(ctk.CTk):
    def __init__(self, mode="direct"):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._default_mode = mode

        self.title("Spyware Detection - Automated Forensics")
        self.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.minsize(900, 600)
        self.configure(fg_color=BG_MAIN)

        self._state = {
            "mode": self._default_mode,
            "device_type": None,
            "imei": "",
            "dest_choice": "1",
            "ext_dir": None,
            "password": "",
        }

        self._sidebar = ctk.CTkFrame(self, fg_color=BG_MAIN, width=200, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=16, pady=(20, 24))
        self._logo_img = None
        import os as _os
        _icon_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "icon.png")
        if _os.path.isfile(_icon_path):
            try:
                self._logo_img = _tk.PhotoImage(file=_icon_path).subsample(10)
                ctk.CTkLabel(logo_frame, image=self._logo_img, text="",
                             fg_color="transparent").pack()
            except Exception:
                pass
        ctk.CTkLabel(logo_frame, text="SPYWARE\nDETECTION", font=(FONT_FAMILY, 13, "bold"),
                     text_color=PRIMARY, justify="center").pack()

        self._step_indicator = StepIndicator(self._sidebar, ANALYSIS_STEPS)
        self._step_indicator.pack(fill="both", expand=True, padx=8)

        self._main = ctk.CTkFrame(self, fg_color=BG_MAIN, corner_radius=0)
        self._main.pack(side="left", fill="both", expand=True)

        self._pages = {}
        self._current_page = None

        self._pages["home"] = HomePage(self._main,
                                       on_analyze=self._start_analysis_flow,
                                       on_install=self._show_install)
        self._pages["install"] = InstallPage(self._main, on_back=self._show_home)
        self._pages["mode"] = ModePage(self._main,
                                       on_next=self._on_mode_selected,
                                       on_back=self._show_home)
        self._pages["device_type"] = DeviceTypePage(self._main,
                                                    on_next=self._on_device_type_selected,
                                                    on_back=self._show_mode)
        self._pages["detect"] = DetectPage(self._main,
                                           on_next=self._on_device_detected,
                                           on_back=self._show_device_type)
        self._pages["destination"] = DestinationPage(self._main,
                                                     on_next=self._on_destination_selected,
                                                     on_back=self._show_detect)
        self._pages["password"] = PasswordPage(self._main,
                                               on_next=self._on_password_set,
                                               on_back=self._show_destination)
        self._pages["analysis"] = AnalysisPage(self._main,
                                               on_next=self._on_analysis_done,
                                               on_back=self._show_password)
        self._pages["results"] = ResultsPage(self._main, on_home=self._show_home)

        self._show_home()

    def _show_page(self, name, step_index=None):
        if self._current_page:
            self._current_page.pack_forget()
        page = self._pages[name]
        page.pack(fill="both", expand=True)
        self._current_page = page
        if step_index is not None:
            self._step_indicator.set_step(step_index)
        else:
            self._step_indicator.reset()
        if hasattr(page, "refresh"):
            page.refresh()

    def _show_home(self):
        self._show_page("home")

    def _show_install(self):
        self._show_page("install")

    def _start_analysis_flow(self):
        self._state = {"mode": self._default_mode, "device_type": None, "imei": "",
                        "dest_choice": "1", "ext_dir": None, "password": ""}
        self._pages["mode"].reset()
        self._show_page("mode", step_index=0)

    def _show_mode(self):
        self._show_page("mode", step_index=0)

    def _on_mode_selected(self, mode):
        self._state["mode"] = mode
        self._pages["device_type"].reset()
        self._show_page("device_type", step_index=1)

    def _show_device_type(self):
        self._show_page("device_type", step_index=1)

    def _on_device_type_selected(self, dtype):
        self._state["device_type"] = dtype
        self._pages["detect"].set_mode(self._state["mode"])
        self._pages["detect"].set_device_type(dtype)
        self._show_page("detect", step_index=2)

    def _show_detect(self):
        self._show_page("detect", step_index=2)

    def _on_device_detected(self, imei):
        self._state["imei"] = imei
        self._pages["destination"].reset()
        self._show_page("destination", step_index=3)

    def _show_destination(self):
        self._show_page("destination", step_index=3)

    def _on_destination_selected(self, dest_choice, ext_dir):
        self._state["dest_choice"] = dest_choice
        self._state["ext_dir"] = ext_dir
        self._pages["password"].reset()
        self._show_page("password", step_index=4)

    def _show_password(self):
        self._show_page("password", step_index=4)

    def _on_password_set(self, password):
        self._state["password"] = password
        self._pages["analysis"].reset()
        self._show_page("analysis", step_index=5)
        self._pages["analysis"].start_analysis(
            self._state["device_type"],
            self._state["password"],
            self._state["dest_choice"],
            self._state["ext_dir"],
            self._state["mode"],
        )

    def _on_analysis_done(self, result):
        self._pages["results"].show_results(result)
        self._show_page("results", step_index=6)
