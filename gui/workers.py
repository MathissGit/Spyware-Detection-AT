import os
import sys
import glob
import time
import shutil
import tarfile
import platform
import datetime
import subprocess
import threading
import re

import pyAesCrypt

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DEST_DIR = os.path.join(SCRIPT_DIR, "results")
IOCS_DIR = os.path.join(SCRIPT_DIR, "mvt_iocs")
# Les fichiers .stix2 de mvt_iocs/ sont chargés par MVT via la variable
# MVT_STIX2 (dossier). Si elle n'est pas déjà définie (scripts .sh), on la pose.
os.environ.setdefault("MVT_STIX2", IOCS_DIR)
IOC_FILES = sorted(glob.glob(os.path.join(IOCS_DIR, "*.stix2")))
SYSTEM = platform.system()
AES_BUFFER_SIZE = 32 * 1024 * 1024
DATE_STR = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _get_bin(name):
    local = f"/usr/local/bin/{name}"
    return local if os.path.exists(local) else name


def _find_androidqf():
    c = glob.glob(os.path.join(SCRIPT_DIR, "androidqf*"))
    return c[0] if c else os.path.join(SCRIPT_DIR, "androidqf")


def detect_android_device(mode="direct"):
    if mode == "sandbox":
        try:
            from gui.sandbox_client import SandboxClient, SandboxError
            client = SandboxClient()
            try:
                client.ensure_up()
            except SandboxError as e:
                return False, str(e), ""
            return client.detect_android()
        except Exception as e:
            return False, f"Erreur sandbox: {e}", ""
    try:
        subprocess.run(["adb", "start-server"],
                        stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=5)
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        lines = [l.strip() for l in res.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]
        if not lines:
            return False, "Aucun appareil Android détecté", ""
        serial = lines[0].split("\t")[0]
        imei = "UNKNOWN"
        try:
            r = subprocess.run(["adb", "-s", serial, "shell", "service", "call",
                                "iphonesubinfo", "1"], capture_output=True, text=True, timeout=5)
            matches = re.findall(r"'([0-9]{15,17})'", r.stdout.replace(".", ""))
            if matches:
                imei = matches[0]
            else:
                r2 = subprocess.run(["adb", "-s", serial, "shell", "getprop", "ro.serialno"],
                                     capture_output=True, text=True, timeout=3)
                if r2.returncode == 0 and r2.stdout.strip():
                    imei = r2.stdout.strip()
        except Exception:
            pass
        return True, f"Android connecté (Serial: {serial})", imei
    except Exception as e:
        return False, f"Erreur ADB: {e}", ""


