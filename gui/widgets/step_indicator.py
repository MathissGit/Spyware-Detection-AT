import customtkinter as ctk
from gui.theme import *


class StepIndicator(ctk.CTkFrame):
    def __init__(self, master, steps, **kw):
        super().__init__(master, fg_color=BG_MAIN, corner_radius=0, **kw)
        self.steps = steps
        self.current = -1
        self.labels = []
        self.dots = []
        self.lines = []

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(expand=True, padx=20)

        for i, label in enumerate(steps):
            row = ctk.CTkFrame(container, fg_color="transparent")
            row.pack(fill="x", pady=4)

            dot_frame = ctk.CTkFrame(row, width=32, height=32, fg_color="transparent")
            dot_frame.pack(side="left")
            dot_frame.pack_propagate(False)

            dot = ctk.CTkLabel(dot_frame, text=str(i + 1), width=28, height=28,
                               corner_radius=14, font=FONT_BTN_SM,
                               fg_color=BORDER, text_color=TEXT_DIM)
            dot.pack(expand=True)
            self.dots.append(dot)

            lbl = ctk.CTkLabel(row, text=label, font=FONT_SMALL, text_color=TEXT_DIM,
                               anchor="w")
            lbl.pack(side="left", padx=(10, 0), fill="x", expand=True)
            self.labels.append(lbl)

            if i < len(steps) - 1:
                line = ctk.CTkLabel(container, text="│", font=("Consolas", 14),
                                    text_color=BORDER, anchor="w", padx=14)
                line.pack(fill="x", pady=0)
                self.lines.append(line)

    def set_step(self, index):
        if index == self.current:
            return
        self.current = index
        for i in range(len(self.steps)):
            if i < index:
                self.dots[i].configure(fg_color=SUCCESS, text_color=BG_MAIN, text="✓")
                self.labels[i].configure(text_color=TEXT_DIM)
            elif i == index:
                self.dots[i].configure(fg_color=PRIMARY, text_color=BG_MAIN)
                self.labels[i].configure(text_color=PRIMARY, font=(FONT_FAMILY, 12, "bold"))
            else:
                self.dots[i].configure(fg_color=BORDER, text_color=TEXT_DIM, text=str(i + 1))
                self.labels[i].configure(text_color=TEXT_DIM)
        for i, line in enumerate(self.lines):
            if i < index:
                line.configure(text_color=SUCCESS)
            else:
                line.configure(text_color=BORDER)

    def reset(self):
        self.current = -1
        for i in range(len(self.steps)):
            self.dots[i].configure(fg_color=BORDER, text_color=TEXT_DIM, text=str(i + 1))
            self.labels[i].configure(text_color=TEXT_DIM, font=FONT_SMALL)
        for line in self.lines:
            line.configure(text_color=BORDER)
