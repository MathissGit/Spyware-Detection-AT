import customtkinter as ctk
from gui.theme import *
from gui.widgets.device_card import DeviceCard


class DeviceTypePage(ctk.CTkFrame):
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

        ctk.CTkLabel(header, text="Type d'appareil", font=FONT_TITLE, text_color=TEXT).pack(side="left", padx=20)

        ctk.CTkLabel(self, text="Quel appareil souhaitez-vous analyser ?",
                     font=FONT_SUBTITLE, text_color=TEXT_DIM).pack(pady=(8, 24))

        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(expand=True)

        self._android_card = DeviceCard(cards_frame, label="Android",
                                        description="Smartphones et tablettes Android (Samsung, Google, Xiaomi...)",
                                        command=lambda: self._select("android"))
        self._android_card.pack(side="left", padx=20, ipadx=20, ipady=10)

        self._ios_card = DeviceCard(cards_frame, label="iOS / iPhone",
                                    description="iPhone et iPad (Apple iOS/iPadOS)",
                                    command=lambda: self._select("ios"))
        self._ios_card.pack(side="left", padx=20, ipadx=20, ipady=10)

        self._next_btn = ctk.CTkButton(self, text="Continuer →", font=FONT_BTN,
                                       fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                                       text_color=BG_MAIN, height=44, width=200,
                                       corner_radius=10, state="disabled",
                                       command=self._go_next)
        self._next_btn.pack(pady=(30, 30))

    def _select(self, dtype):
        self._selected = dtype
        self._android_card.select() if dtype == "android" else self._android_card.deselect()
        self._ios_card.select() if dtype == "ios" else self._ios_card.deselect()
        self._next_btn.configure(state="normal")

    def _go_next(self):
        if self._selected and self._on_next:
            self._on_next(self._selected)

    def reset(self):
        self._selected = None
        self._android_card.deselect()
        self._ios_card.deselect()
        self._next_btn.configure(state="disabled")
