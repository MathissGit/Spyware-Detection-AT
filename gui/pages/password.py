import customtkinter as ctk
from gui.theme import *


class PasswordPage(ctk.CTkFrame):
    def __init__(self, master, on_next=None, on_back=None):
        super().__init__(master, fg_color=BG_MAIN, corner_radius=0)
        self._on_next = on_next
        self._on_back = on_back

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 0))
        ctk.CTkButton(header, text="← Retour", font=FONT_BTN_SM,
                      fg_color="transparent", hover_color=BG_CARD,
                      text_color=TEXT_DIM, width=80, command=self._on_back).pack(side="left")
        ctk.CTkLabel(header, text="Mot de passe de chiffrement", font=FONT_TITLE,
                     text_color=TEXT).pack(side="left", padx=20)

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.42, anchor="center")

        ctk.CTkLabel(center, text="Créez un mot de passe pour chiffrer l'archive AES-256",
                     font=FONT_SUBTITLE, text_color=TEXT_DIM).pack(pady=(0, 20))

        form = ctk.CTkFrame(center, fg_color=BG_CARD, corner_radius=12)
        form.pack(padx=20)

        ctk.CTkLabel(form, text="Mot de passe", font=FONT_BODY, text_color=TEXT_DIM).pack(
            anchor="w", padx=20, pady=(16, 4))
        self._pwd1 = ctk.CTkEntry(form, font=FONT_BODY, show="•", width=360,
                                  fg_color=BG_INPUT, border_color=BORDER,
                                  text_color=TEXT)
        self._pwd1.pack(padx=20, pady=(0, 8))
        self._pwd1.bind("<KeyRelease>", self._check_match)

        ctk.CTkLabel(form, text="Confirmez le mot de passe", font=FONT_BODY,
                     text_color=TEXT_DIM).pack(anchor="w", padx=20, pady=(4, 4))
        self._pwd2 = ctk.CTkEntry(form, font=FONT_BODY, show="•", width=360,
                                  fg_color=BG_INPUT, border_color=BORDER,
                                  text_color=TEXT)
        self._pwd2.pack(padx=20, pady=(0, 8))
        self._pwd2.bind("<KeyRelease>", self._check_match)

        self._strength_bar = ctk.CTkProgressBar(form, width=360, height=6,
                                                fg_color=BORDER, progress_color=BORDER)
        self._strength_bar.pack(padx=20, pady=(0, 4))
        self._strength_bar.set(0)

        self._strength_label = ctk.CTkLabel(form, text="", font=FONT_SMALL, text_color=TEXT_DIM)
        self._strength_label.pack(padx=20, pady=(0, 4))

        self._match_label = ctk.CTkLabel(form, text="", font=FONT_SMALL, text_color=DANGER)
        self._match_label.pack(padx=20, pady=(0, 16))

        self._next_btn = ctk.CTkButton(center, text="Continuer →", font=FONT_BTN,
                                       fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                                       text_color=BG_MAIN, height=44, width=200,
                                       corner_radius=10, state="disabled",
                                       command=self._go_next)
        self._next_btn.pack(pady=(20, 0))

    def _check_match(self, e=None):
        p1 = self._pwd1.get()
        p2 = self._pwd2.get()

        strength = 0
        if len(p1) >= 8: strength += 1
        if len(p1) >= 12: strength += 1
        if any(c.isupper() for c in p1): strength += 1
        if any(c.isdigit() for c in p1): strength += 1
        if any(c in "!@#$%^&*()_+-=[]{}|;:',.<>?/" for c in p1): strength += 1

        if len(p1) == 0:
            self._strength_bar.set(0)
            self._strength_bar.configure(progress_color=BORDER)
            self._strength_label.configure(text="")
        else:
            frac = min(strength / 5, 1.0)
            self._strength_bar.set(frac)
            labels = ["Très faible", "Faible", "Moyen", "Fort", "Très fort"]
            colors = [DANGER, DANGER, WARNING, SUCCESS, SUCCESS]
            idx = min(strength - 1, len(labels) - 1) if strength > 0 else 0
            self._strength_bar.configure(progress_color=colors[idx])
            self._strength_label.configure(text=labels[idx], text_color=colors[idx])

        if p1 and p2:
            if p1 == p2:
                self._match_label.configure(text="✓ Les mots de passe correspondent", text_color=SUCCESS)
                self._next_btn.configure(state="normal")
            else:
                self._match_label.configure(text="✗ Les mots de passe ne correspondent pas", text_color=DANGER)
                self._next_btn.configure(state="disabled")
        else:
            self._match_label.configure(text="")
            self._next_btn.configure(state="disabled")

    def _go_next(self):
        if self._on_next:
            self._on_next(self._pwd1.get())

    def reset(self):
        self._pwd1.delete(0, "end")
        self._pwd2.delete(0, "end")
        self._strength_bar.set(0)
        self._strength_label.configure(text="")
        self._match_label.configure(text="")
        self._next_btn.configure(state="disabled")
