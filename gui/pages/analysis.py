import time
import customtkinter as ctk
from gui.theme import *
from gui.widgets.progress_step import ProgressStep


class AnalysisPage(ctk.CTkFrame):
    STEPS = [
        "Connexion à l'appareil",
        "Extraction des données",
        "Analyse des menaces (IOC)",
        "Génération du rapport",
        "Chiffrement & Archival",
        "Finalisation",
    ]

    def __init__(self, master, on_next=None, on_back=None):
        super().__init__(master, fg_color=BG_MAIN, corner_radius=0)
        self._on_next = on_next
        self._on_back = on_back
        self._worker = None
        self._start_time = 0
        self._step_times = [0] * len(self.STEPS)
        self._ticking = False
        self._timer_job = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 0))
        ctk.CTkButton(header, text="← Annuler", font=FONT_BTN_SM,
                      fg_color="transparent", hover_color=BG_CARD,
                      text_color=TEXT_DIM, width=80, command=self._cancel).pack(side="left")
        ctk.CTkLabel(header, text="Analyse en cours", font=FONT_TITLE,
                     text_color=TEXT).pack(side="left", padx=20)

        self._timer_label = ctk.CTkLabel(header, text="00:00", font=FONT_MONO,
                                         text_color=TEXT_DIM)
        self._timer_label.pack(side="right")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=30, pady=16)

        left = ctk.CTkFrame(body, fg_color="transparent", width=340)
        left.pack(side="left", fill="y", padx=(0, 16))
        left.pack_propagate(False)

        self._steps = []
        for i, label in enumerate(self.STEPS):
            ps = ProgressStep(left, label, index=i)
            ps.pack(fill="x", pady=3)
            self._steps.append(ps)

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="right", fill="both", expand=True)

        self._global_label = ctk.CTkLabel(right, text="Préparation...", font=FONT_BODY,
                                          text_color=TEXT_DIM)
        self._global_label.pack(anchor="w", pady=(0, 8))

        log_frame = ctk.CTkFrame(right, fg_color=BG_CARD, corner_radius=10)
        log_frame.pack(fill="both", expand=True)

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(log_header, text="Journal d'exécution", font=FONT_BTN_SM,
                     text_color=TEXT_DIM).pack(side="left")

        self._activity_label = ctk.CTkLabel(log_header, text="", font=FONT_SMALL,
                                            text_color=TEXT_DIM)
        self._activity_label.pack(side="right")

        log_spinner_frame = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_spinner_frame.pack(fill="x", padx=12, pady=(0, 4))
        self._spinner = ctk.CTkProgressBar(log_spinner_frame, height=4, fg_color=BORDER,
                                           progress_color=PRIMARY)
        self._spinner.pack(fill="x")

        self._log_box = ctk.CTkTextbox(log_frame, font=FONT_MONO, fg_color=BG_INPUT,
                                        text_color=TEXT, corner_radius=8,
                                        state="disabled")
        self._log_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._log_max_lines = 500

        self._error_frame = ctk.CTkFrame(right, fg_color=BG_CARD, corner_radius=10,
                                          border_width=2, border_color=DANGER)
        self._error_label = ctk.CTkLabel(self._error_frame, text="", font=FONT_BODY,
                                         text_color=DANGER, wraplength=400)
        self._error_label.pack(padx=16, pady=12)

        self._retry_btn = ctk.CTkButton(right, text="Réessayer", font=FONT_BTN,
                                        fg_color=DANGER, hover_color=DANGER_HOVER,
                                        text_color=BG_LIGHT, height=40, width=160,
                                        corner_radius=8, command=self._retry)

    def start_analysis(self, device_type, password, dest_choice, ext_dir=None, mode="direct"):
        for s in self._steps:
            s.reset()
        self._spinner.set(0)
        self._global_label.configure(text="Démarrage de l'analyse...", text_color=TEXT_DIM)
        self._activity_label.configure(text="")
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")
        self._error_frame.pack_forget()
        self._retry_btn.pack_forget()
        self._start_time = time.monotonic()
        self._step_times = [0] * len(self.STEPS)

        from gui.workers import AnalysisWorker
        self._worker = AnalysisWorker(device_type, password, dest_choice, ext_dir, mode=mode)
        self._worker.set_callbacks(
            progress_cb=self._on_progress,
            log_cb=self._on_log,
            activity_cb=self._on_activity,
        )
        self._worker.start()

        self._ticking = True
        self._update_timer()
        self._poll_worker()

    def _on_progress(self, step_index, state, elapsed=""):
        def _do():
            if 0 <= step_index < len(self._steps):
                self._steps[step_index].set_state(state, elapsed)
            total = len(self.STEPS)
            done = sum(1 for s in self._steps if s.state == "done")
            if state == "active":
                self._spinner.configure(progress_color=PRIMARY)
                self._spinner.set(0.3)
                self._global_label.configure(text=self.STEPS[step_index] + "...",
                                             text_color=PRIMARY)
            elif state == "done":
                self._spinner.set(0)
                self._global_label.configure(text=f"Étape {step_index + 1}/{total} terminée",
                                             text_color=SUCCESS)
            elif state == "error":
                self._spinner.set(0)
                self._global_label.configure(text="Erreur lors de l'analyse",
                                             text_color=DANGER)
        self.after(0, _do)

    def _on_log(self, msg):
        def _do():
            self._log_box.configure(state="normal")
            current_lines = int(self._log_box.index("end-1c").split(".")[0])
            if current_lines >= self._log_max_lines:
                self._log_box.delete("1.0", f"{current_lines - self._log_max_lines + 10}.0")
            self._log_box.insert("end", msg + "\n")
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        self.after(0, _do)

    def _on_activity(self, msg):
        def _do():
            text = (msg[:80] + "...") if len(msg) > 80 else msg
            self._activity_label.configure(text=text)
        self.after(0, _do)

    def _poll_worker(self):
        if self._worker and self._worker.is_alive():
            self.after(500, self._poll_worker)
        else:
            self._ticking = False
            if self._timer_job:
                self.after_cancel(self._timer_job)
                self._timer_job = None
            elapsed = time.monotonic() - self._start_time
            mins = int(elapsed) // 60
            secs = int(elapsed) % 60
            self._timer_label.configure(text=f"{mins:02d}:{secs:02d}")
            self._spinner.set(0)
            self._activity_label.configure(text="")
            if self._worker and self._worker.error:
                self._error_frame.pack(fill="x", pady=(8, 0))
                self._error_label.configure(text=self._worker.error)
                self._retry_btn.pack(pady=(8, 0))
            elif self._worker and self._worker.result:
                self._global_label.configure(text="Analyse terminée avec succès",
                                             text_color=SUCCESS)
                self.after(1500, lambda: self._on_next(self._worker.result))

    def _update_timer(self):
        if not self._ticking or not self.winfo_exists():
            return
        elapsed = time.monotonic() - self._start_time
        mins = int(elapsed) // 60
        secs = int(elapsed) % 60
        self._timer_label.configure(text=f"{mins:02d}:{secs:02d}")
        self._timer_job = self.after(1000, self._update_timer)

    def _cancel(self):
        if self._worker and self._worker.is_alive():
            self._worker.cancel()
            self._global_label.configure(text="Annulation en cours...", text_color=WARNING)
        else:
            if self._on_back:
                self._on_back()

    def _retry(self):
        if self._on_back:
            self._on_back()

    def reset(self):
        self._ticking = False
        if self._timer_job:
            self.after_cancel(self._timer_job)
            self._timer_job = None
        for s in self._steps:
            s.reset()
        self._spinner.set(0)
        self._global_label.configure(text="Préparation...")
        self._error_frame.pack_forget()
        self._retry_btn.pack_forget()
        self._timer_label.configure(text="00:00")
        self._activity_label.configure(text="")