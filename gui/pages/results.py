import os
import webbrowser
import customtkinter as ctk
from gui.theme import *


class ResultsPage(ctk.CTkFrame):
    def __init__(self, master, on_home=None):
        super().__init__(master, fg_color=BG_MAIN, corner_radius=0)
        self._on_home = on_home
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 0))
        ctk.CTkLabel(header, text="Résultats de l'analyse", font=FONT_TITLE,
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(header, text="Accueil", font=FONT_BTN_SM,
                      fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                      text_color=BG_MAIN, height=36, width=100,
                      corner_radius=8, command=self._on_home).pack(side="right")

        self._body = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                             scrollbar_button_color=BORDER)
        self._body.pack(fill="both", expand=True, padx=30, pady=16)

    def show_results(self, result):
        for w in self._body.winfo_children():
            w.destroy()

        imei = result.get("imei", "UNKNOWN")
        output_dir = result.get("output_dir", "")
        report_html = result.get("report_html", "")

        banner = ctk.CTkFrame(self._body, fg_color=BG_CARD, corner_radius=12)
        banner.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(banner, text="Analyse terminée", font=FONT_BTN,
                     text_color=SUCCESS).pack(anchor="w", padx=20, pady=(14, 4))
        ctk.CTkLabel(banner, text=f"IMEI: {imei}", font=FONT_MONO,
                     text_color=SECONDARY).pack(anchor="w", padx=20)
        ctk.CTkLabel(banner, text=f"Résultats: {output_dir}", font=FONT_SMALL,
                     text_color=TEXT_DIM, wraplength=600).pack(anchor="w", padx=20, pady=(4, 14))

        report_file = None
        if output_dir and os.path.isdir(output_dir):
            for f in os.listdir(output_dir):
                if f.endswith(".html"):
                    report_file = os.path.join(output_dir, f)
                    break

        if report_file:
            report_card = ctk.CTkFrame(self._body, fg_color=BG_CARD, corner_radius=12)
            report_card.pack(fill="x", pady=(0, 12))

            ctk.CTkLabel(report_card, text="Rapport d'analyse", font=FONT_BTN,
                         text_color=TEXT).pack(anchor="w", padx=20, pady=(14, 8))

            btn_frame = ctk.CTkFrame(report_card, fg_color="transparent")
            btn_frame.pack(fill="x", padx=20, pady=(0, 14))

            ctk.CTkButton(btn_frame, text="Ouvrir le rapport HTML",
                          font=FONT_BTN_SM, fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                          text_color=BG_MAIN, height=38, width=200,
                          corner_radius=8,
                          command=lambda: self._open_file(report_file)).pack(side="left", padx=(0, 8))

            pdf_file = report_file.replace(".html", ".pdf")
            if os.path.exists(pdf_file):
                ctk.CTkButton(btn_frame, text="Ouvrir le rapport PDF",
                              font=FONT_BTN_SM, fg_color=SECONDARY, hover_color=SECONDARY_HOVER,
                              text_color=BG_MAIN, height=38, width=200,
                              corner_radius=8,
                              command=lambda: self._open_file(pdf_file)).pack(side="left")

        aes_files = [f for f in os.listdir(output_dir) if f.endswith(".aes")] if output_dir and os.path.isdir(output_dir) else []
        if aes_files:
            enc_card = ctk.CTkFrame(self._body, fg_color=BG_CARD, corner_radius=12)
            enc_card.pack(fill="x", pady=(0, 12))
            ctk.CTkLabel(enc_card, text="Archive chiffrée", font=FONT_BTN,
                         text_color=TEXT).pack(anchor="w", padx=20, pady=(14, 4))
            for f in aes_files:
                fpath = os.path.join(output_dir, f)
                size_mb = os.path.getsize(fpath) / (1024 * 1024)
                row = ctk.CTkFrame(enc_card, fg_color="transparent")
                row.pack(fill="x", padx=20, pady=2)
                ctk.CTkLabel(row, text=f"{f}", font=FONT_MONO,
                             text_color=SUCCESS).pack(side="left")
                ctk.CTkLabel(row, text=f"{size_mb:.1f} MB", font=FONT_SMALL,
                             text_color=TEXT_DIM).pack(side="right")
            ctk.CTkLabel(enc_card, text="", height=10).pack()

    def _open_file(self, path):
        try:
            webbrowser.open(f"file://{os.path.abspath(path)}")
        except Exception:
            pass

    def reset(self):
        for w in self._body.winfo_children():
            w.destroy()
