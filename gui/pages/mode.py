import customtkinter as ctk
from gui.theme import *
from gui.widgets.device_card import DeviceCard


class ModePage(ctk.CTkFrame):
    def __init__(self, master, on_next=None, on_back=None):
        super().__init__(master, fg_color=BG_MAIN, corner_radius=0)
        self._on_next = on_next
        self._on_back = on_back
        self._selected = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 0))

        ctk.CTkButton(header, text="← Retour", font=FONT_BTN_SM,
                      fg_color="transparent", hover_color=BG_CARD,
                      text_color=TEXT_DIM, width=80, command=self._on_back).pack(side="left")

        ctk.CTkLabel(header, text="Mode d'analyse", font=FONT_TITLE, text_color=TEXT).pack(side="left", padx=20)

        ctk.CTkLabel(self, text="Choisissez le mode d'exécution de l'analyse",
                     font=FONT_SUBTITLE, text_color=TEXT_DIM).pack(pady=(8, 24))

        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(expand=True)

        self._sandbox_card = DeviceCard(cards_frame, label="Sandbox",
                                        description="Exécution dans une VM isolée (VirtualBox). Maximum de sécurité.",
                                        command=lambda: self._select("sandbox"))
        self._sandbox_card.pack(side="left", padx=20, ipadx=20, ipady=10)

        self._direct_card = DeviceCard(cards_frame, label="Mode Direct",
                                       description="Exécution locale sans isolation. Plus rapide mais moins sûr.",
                                       command=lambda: self._select("direct"))
        self._direct_card.pack(side="left", padx=20, ipadx=20, ipady=10)

        info_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        info_frame.pack(fill="x", padx=60, pady=(24, 0))
        self._info_label = ctk.CTkLabel(info_frame, text="Sélectionnez un mode pour continuer",
                                        font=FONT_BODY, text_color=TEXT_DIM, wraplength=500)
        self._info_label.pack(padx=20, pady=14)

        self._next_btn = ctk.CTkButton(self, text="Continuer →", font=FONT_BTN,
                                       fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                                       text_color=BG_MAIN, height=44, width=200,
                                       corner_radius=10, state="disabled",
                                       command=self._go_next)
        self._next_btn.pack(pady=(20, 30))

    def _select(self, mode):
        self._selected = mode
        self._sandbox_card.select() if mode == "sandbox" else self._sandbox_card.deselect()
        self._direct_card.select() if mode == "direct" else self._direct_card.deselect()
        self._next_btn.configure(state="normal")
        if mode == "sandbox":
            self._info_label.configure(text="Sandbox : Crée une VM Debian 12 isolée via VirtualBox.\n"
                                         "L'analyse s'effectue dans un environnement éphémère détruit à la sortie.")
        else:
            self._info_label.configure(text="Mode Direct : Exécute l'analyse directement sur votre machine.\n"
                                         "Plus rapide, mais sans isolation de sécurité.")

    def _go_next(self):
        if self._selected and self._on_next:
            self._on_next(self._selected)

    def reset(self):
        self._selected = None
        self._sandbox_card.deselect()
        self._direct_card.deselect()
        self._next_btn.configure(state="disabled")
        self._info_label.configure(text="Sélectionnez un mode pour continuer")
