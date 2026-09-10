import customtkinter as ctk
import tkinter as _tk
import os as _os
from gui.theme import *


class HomePage(ctk.CTkFrame):
    def __init__(self, master, on_analyze=None, on_install=None):
        super().__init__(master, fg_color=BG_MAIN, corner_radius=0)
        self._on_analyze = on_analyze
        self._on_install = on_install

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        self._home_img = None
        _icon_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "icon.png")
        if _os.path.isfile(_icon_path):
            try:
                self._home_img = _tk.PhotoImage(file=_icon_path).subsample(6)
                ctk.CTkLabel(center, image=self._home_img, text="",
                             fg_color="transparent").pack(pady=(0, 12))
            except Exception:
                pass

        banner = ctk.CTkLabel(center, text="SPYWARE\nDETECTION", font=FONT_TITLE,
                              text_color=PRIMARY, justify="center")
        banner.pack(pady=(0, 8))

        sub = ctk.CTkLabel(center, text="Automated Forensics with MVT",
                           font=FONT_SUBTITLE, text_color=TEXT_DIM)
        sub.pack(pady=(0, 40))

        btn_frame = ctk.CTkFrame(center, fg_color="transparent")
        btn_frame.pack()

        analyze_btn = ctk.CTkButton(btn_frame, text="  Nouvelle Analyse  ", font=FONT_BTN,
                                    fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                                    text_color=BG_MAIN, height=48, width=260,
                                    corner_radius=10, command=self._on_analyze)
        analyze_btn.pack(pady=8)

        install_btn = ctk.CTkButton(btn_frame, text="  Installer les dépendances  ", font=FONT_BTN_SM,
                                    fg_color="transparent", hover_color=BG_CARD_H,
                                    text_color=SECONDARY, height=40, width=260,
                                    corner_radius=10, border_width=1, border_color=SECONDARY,
                                    command=self._on_install)
        install_btn.pack(pady=4)

        footer = ctk.CTkLabel(center, text="Powered by Amnesty International MVT",
                              font=FONT_SMALL, text_color=TEXT_MUTED)
        footer.pack(pady=(40, 0))
