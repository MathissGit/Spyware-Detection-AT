import customtkinter as ctk
from gui.theme import *


class DetectPage(ctk.CTkFrame):
    def __init__(self, master, on_next=None, on_back=None):
        super().__init__(master, fg_color=BG_MAIN, corner_radius=0)
        self._on_next = on_next
        self._on_back = on_back
        self._device_type = None
        self._mode = "direct"
        self._imei = ""
        self._detected = False
        self._polling = False

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 0))
        ctk.CTkButton(header, text="← Retour", font=FONT_BTN_SM,
                      fg_color="transparent", hover_color=BG_CARD,
                      text_color=TEXT_DIM, width=80, command=self._on_back).pack(side="left")
        ctk.CTkLabel(header, text="Détection de l'appareil", font=FONT_TITLE,
                     text_color=TEXT).pack(side="left", padx=20)

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.45, anchor="center")

        self._status_dot = ctk.CTkLabel(center, text="", width=20, height=20,
                                        corner_radius=10, fg_color=BORDER)
        self._status_dot.pack(pady=(0, 16))

        self._status_label = ctk.CTkLabel(center, text="Branchez votre appareil par USB...",
                                          font=FONT_SUBTITLE, text_color=TEXT_DIM)
        self._status_label.pack(pady=(0, 8))

        self._imei_label = ctk.CTkLabel(center, text="", font=FONT_MONO,
                                        text_color=SECONDARY)
        self._imei_label.pack(pady=(0, 8))

        self._detail_label = ctk.CTkLabel(center, text="", font=FONT_SMALL,
                                          text_color=TEXT_DIM, wraplength=400)
        self._detail_label.pack(pady=(0, 20))

        self._spinner = ctk.CTkProgressBar(center, width=200, height=4, fg_color=BORDER,
                                           progress_color=PRIMARY)
        self._spinner.pack(pady=(0, 8))
        self._spinner.set(0)

        btn_frame = ctk.CTkFrame(center, fg_color="transparent")
        btn_frame.pack()

        self._refresh_btn = ctk.CTkButton(btn_frame, text="⟳ Actualiser", font=FONT_BTN_SM,
                                          fg_color=BG_CARD_H, hover_color=BORDER,
                                          text_color=TEXT, height=38, width=160,
                                          corner_radius=8, command=self._detect)
        self._refresh_btn.pack(side="left", padx=6)

        self._next_btn = ctk.CTkButton(btn_frame, text="Continuer →", font=FONT_BTN_SM,
                                       fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                                       text_color=BG_MAIN, height=38, width=160,
                                       corner_radius=8, state="disabled",
                                       command=self._go_next)
        self._next_btn.pack(side="left", padx=6)

    def set_mode(self, mode):
        self._mode = mode

    def set_device_type(self, dtype):
        self._device_type = dtype
        self._detected = False
        self._imei = ""
        self._status_dot.configure(fg_color=PRIMARY)
        self._spinner.configure(progress_color=PRIMARY)
        self._spinner.set(0.3)
        self._status_label.configure(text="Recherche en cours...",
                                     text_color=PRIMARY)
        self._imei_label.configure(text="")
        self._detail_label.configure(text=f"Appareil: {'Android' if dtype == 'android' else 'iOS'}")
        self._next_btn.configure(state="disabled")
        self._detect()

    def _detect(self):
        if self._polling:
            return
        self._polling = True
        self._status_dot.configure(fg_color=PRIMARY)
        self._spinner.set(0.3)
        self._status_label.configure(text="Recherche en cours...", text_color=PRIMARY)
        self.after(100, self._run_detect)

    def _run_detect(self):
        from gui.workers import detect_android_device, detect_ios_device
        if self._device_type == "android":
            found, msg, imei = detect_android_device(mode=self._mode)
        else:
            found, msg, imei = detect_ios_device(mode=self._mode)
        self._polling = False
        if found:
            self._detected = True
            self._imei = imei
            self._spinner.set(0)
            self._status_dot.configure(fg_color=SUCCESS)
            self._status_label.configure(text=msg, text_color=SUCCESS)
            self._imei_label.configure(text=f"IMEI: {imei}" if imei != "UNKNOWN" else "")
            self._next_btn.configure(state="normal")
        else:
            self._detected = False
            self._spinner.set(0)
            self._status_dot.configure(fg_color=DANGER)
            self._status_label.configure(text=msg, text_color=DANGER)
            self._imei_label.configure(text="")
            self._next_btn.configure(state="disabled")
            self.after(3000, self._detect)

    def _go_next(self):
        if self._detected and self._on_next:
            self._on_next(self._imei)

    def reset(self):
        self._detected = False
        self._imei = ""
        self._polling = False
        self._spinner.set(0)
        self._status_dot.configure(fg_color=BORDER)
        self._status_label.configure(text="Branchez votre appareil USB...", text_color=TEXT_DIM)
        self._imei_label.configure(text="")
        self._next_btn.configure(state="disabled")