def detect_ios_device(mode="direct"):
    if mode == "sandbox":
        try:
            from gui.sandbox_client import SandboxClient, SandboxError
            client = SandboxClient()
            try:
                client.ensure_up()
            except SandboxError as e:
                return False, str(e), ""
            return client.detect_ios()
        except Exception as e:
            return False, f"Erreur sandbox: {e}", ""
    try:
        bin_pair = _get_bin("idevicepair")
        res = subprocess.run([bin_pair, "validate"], capture_output=True, timeout=5)
        if res.returncode != 0:
            subprocess.run([bin_pair, "pair"], capture_output=True, timeout=10)
            res = subprocess.run([bin_pair, "validate"], capture_output=True, timeout=5)
        if res.returncode == 0:
            imei = "UNKNOWN"
            try:
                r = subprocess.run([_get_bin("ideviceinfo"), "-k",
                                    "InternationalMobileEquipmentIdentity"],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode == 0 and r.stdout.strip():
                    imei = r.stdout.strip()
            except Exception:
                pass
            return True, "iOS/Appareil connecté", imei
        return False, "Aucun appareil iOS détecté", ""
    except Exception as e:
        return False, f"Erreur iOS: {e}", ""


def _extract_imei(device_type, mode="direct"):
    if device_type == "android":
        return detect_android_device(mode=mode)[2]
    return detect_ios_device(mode=mode)[2]


class AnalysisWorker(threading.Thread):
    def __init__(self, device_type, password, dest_choice, ext_dir=None, mode="direct"):
        super().__init__(daemon=True)
        self.device_type = device_type
        self.password = password
        self.dest_choice = dest_choice
        self.ext_dir = ext_dir
        self.mode = mode
        self.cancel_event = threading.Event()
        self._progress_cb = None
        self._log_cb = None
        self._activity_cb = None
        self._result = None
        self._error = None

    def set_callbacks(self, progress_cb=None, log_cb=None, activity_cb=None):
        self._progress_cb = progress_cb
        self._log_cb = log_cb
        self._activity_cb = activity_cb

    def _emit_progress(self, step_index, state, elapsed=""):
        if self._progress_cb:
            self._progress_cb(step_index, state, elapsed)

    def _emit_log(self, msg):
        if self._log_cb:
            self._log_cb(msg)

    def _emit_activity(self, msg):
        if self._activity_cb:
            self._activity_cb(msg)

    @property
    def result(self):
        return self._result

    @property
    def error(self):
        return self._error

    def run(self):
        try:
            if self.mode == "sandbox":
                self._run_sandbox()
            elif self.device_type == "android":
                self._run_android()
            else:
                self._run_ios()
        except Exception as e:
            self._error = str(e)
            self._emit_log(f"ERREUR: {e}")

    def _run_sandbox(self):
        """Toute l'extraction/analyse s'effectue dans la VM ; le rapport et le
        packaging restent côté hôte (le dossier partagé /vagrant est miroir
        du dossier projet)."""
        from gui.sandbox_client import SandboxClient, SandboxError
        client = SandboxClient()

        self._emit_progress(0, "active")
        self._emit_log("Connexion à la VM sandbox...")
        try:
            client.ensure_up()
        except SandboxError as e:
            self._emit_progress(0, "error")
            self._error = str(e)
            return
        self._emit_progress(0, "done", "")
        if self.cancel_event.is_set():
            return

        t0 = time.monotonic()
        self._emit_progress(1, "active")
        self._emit_log(f"Extraction des données {self.device_type} dans la sandbox...")
        try:
            result = client.analyze(
                self.device_type, self.password,
                live_cb=self._emit_activity, stop_event=self.cancel_event,
                timeout=1800 if self.device_type == "ios" else 1200,
            )
        except SandboxError as e:
            self._emit_progress(1, "error")
            self._error = str(e)
            return
        if self.cancel_event.is_set():
            return

        imei = result.get("imei", "UNKNOWN")
        log_name = result.get("log_file", "mvt_log.txt")
        folders = []
        if self.device_type == "android":
            folders = [os.path.join(SCRIPT_DIR, result["dump_dir"]),
                       os.path.join(SCRIPT_DIR, result["mvt_out"])]
        else:
            folders = [os.path.join(SCRIPT_DIR, result["raw_dir"]),
                       os.path.join(SCRIPT_DIR, result["mvt_out"])]
        log_file = os.path.join(SCRIPT_DIR, log_name)
        self._emit_progress(1, "done", f"{time.monotonic() - t0:.1f}s")
        self._emit_log(f"Extraction et analyse terminées (IMEI: {imei})")
        if self.cancel_event.is_set():
            return

        t0 = time.monotonic()
        self._emit_progress(2, "done", f"{time.monotonic() - t0:.1f}s")
        if self.cancel_event.is_set():
            return

        t0 = time.monotonic()
        self._emit_progress(3, "active")
        self._emit_log("Génération des rapports HTML et PDF (hôte)...")
        report_html, report_pdf = self._generate_reports(log_file, imei)
        self._emit_progress(3, "done", f"{time.monotonic() - t0:.1f}s")
        if self.cancel_event.is_set():
            return

        t0 = time.monotonic()
        self._emit_progress(4, "active")
        self._emit_log("Chiffrement et archivage des données (hôte)...")
        primary_dir = self._secure_packaging(folders, imei, report_html, report_pdf, log_file)
        self._emit_progress(4, "done", f"{time.monotonic() - t0:.1f}s")

        self._emit_progress(5, "active")
        self._emit_log("Nettoyage des fichiers temporaires...")
        for folder in folders:
            if os.path.exists(folder):
                shutil.rmtree(folder, ignore_errors=True)
        self._emit_progress(5, "done", "OK")

        self._result = {"imei": imei, "output_dir": primary_dir,
                        "report_html": report_html, "report_pdf": report_pdf}

    def _run_android(self):
        t0 = time.monotonic()
        imei = "UNKNOWN"

        self._emit_progress(0, "active")
        self._emit_log("Démarrage du serveur ADB...")
        subprocess.run(["adb", "start-server"],
                        stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=10)
        self._emit_progress(0, "done", f"{time.monotonic() - t0:.1f}s")
        if self.cancel_event.is_set():
            return

        t0 = time.monotonic()
        self._emit_progress(1, "active")
        self._emit_log("Extraction des données Android via AndroidQF...")
        imei = _extract_imei("android")
        androidqf_bin = _find_androidqf()
        dirs_before = set(next(os.walk(SCRIPT_DIR))[1])
        try:
            subprocess.run([androidqf_bin], cwd=SCRIPT_DIR, timeout=600)
        except FileNotFoundError:
            self._emit_progress(1, "error")
            self._error = f"Binaire AndroidQF introuvable: {androidqf_bin}"
            return
        new_dirs = set(next(os.walk(SCRIPT_DIR))[1]) - dirs_before
        if not new_dirs:
            self._emit_progress(1, "error")
            self._error = "Aucun dossier de dump généré par AndroidQF"
            return
        dump_dir = os.path.join(SCRIPT_DIR, list(new_dirs)[0])
        if imei == "UNKNOWN":
            imei = _extract_imei("android")
        self._emit_progress(1, "done", f"{time.monotonic() - t0:.1f}s")
        self._emit_log(f"Données extraites (IMEI: {imei})")
        if self.cancel_event.is_set():
            return

        t0 = time.monotonic()
        self._emit_progress(2, "active")
        self._emit_log("Analyse des indicateurs de compromission (IOC)...")
        mvt_out = f"{dump_dir}_mvt_results"
        os.makedirs(mvt_out, exist_ok=True)
        log_file = os.path.join(SCRIPT_DIR, "mvt_log.txt")
        files_csv = os.path.join(dump_dir, "files.csv")
        hidden = os.path.join(dump_dir, "_hidden_files.csv")
        renamed = False
        if os.path.exists(files_csv):
            shutil.move(files_csv, hidden)
            renamed = True
        try:
            with open(log_file, "w") as f:
                cmd = ["mvt-android", "check-androidqf", dump_dir]
                for ioc in IOC_FILES:
                    cmd += ["--iocs", ioc]
                cmd += ["--output", mvt_out]
                subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=1800)
        finally:
            if renamed and os.path.exists(hidden):
                shutil.move(hidden, files_csv)
        self._emit_progress(2, "done", f"{time.monotonic() - t0:.1f}s")
        if self.cancel_event.is_set():
            return

        t0 = time.monotonic()
        self._emit_progress(3, "active")
        self._emit_log("Génération des rapports HTML et PDF...")
        report_html, report_pdf = self._generate_reports(log_file, imei)
        self._emit_progress(3, "done", f"{time.monotonic() - t0:.1f}s")
        if self.cancel_event.is_set():
            return

        t0 = time.monotonic()
        self._emit_progress(4, "active")
        self._emit_log("Chiffrement et archivage des données...")
        folders = [dump_dir, mvt_out]
        primary_dir = self._secure_packaging(folders, imei, report_html, report_pdf, log_file)
        self._emit_progress(4, "done", f"{time.monotonic() - t0:.1f}s")

        self._emit_progress(5, "active")
        self._emit_log("Nettoyage des fichiers temporaires...")
        for folder in folders:
            if os.path.exists(folder):
                shutil.rmtree(folder, ignore_errors=True)
        self._emit_progress(5, "done", "OK")

        self._result = {"imei": imei, "output_dir": primary_dir,
                        "report_html": report_html, "report_pdf": report_pdf}

    def _run_ios(self):
        t0 = time.monotonic()
        self._emit_progress(0, "active")
        self._emit_log("Appairage de l'appareil iOS...")
        bin_pair = _get_bin("idevicepair")
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if self.cancel_event.is_set():
                return
            if subprocess.run([bin_pair, "validate"], capture_output=True).returncode == 0:
                break
            subprocess.run([bin_pair, "pair"], capture_output=True)
            time.sleep(2)
        else:
            self._emit_progress(0, "error")
            self._error = "Délai d'appairage iOS dépassé (120s)"
            return
        imei = _extract_imei("ios")
        self._emit_progress(0, "done", f"{time.monotonic() - t0:.1f}s")
        self._emit_log(f"Appareil iOS appairé (IMEI: {imei})")
        if self.cancel_event.is_set():
            return

        t0 = time.monotonic()
        self._emit_progress(1, "active")
        self._emit_log("Création de la sauvegarde iOS chiffrée...")
        bin_backup = _get_bin("idevicebackup2")
        raw_dir = os.path.join(SCRIPT_DIR, f"dump_{imei}_{DATE_STR}")
        os.makedirs(raw_dir, exist_ok=True)
        env = os.environ.copy()
        env["BACKUP_PASSWORD"] = self.password
        res = subprocess.run([bin_backup, "encryption", "on", "-i"],
                             env=env, capture_output=True, text=True)
        if res.returncode != 0 and "already enabled" not in (res.stderr or res.stdout).lower():
            shutil.rmtree(raw_dir, ignore_errors=True)
            self._emit_progress(1, "error")
            self._error = "Erreur activation chiffrement iOS"
            return
        try:
            subprocess.run([bin_backup, "-i", "backup", raw_dir], env=env,
                           check=True, timeout=1800)
        except subprocess.CalledProcessError as e:
            shutil.rmtree(raw_dir, ignore_errors=True)
            self._emit_progress(1, "error")
            self._error = f"Échec sauvegarde iOS (code {e.returncode})"
            return
        try:
            udid = next(os.walk(raw_dir))[1][0]
            full_path = os.path.join(raw_dir, udid)
        except Exception:
            shutil.rmtree(raw_dir, ignore_errors=True)
            self._emit_progress(1, "error")
            self._error = "Dossier UDID introuvable dans la sauvegarde"
            return
        self._emit_progress(1, "done", f"{time.monotonic() - t0:.1f}s")
        if self.cancel_event.is_set():
            return

        t0 = time.monotonic()
        self._emit_progress(2, "active")
        self._emit_log("Analyse des indicateurs de compromission (IOC)...")
        mvt_out = os.path.join(SCRIPT_DIR, f"ios_mvt_results_{DATE_STR}")
        os.makedirs(mvt_out, exist_ok=True)
        log_file = os.path.join(SCRIPT_DIR, "mvt_log.txt")
        with open(log_file, "w") as f:
            cmd = ["mvt-ios", "check-backup", "-p", self.password, "--fast"]
            for ioc in IOC_FILES:
                cmd += ["--iocs", ioc]
            cmd += ["--output", mvt_out, full_path]
            subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=1800)
        self._emit_progress(2, "done", f"{time.monotonic() - t0:.1f}s")
        if self.cancel_event.is_set():
            return

        t0 = time.monotonic()
        self._emit_progress(3, "active")
        self._emit_log("Génération des rapports HTML et PDF...")
        report_html, report_pdf = self._generate_reports(log_file, imei)
        self._emit_progress(3, "done", f"{time.monotonic() - t0:.1f}s")
        if self.cancel_event.is_set():
            return

        t0 = time.monotonic()
        self._emit_progress(4, "active")
        self._emit_log("Chiffrement et archivage des données...")
        folders = [raw_dir, mvt_out]
        primary_dir = self._secure_packaging(folders, imei, report_html, report_pdf, log_file)
        self._emit_progress(4, "done", f"{time.monotonic() - t0:.1f}s")

        self._emit_progress(5, "active")
        self._emit_log("Nettoyage des fichiers temporaires...")
        for folder in folders:
            if os.path.exists(folder):
                shutil.rmtree(folder, ignore_errors=True)
        self._emit_progress(5, "done", "OK")

        self._result = {"imei": imei, "output_dir": primary_dir,
                        "report_html": report_html, "report_pdf": report_pdf}

    def _generate_reports(self, log_file, imei):
        categories = {
            "Logiciels Espions Ciblés": {
                "keywords": ["pegasus", "predator", "finspy", "candiru", "cytrox", "reign"],
                "desc": "Signature détectée d'un logiciel espion de niveau gouvernemental.",
                "reco": "DANGER IMMÉDIAT : Mode Avion. Consultez un expert en sécurité.",
                "alerts": []
            },
            "Stalkerwares & Apps Espionnes": {
                "keywords": ["stalkerware", "mspy", "cerberus", "flexispy", "package", "app", "apk", "bundle"],
                "desc": "Application d'espionnage commercial détectée.",
                "reco": "Désinstallez l'application. Modifiez tous vos mots de passe.",
                "alerts": []
            },
            "Domaines & Serveurs C2": {
                "keywords": ["domain", "url", "http", "ip address"],
                "desc": "Communications vers des serveurs de contrôle détectées.",
                "reco": "Isolez l'appareil du réseau.",
                "alerts": []
            },
            "Fichiers & Processus Compromis": {
                "keywords": ["file", "hash", "macho", "binary", "process"],
                "desc": "Fichier ou processus malveillant identifié.",
                "reco": "Ne lancez plus d'applications.",
                "alerts": []
            },
            "Communications Malveillantes": {
                "keywords": ["sms", "message", "mail", "whatsapp", "telegram", "email", "phone number"],
                "desc": "Message de phishing ou exploit détecté.",
                "reco": "Ne cliquez sur aucun lien suspect.",
                "alerts": []
            },
            "Autres Indicateurs STIX2": {
                "keywords": [],
                "desc": "Indicateur de threat intelligence nécessitant analyse experte.",
                "reco": "Analysez les journaux MVT pour plus de détails.",
                "alerts": []
            }
        }
        criticals = 0
        warnings = 0

        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    clean = line.strip()
                    if len(clean) < 10:
                        continue
                    low = clean.lower()
                    if not any(kw in low for kw in ["match found", "matched stix2", "matched indicator",
                                                     "malicious indicator", "indicator match"]):
                        continue
                    is_crit = "CRITICAL" in clean
                    sev = "CRITIQUE" if is_crit else "ALERTE IOC"
                    if is_crit:
                        criticals += 1
                    else:
                        warnings += 1
                    matched = False
                    for name, data in categories.items():
                        if name == "Autres Indicateurs STIX2":
                            continue
                        if any(k.lower() in low for k in data["keywords"]):
                            data["alerts"].append((sev, clean))
                            matched = True
                            break
                    if not matched:
                        categories["Autres Indicateurs STIX2"]["alerts"].append((sev, clean))
        except Exception:
            pass

        total = criticals + warnings
        if total == 0:
            status_color, status_text = "#27ae60", "Aucun IoC détecté"
        elif criticals > 0:
            status_color, status_text = "#e74c3c", "Appareil Compromis"
        else:
            status_color, status_text = "#f39c12", "Menaces Potentielles"

        from xhtml2pdf import pisa
        date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<title>Rapport IoC - {imei}</title>
