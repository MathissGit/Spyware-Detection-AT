import os
import platform
import shutil
import subprocess
import customtkinter as ctk
from gui.theme import *


class InstallPage(ctk.CTkFrame):
    def __init__(self, master, on_back=None):
        super().__init__(master, fg_color=BG_MAIN, corner_radius=0)
        self._on_back = on_back
        self._worker = None
        self._build_ui()
        self._check_prereqs()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 0))

        back_btn = ctk.CTkButton(header, text="← Retour", font=FONT_BTN_SM,
                                 fg_color="transparent", hover_color=BG_CARD,
                                 text_color=TEXT_DIM, width=80, command=self._on_back)
        back_btn.pack(side="left")

        ctk.CTkLabel(header, text="Installation", font=FONT_TITLE, text_color=TEXT).pack(side="left", padx=20)

        self._body = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                             scrollbar_button_color=BORDER)
        self._body.pack(fill="both", expand=True, padx=30, pady=16)

        self._prereq_frame = ctk.CTkFrame(self._body, fg_color=BG_CARD, corner_radius=12)
        self._prereq_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(self._prereq_frame, text="Prérequis détectés", font=FONT_BTN,
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(12, 4))

        self._checks_frame = ctk.CTkFrame(self._prereq_frame, fg_color="transparent")
        self._checks_frame.pack(fill="x", padx=16, pady=(0, 12))

        mode_frame = ctk.CTkFrame(self._body, fg_color=BG_CARD, corner_radius=12)
        mode_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(mode_frame, text="Mode d'installation", font=FONT_BTN,
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(12, 8))

        self._mode_var = ctk.StringVar(value="sandbox")

        sandbox_row = ctk.CTkFrame(mode_frame, fg_color="transparent")
        sandbox_row.pack(fill="x", padx=16, pady=4)
        ctk.CTkRadioButton(sandbox_row, text="  Sandbox (VM VirtualBox) — Sécurisé, isolé",
                           variable=self._mode_var, value="sandbox",
                           font=FONT_BODY, text_color=TEXT,
                           fg_color=PRIMARY, hover_color=SECONDARY).pack(anchor="w")
        ctk.CTkLabel(sandbox_row, text="     Installe VirtualBox + Vagrant + VM Debian 12",
                     font=FONT_SMALL, text_color=TEXT_DIM).pack(anchor="w")

        direct_row = ctk.CTkFrame(mode_frame, fg_color="transparent")
        direct_row.pack(fill="x", padx=16, pady=(4, 12))
        ctk.CTkRadioButton(direct_row, text="  Mode direct — Rapide, pas d'isolation",
                           variable=self._mode_var, value="direct",
                           font=FONT_BODY, text_color=TEXT,
                           fg_color=PRIMARY, hover_color=SECONDARY).pack(anchor="w")
        ctk.CTkLabel(direct_row, text="     Installe adb, libimobiledevice directement",
                     font=FONT_SMALL, text_color=TEXT_DIM).pack(anchor="w")

        btn_frame = ctk.CTkFrame(self._body, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 8))
        self._install_btn = ctk.CTkButton(btn_frame, text="Lancer l'installation",
                                          font=FONT_BTN, fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
                                          text_color=BG_MAIN, height=44, width=240,
                                          corner_radius=10, command=self._start_install)
        self._install_btn.pack(side="left")

        self._spinner = ctk.CTkProgressBar(btn_frame, width=120, height=4, fg_color=BORDER,
                                           progress_color=SUCCESS)
        self._spinner.pack(side="left", padx=12)
        self._spinner.set(0)

        self._status_label = ctk.CTkLabel(btn_frame, text="", font=FONT_SMALL, text_color=TEXT_DIM)
        self._status_label.pack(side="left", padx=16)

        log_frame = ctk.CTkFrame(self._body, fg_color=BG_CARD, corner_radius=12)
        log_frame.pack(fill="both", expand=True)
        ctk.CTkLabel(log_frame, text="Journal d'installation", font=FONT_BTN,
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(12, 4))
        self._log_box = ctk.CTkTextbox(log_frame, font=FONT_MONO, fg_color=BG_INPUT,
                                        text_color=SUCCESS, corner_radius=8,
                                        height=200, state="disabled")
        self._log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _check_prereqs(self):
        for w in self._checks_frame.winfo_children():
            w.destroy()
        checks = self._get_checks()
        for name, ok in checks:
            row = ctk.CTkFrame(self._checks_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            icon = "✓" if ok else "✗"
            color = SUCCESS if ok else DANGER
            ctk.CTkLabel(row, text=f"  {icon}", font=FONT_BTN_SM, text_color=color, width=24).pack(side="left")
            ctk.CTkLabel(row, text=name, font=FONT_BODY,
                         text_color=TEXT if ok else TEXT_DIM).pack(side="left")

    def _get_checks(self):
        system = platform.system()
        checks = []
        checks.append(("Python 3", shutil.which("python3") is not None or shutil.which("python") is not None))
        checks.append(("adb (Android Debug Bridge)", shutil.which("adb") is not None))
        checks.append(("libimobiledevice (iOS)", shutil.which("idevicepair") is not None))
        checks.append(("Interface graphique (tkinter)", self._has_tk()))
        checks.append(("VirtualBox", shutil.which("virtualbox") is not None or shutil.which("vboxmanage") is not None))
        checks.append(("Vagrant", shutil.which("vagrant") is not None))
        venv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv_forensics")
        checks.append(("Environnement Python (.venv_forensics)", os.path.isdir(venv_path)))
        iocs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mvt_iocs")
        has_iocs = os.path.isdir(iocs_path) and len(os.listdir(iocs_path)) > 0 if os.path.isdir(iocs_path) else False
        checks.append(("Bases IOC (mvt_iocs)", has_iocs))
        return checks

    def _has_tk(self):
        try:
            import tkinter
            return True
        except Exception:
            return False

    def _start_install(self):
        self._install_btn.configure(state="disabled", text="Installation en cours...")
        self._spinner.set(0.3)
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")
        from gui.workers import InstallWorker
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._worker = InstallWorker(self._mode_var.get(), script_dir, callback=self._append_log)
        self._worker.start()
        self._poll_worker()

    def _append_log(self, msg):
        def _do():
            self._log_box.configure(state="normal")
            self._log_box.insert("end", msg + "\n")
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        self.after(0, _do)

    def _poll_worker(self):
        if self._worker and self._worker.is_alive():
            self.after(500, self._poll_worker)
        else:
            self._spinner.set(0)
            self._install_btn.configure(state="normal", text="Lancer l'installation")
            if self._worker and self._worker.success:
                self._status_label.configure(text="Installation terminée avec succès", text_color=SUCCESS)
            elif self._worker and self._worker.error:
                self._status_label.configure(text=f"Erreur: {self._worker.error}", text_color=DANGER)
            self._check_prereqs()

    def refresh(self):
        self._check_prereqs()
