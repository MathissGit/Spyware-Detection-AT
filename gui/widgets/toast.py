import customtkinter as ctk
from gui.theme import *


class Toast(ctk.CTkToplevel):
    def __init__(self, master, message, toast_type="info", duration=3000):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        colors = {
            "success": SUCCESS,
            "error": DANGER,
            "warning": WARNING,
            "info": PRIMARY,
        }
        color = colors.get(toast_type, PRIMARY)
        icons = {"success": "✓", "error": "✗", "warning": "!", "info": "i"}
        icon = icons.get(toast_type, "i")

        self.configure(fg_color=BG_CARD, corner_radius=10,
                       border_width=2, border_color=color)

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(padx=16, pady=10)

        ctk.CTkLabel(frame, text=icon, font=(FONT_FAMILY, 16, "bold"),
                     text_color=color, width=24).pack(side="left")
        ctk.CTkLabel(frame, text=message, font=FONT_BODY,
                     text_color=TEXT, wraplength=400).pack(side="left", padx=(8, 16))

        self.update_idletasks()
        pw = self.winfo_reqwidth()
        mw = master.winfo_width()
        x = mw - pw - 20
        y = 20
        self.geometry(f"+{x}+{y}")

        self.after(duration, self.destroy)