<style>
@page {{ size: A4; margin: 1.5cm; }} body {{ font-family: sans-serif; font-size: 12px; color: #333; }}
h1 {{ color: #2C3E50; border-bottom: 2px solid #3498DB; padding-bottom: 5px; }}
.dash {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
.dash td {{ padding: 15px; border: 1px solid #ECF0F1; text-align: center; background: #FAFAFA; width: 33%; }}
.val {{ font-size: 24px; font-weight: bold; }} .lab {{ font-size: 10px; color: #7F8C8D; margin-top: 5px; }}
.box {{ background: {status_color}; color: white; padding: 12px; text-align: center; font-weight: bold;
        font-size: 14px; border-radius: 3px; margin-bottom: 20px; }}
.cat-card {{ border: 1px solid #BDC3C7; border-radius: 4px; margin-bottom: 25px; overflow: hidden; }}
.cat-header {{ background: #2C3E50; color: white; padding: 10px 15px; font-weight: bold; font-size: 13px; }}
.cat-desc {{ padding: 12px 15px; font-size: 11px; background: #ECF0F1; color: #34495E; }}
.cat-reco {{ padding: 12px 15px; font-size: 11px; background: #D5F5E3; color: #1E8449; border-top: 1px solid #BDC3C7; }}
.cat-alerts {{ padding: 0; margin: 0; list-style-type: none; }}
.cat-alerts li {{ padding: 10px 15px; border-top: 1px solid #ECF0F1; font-family: monospace; font-size: 10px;
                  word-wrap: break-word; background: #FFFFFF; }}
.crit {{ color: #e74c3c; font-weight: bold; }} .warn {{ color: #f39c12; font-weight: bold; }}
</style></head><body>
<h1>Rapport d'Analyse IoC - IMEI: {imei}</h1>
<div class="box">STATUT : {status_text.upper()}</div>
<table class="dash"><tr>
<td><div class="val">{total}</div><div class="lab">Total IoC</div></td>
<td><div class="val" style="color:#e74c3c;">{criticals}</div><div class="lab">Critiques</div></td>
<td><div class="val" style="color:#f39c12;">{warnings}</div><div class="lab">Avertissements</div></td>
</tr></table>
<p style="font-size:11px;color:#7F8C8D;margin-bottom:30px;"><strong>Date :</strong> {date_str}</p>
<h2>Détail des Signatures</h2>"""

        if total == 0:
            html += '<div style="text-align:center;padding:20px;color:#27ae60;background:#F9FFF9;border:1px solid #27ae60;">Aucune trace de logiciel espion détectée.</div>'
        else:
            for name, data in categories.items():
                if data["alerts"]:
                    html += f'<div class="cat-card"><div class="cat-header">{name} ({len(data["alerts"])} alertes)</div>'
                    html += f'<div class="cat-desc"><b>Menace :</b> {data["desc"]}</div>'
                    html += f'<div class="cat-reco"><b>Recommandation :</b> {data["reco"]}</div><ul class="cat-alerts">'
                    for sev, txt in data["alerts"]:
                        cls = "crit" if sev == "CRITIQUE" else "warn"
                        html += f'<li><span class="{cls}">[{sev}]</span> {txt}</li>'
                    html += "</ul></div>"
        html += "</body></html>"

        base = f"Report_{imei}_{DATE_STR}"
        html_path = os.path.join(SCRIPT_DIR, f"{base}.html")
        pdf_path = os.path.join(SCRIPT_DIR, f"{base}.pdf")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        try:
            with open(html_path, "r", encoding="utf-8") as s, open(pdf_path, "w+b") as d:
                pisa.CreatePDF(s, dest=d)
        except Exception:
            pass
        return html_path, pdf_path

    def _secure_packaging(self, folders, imei, html_rep, pdf_rep, log_file):
        session = f"Dump_{imei}_{DATE_STR}"
        if self.dest_choice == "2" and self.ext_dir:
            primary = os.path.join(self.ext_dir, "results", session)
        else:
            primary = os.path.join(LOCAL_DEST_DIR, session)
        os.makedirs(primary, exist_ok=True)

        tar_path = os.path.join(primary, f"{session}.tar.gz")
        enc_path = os.path.join(primary, f"{session}.tar.gz.aes")

        with tarfile.open(tar_path, "w:gz") as tar:
            for folder in folders:
                if os.path.exists(folder):
                    tar.add(folder, arcname=os.path.basename(folder))

        pyAesCrypt.encryptFile(tar_path, enc_path, self.password, AES_BUFFER_SIZE)
        os.remove(tar_path)

        for f in [html_rep, pdf_rep]:
            if os.path.exists(f):
                shutil.move(f, os.path.join(primary, os.path.basename(f)))
        if os.path.exists(log_file):
            os.remove(log_file)

        if self.dest_choice == "3" and self.ext_dir:
            ext_session = os.path.join(self.ext_dir, "results", session)
            shutil.copytree(primary, ext_session, dirs_exist_ok=True)

        return primary

    def cancel(self):
        self.cancel_event.set()


class InstallWorker(threading.Thread):
    def __init__(self, mode, script_dir, callback=None):
        super().__init__(daemon=True)
        self.mode = mode
        self.script_dir = script_dir
        self._callback = callback
        self.success = False
        self.error = None

    def _emit(self, msg):
        if self._callback:
            self._callback(msg)

    def run(self):
        try:
            if SYSTEM == "Linux" or SYSTEM == "Darwin":
                self._run_linux()
            else:
                self.error = (
                    f"MVT ne fonctionne pas nativement sur {SYSTEM} (Windows non supporté). "
                    "Installez et exécutez l'outil via WSL (Windows Subsystem for Linux), puis "
                    "utilisez le script setup.sh (à la racine du projet). Référez-vous à install.md."
                )
        except Exception as e:
            self.error = str(e)
            self._emit(f"ERREUR: {e}")

    def _run_linux(self):
        script = os.path.join(self.script_dir, "Setup", "setup.sh")
        if not os.path.exists(script):
            self.error = f"Script d'installation introuvable: {script}"
            return
        self._emit(f"Exécution: {script}")
        self._emit(f"Mode: {'Sandbox (VM)' if self.mode == 'sandbox' else 'Direct'}")
        env = os.environ.copy()
        env["DEBIAN_FRONTEND"] = "noninteractive"
        proc = subprocess.Popen(
            ["bash", script],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=self.script_dir, env=env, text=True
        )
        proc.stdin.write(("2\n" if self.mode == "direct" else "1\n") + "O\n")
        proc.stdin.flush()
        for line in iter(proc.stdout.readline, ""):
            if line:
                self._emit(line.rstrip())
        proc.wait()
        self.success = proc.returncode == 0
        if not self.success:
            self.error = f"Script terminé avec le code {proc.returncode}"
