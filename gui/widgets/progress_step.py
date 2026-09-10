import customtkinter as ctk
from gui.theme import *


class ProgressStep(ctk.CTkFrame):
    STATES = ("pending", "active", "done", "error")

    def __init__(self, master, label, index=0, **kw):
        super().__init__(master, fg_color=BG_CARD, corner_radius=10, **kw)
        self._state = "pending"
        self._index = index

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=10)

        self._dot = ctk.CTkLabel(row, text=str(index + 1), width=28, height=28,
                                 corner_radius=14, font=FONT_BTN_SM,
                                 fg_color=BORDER, text_color=TEXT_DIM)
        self._dot.pack(side="left")

        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", padx=(12, 0), fill="x", expand=True)

        self._label = ctk.CTkLabel(text_frame, text=label, font=FONT_BODY, text_color=TEXT_DIM,
                                   anchor="w")
        self._label.pack(anchor="w")

        self._time = ctk.CTkLabel(row, text="", font=FONT_SMALL, text_color=TEXT_DIM)
        self._time.pack(side="right")

    def set_state(self, state, elapsed=""):
        if state not in self.STATES:
            return
        self._state = state
        if state == "pending":
            self.configure(fg_color=BG_CARD)
            self._dot.configure(fg_color=BORDER, text_color=TEXT_DIM, text=str(self._index + 1))
            self._label.configure(text_color=TEXT_DIM)
            self._time.configure(text="")
        elif state == "active":
            self.configure(fg_color=BG_CARD_H)
            self._dot.configure(fg_color=PRIMARY, text_color=BG_MAIN, text=str(self._index + 1))
            self._label.configure(text_color=PRIMARY, font=(FONT_FAMILY, 13, "bold"))
        elif state == "done":
            self.configure(fg_color=BG_CARD)
            self._dot.configure(fg_color=SUCCESS, text_color=BG_MAIN, text="✓")
            self._label.configure(text_color=SUCCESS, font=FONT_BODY)
            if elapsed:
                self._time.configure(text=elapsed, text_color=SUCCESS)
        elif state == "error":
            self.configure(fg_color=BG_CARD)
            self._dot.configure(fg_color=DANGER, text_color=BG_LIGHT, text="✗")
            self._label.configure(text_color=DANGER)
            if elapsed:
                self._time.configure(text=elapsed, text_color=DANGER)

    def reset(self):
        self.set_state("pending")

    @property
    def state(self):
        return self._state
