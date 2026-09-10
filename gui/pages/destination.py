import os
import platform
import customtkinter as ctk
from gui.theme import *


class DestinationPage(ctk.CTkFrame):
    def __init__(self, master, on_next=None, on_back=None):
        super().__init__(master, fg_color=BG_MAIN, corner_radius=0)
        self._on_next = on_next
        self._on_back = on_back
        self._dest = None
        self._ext_dir = None
        self._script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        from gui.workers import LOCAL_DEST_DIR

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 0))
        ctk.CTkButton(header, text="← Retour", font=FONT_BTN_SM,
                      fg_color="transparent", hover_color=BG_CARD,
                      text_color=TEXT_DIM, width=80, command=self._on_back).pack(side="left")
        ctk.CTkLabel(header, text="Destination", font=FONT_TITLE, text_color=TEXT).pack(side="left", padx=20)

        ctk.CTkLabel(self, text="Où sauvegarder l'archive chiffrée ?",
                     font=FONT_SUBTITLE, text_color=TEXT_DIM).pack(pady=(8, 16))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=40)

        self._var = ctk.StringVar(value="local")

        r1 = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=10)
        r1.pack(fill="x", pady=4)
        ctk.CTkRadioButton(r1, text=f"  Uniquement en local ({LOCAL_DEST_DIR})",
                           variable=self._var, value="local",
                           font=FONT_BODY, text_color=TEXT,
                           fg_color=PRIMARY, hover_color=SECONDARY,
                           command=self._on_choice).pack(anchor="w", padx=16, pady=10)

        r2 = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=10)
        r2.pack(fill="x", pady=4)
        ctk.CTkRadioButton(r2, text="  Uniquement sur un périphérique externe",
                           variable=self._var, value="ext",
                           font=FONT_BODY, text_color=TEXT,
                           fg_color=PRIMARY, hover_color=SECONDARY,
                           command=self._on_choice).pack(anchor="w", padx=16, pady=10)

        r3 = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=10)
        r3.pack(fill="x", pady=4)
        ctk.CTkRadioButton(r3, text="  Les deux (Copie locale + externe)",
                           variable=self._var, value="both",
                           font=FONT_BODY, text_color=TEXT,
                           fg_color=PRIMARY, hover_color=SECONDARY,
                           command=self._on_choice).pack(anchor="w", padx=16, pady=10)

        self._drive_frame = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=10)
        ctk.CTkLabel(self._drive_frame, text="Périphérique externe", font=FONT_BTN,
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(12, 4))

        self._drive_combo = ctk.CTkComboBox(self._drive_frame, values=[""],
                                            font=FONT_BODY, fg_color=BG_INPUT,
                                            border_color=BORDER, button_color=PRIMARY,
                                            button_hover_color=PRIMARY_HOVER,
                                            dropdown_fg_color=BG_CARD,
                                            command=self._on_drive_select)
        self._drive_combo.pack(fill="x", padx=16, pady=(0, 4))

        ctk.CTkLabel(self._drive_frame, text="ou entrez un chemin manuellement :",
                     font=FONT_SMALL, text_color=TEXT_DIM).pack(anchor="w", padx=16)

        self._manual_entry = ctk.CTkEntry(self._drive_frame, font=FONT_BODY,
                                          fg_color=BG_INPUT, border_color=BORDER,
                                          text_color=TEXT, placeholder_text="/media/user/USB...")
        self._manual_entry.pack(fill="x", padx=16, pady=(4, 12))

        self._next_btn = ctk.CTkButton(self, text="Continuer →", font=FONT_BTN,
                                       fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                                       text_color=BG_MAIN, height=44, width=200,
                                       corner_radius=10, state="disabled",
                                       command=self._go_next)
        self._next_btn.pack(pady=(16, 30))

    def _on_choice(self):
        choice = self._var.get()
        if choice in ("ext", "both"):
            self._drive_frame.pack(fill="x", pady=(8, 0))
            self._refresh_drives()
        else:
            self._drive_frame.pack_forget()
            self._ext_dir = None
            self._next_btn.configure(state="normal")

    def _refresh_drives(self):
        drives = self._get_drives()
        if drives:
            self._drive_combo.configure(values=drives)
            self._drive_combo.set(drives[0])
            self._ext_dir = drives[0]
        else:
            self._drive_combo.configure(values=["Aucun périphérique trouvé"])
            self._drive_combo.set("Aucun périphérique trouvé")
            self._ext_dir = None
        self._next_btn.configure(state="normal")

    def _on_drive_select(self, selection):
        manual = self._manual_entry.get().strip()
        if manual and os.path.isdir(manual):
            self._ext_dir = manual
        else:
            self._ext_dir = selection if selection != "Aucun périphérique trouvé" else None
        self._next_btn.configure(state="normal" if self._ext_dir or self._var.get() == "local" else "disabled")

    def _get_drives(self):
        system = platform.system()
        drives = []
        if system == "Linux":
            user = os.getenv("USER", "")
            for base in [f"/media/{user}", "/mnt"]:
                if os.path.exists(base):
                    for d in os.listdir(base):
                        p = os.path.join(base, d)
                        if os.path.isdir(p):
                            drives.append(p)
        elif system == "Darwin":
            if os.path.exists("/Volumes"):
                for d in os.listdir("/Volumes"):
                    if d != "Macintosh HD" and os.path.isdir(f"/Volumes/{d}"):
                        drives.append(f"/Volumes/{d}")
        return drives

    def _go_next(self):
        if self._on_next:
            choice = self._var.get()
            dest_map = {"local": "1", "ext": "2", "both": "3"}
            manual = self._manual_entry.get().strip()
            ext = manual if manual and os.path.isdir(manual) else self._ext_dir
            self._on_next(dest_map[choice], ext)

    def reset(self):
        self._var.set("local")
        self._ext_dir = None
        self._drive_frame.pack_forget()
        self._next_btn.configure(state="disabled")
