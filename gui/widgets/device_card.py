import customtkinter as ctk
from gui.theme import *


class DeviceCard(ctk.CTkFrame):
    def __init__(self, master, label, description="", command=None, **kw):
        super().__init__(master, fg_color=BG_CARD, corner_radius=12,
                         border_width=2, border_color=BORDER, cursor="hand2", **kw)
        self._command = command
        self._selected = False

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        self.title = ctk.CTkLabel(self, text=label, font=FONT_BTN, text_color=TEXT)
        self.title.pack(pady=(20, 4))
        self.title.bind("<Button-1>", self._on_click)

        if description:
            self.desc = ctk.CTkLabel(self, text=description, font=FONT_SMALL,
                                     text_color=TEXT_DIM, wraplength=200)
            self.desc.pack(pady=(0, 20), padx=16)
            self.desc.bind("<Button-1>", self._on_click)
        else:
            ctk.CTkLabel(self, text="", height=16).pack()

    def _on_click(self, e=None):
        if self._command:
            self._command()

    def _on_enter(self, e=None):
        if not self._selected:
            self.configure(border_color=PRIMARY)

    def _on_leave(self, e=None):
        if not self._selected:
            self.configure(border_color=BORDER)

    def select(self):
        self._selected = True
        self.configure(border_color=PRIMARY, fg_color=BG_CARD_H)

    def deselect(self):
        self._selected = False
        self.configure(border_color=BORDER, fg_color=BG_CARD)