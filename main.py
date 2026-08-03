import os
import sys
import glob
import tarfile
import shutil
import platform
import datetime
import subprocess
import pyAesCrypt
from xhtml2pdf import pisa
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
import questionary
import time
import re

# ==========================================
# Configuration initiale & UI
# ==========================================
SYSTEM = platform.system()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DEST_DIR = os.path.join(SCRIPT_DIR, "results")
IOCS_DIR = os.path.join(SCRIPT_DIR, "mvt_iocs")
DATE_STR = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
AES_BUFFER_SIZE = 32 * 1024 * 1024

console = Console()

def show_banner():
    ascii_art = """
███████╗██████╗ ██╗   ██╗██╗    ██╗ █████╗ ██████╗ ███████╗     █████╗ ███╗   ██╗ █████╗ ██╗  ██╗   ██╗███████╗██╗███████╗
██╔════╝██╔══██╗╚██╗ ██╔╝██║    ██║██╔══██╗██╔══██╗██╔════╝    ██╔══██╗████╗  ██║██╔══██╗██║  ╚██╗ ██╔╝██╔════╝██║██╔════╝
███████╗██████╔╝ ╚████╔╝ ██║ █╗ ██║███████║██████╔╝█████╗      ███████║██╔██╗ ██║███████║██║   ╚████╔╝ ███████╗██║███████╗
╚════██║██╔═══╝   ╚██╔╝  ██║███╗██║██╔══██║██╔══██╗██╔══╝      ██╔══██║██║╚██╗██║██╔══██║██║    ╚██╔╝  ╚════██║██║╚════██║
███████║██║        ██║   ╚███╔███╔╝██║  ██║██║  ██║███████╗    ██║  ██║██║ ╚████║██║  ██║███████╗██║   ███████║██║███████║
╚══════╝╚═╝        ╚═╝    ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝   ╚══════╝╚═╝╚══════╝
    """
    panel = Panel(
        Text(ascii_art, style="bold cyan", justify="center"),
        title="[bold green]S P Y W A R E  D E T E C T I O N  A U T O M A T E D  T O O L[/bold green]",
        subtitle="[dim]Automated Forensics with MVT[/dim]",
        border_style="blue"
    )
    console.print(panel)
    console.print()

def get_external_drives():
    drives = []
    if SYSTEM == "Linux":
        for base in ["/media/" + os.getenv('USER', ''), "/mnt"]:
            if os.path.exists(base):
                drives += [os.path.join(base, d) for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
    elif SYSTEM == "Darwin":
        volumes_path = "/Volumes"
        if os.path.exists(volumes_path):
            drives = [os.path.join(volumes_path, d) for d in os.listdir(volumes_path) if os.path.isdir(os.path.join(volumes_path, d)) and d != "Macintosh HD"]
    elif SYSTEM == "Windows":
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in range(26):
            if bitmask & (1 << letter):
                drive = f"{chr(65 + letter)}:\\"
                if drive != "C:\\" and os.path.exists(drive): drives.append(drive)
    return drives

def get_user_inputs():
    custom_style = questionary.Style([
        ("highlighted", "fg:#00ff00 bold"),
        ("qmark", "fg:#3498DB bold"),
        ("question", "bold"),
        ("pointer", "fg:#00ff00 bold")
    ])

    while True:
        device_type = questionary.select(
            "Quel type d'appareil souhaitez-vous analyser ?",
            choices=[
                questionary.Choice("Android", "1"),
                questionary.Choice("iOS / iPhone", "2"),
                questionary.Choice("-- Quitter l'application --", "EXIT")
            ], style=custom_style).ask()

        if not device_type or device_type == "EXIT": sys.exit(0)

        dest_choice = questionary.select(
            "Où souhaitez-vous sauvegarder l'archive chiffrée ?",
            choices=[
                questionary.Choice(f"Uniquement en local ({LOCAL_DEST_DIR})", "1"),
                questionary.Choice("Uniquement sur un périphérique externe", "2"),
                questionary.Choice("Les deux (Copie Local + Externe)", "3"),
                questionary.Choice("-- Retour --", "BACK")
            ], style=custom_style).ask()

        if not dest_choice: sys.exit(0)
        if dest_choice == "BACK": continue

        ext_dir = None
        if dest_choice in ["2", "3"]:
            while True:
                choices = [questionary.Choice(d, d) for d in get_external_drives()]
                choices.extend([questionary.Choice("Entrer un autre chemin manuellement...", "MANUAL"), questionary.Choice("-- Retour --", "BACK_DEST")])
                selected_drive = questionary.select("Sélectionnez le périphérique externe :", choices=choices, style=custom_style).ask()

                if not selected_drive or selected_drive == "BACK_DEST":
                    ext_dir = "RESTART"; break
                if selected_drive != "MANUAL":
                    ext_dir = selected_drive; break
                
                manual_path = questionary.text("Entrez le chemin absolu du dossier externe :", style=custom_style).ask()
                if manual_path and os.path.exists(manual_path) and os.path.isdir(manual_path):
                    ext_dir = manual_path; break
                console.print("[bold red][!] Chemin introuvable. Réessayez.[/bold red]")

            if ext_dir == "RESTART": continue

        while True:
            pwd1 = questionary.password("Créez le mot de passe de chiffrement AES-256 :", style=custom_style).ask()
            if not pwd1: continue
            pwd2 = questionary.password("Confirmez le mot de passe :", style=custom_style).ask()
            if pwd1 == pwd2: return device_type, dest_choice, ext_dir, pwd1
            console.print("[bold red][!] Les mots de passe ne correspondent pas.[/bold red]\n")

def get_bin(binary_name):
    local_path = f"/usr/local/bin/{binary_name}"
    return local_path if os.path.exists(local_path) else binary_name

def extract_imei(device_type):
    imei = "UNKNOWN-IMEI"
    try:
        if device_type == "1":
            res = subprocess.run(["sudo", "adb", "shell", "service", "call", "iphonesubinfo", "1"], capture_output=True, text=True, timeout=3)
            matches = re.findall(r"'([0-9]{15,17})'", res.stdout.replace(".", ""))
            if matches:
                imei = matches[0]
            else:
                res_fallback = subprocess.run(["sudo", "adb", "shell", "getprop", "ro.serialno"], capture_output=True, text=True, timeout=2)
                if res_fallback.returncode == 0 and res_fallback.stdout.strip():
                    imei = res_fallback.stdout.strip()
        else:
            local_path = "/usr/local/bin/ideviceinfo"
            bin_path = local_path if os.path.exists(local_path) else "ideviceinfo"
            res = subprocess.run([bin_path, "-k", "InternationalMobileEquipmentIdentity"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                imei = res.stdout.strip()
    except Exception:
        pass
    return "".join(c for c in imei if c.isalnum())

# ==========================================
# Moteurs d'Extraction & Analyse
# ==========================================
def run_android():
    console.print("\n[bold cyan][*] Initialisation du pont USB...[/bold cyan]")
    subprocess.run(["sudo", "adb", "kill-server"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run(["sudo", "adb", "start-server"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    time.sleep(2)

    console.print("[bold cyan][*] Lancement d'AndroidQF...[/bold cyan]")
    device_imei = extract_imei("1")

    androidqf_bin = next(iter(glob.glob("androidqf*.exe") + ["androidqf.exe"]), "androidqf.exe") if SYSTEM == "Windows" else ("./" + glob.glob("androidqf*")[0] if glob.glob("androidqf*") else "./androidqf")
    dirs_before = set(next(os.walk('.'))[1])

    try:
        subprocess.run([androidqf_bin], check=True)
    except FileNotFoundError:
        console.print(f"[bold red][!] Binaire {androidqf_bin} introuvable.[/bold red]"); sys.exit(1)

    new_dirs = set(next(os.walk('.'))[1]) - dirs_before
    if not new_dirs:
        console.print("[bold red][!] Aucun dossier généré.[/bold red]"); sys.exit(1)

    dump_dir = list(new_dirs)[0]
    if device_imei.startswith("UNKNOWN"): device_imei = extract_imei("1")

    console.print(f"[bold green][+] Extraction terminée (IMEI/Serial: {device_imei}).[/bold green]")

    mvt_out_dir = f"{dump_dir}_mvt_results"
    os.makedirs(mvt_out_dir, exist_ok=True)
    log_file = "mvt_log.txt"

    with console.status("[bold purple]Analyse des IOC en cours...[/bold purple]", spinner="dots"):
        files_csv = os.path.join(dump_dir, "files.csv")
        hidden_files = os.path.join(dump_dir, "_hidden_files.csv")
        if os.path.exists(files_csv):
            shutil.move(files_csv, hidden_files)

        with open(log_file, "w") as f:
            subprocess.run(["mvt-android", "check-androidqf", dump_dir, "--iocs", IOCS_DIR, "--output", mvt_out_dir], stdout=f, stderr=subprocess.STDOUT)

        if os.path.exists(hidden_files):
            shutil.move(hidden_files, files_csv)

    return [dump_dir, mvt_out_dir], log_file, device_imei

def run_ios(password):
    bin_pair = "/usr/local/bin/idevicepair" if os.path.exists("/usr/local/bin/idevicepair") else "idevicepair"
    bin_backup = "/usr/local/bin/idevicebackup2" if os.path.exists("/usr/local/bin/idevicebackup2") else "idevicebackup2"

    with console.status("[bold yellow][!] Branchez l'appareil, déverrouillez-le et appuyez sur 'Faire confiance' (Saisissez le PIN)...[/bold yellow]", spinner="dots"):
        while True:
            if subprocess.run([bin_pair, "validate"], capture_output=True).returncode == 0: break
            if subprocess.run([bin_pair, "pair"], capture_output=True).returncode == 0:
                if subprocess.run([bin_pair, "validate"], capture_output=True).returncode == 0: break
            time.sleep(2)
            
    console.print("[bold green][+] Appareil appairé avec succès.[/bold green]")
    device_imei = extract_imei("2")

    env = os.environ.copy()
    env["BACKUP_PASSWORD"] = password
    
    res = subprocess.run([bin_backup, "encryption", "on", "-i"], env=env, capture_output=True, text=True)
    if res.returncode != 0 and "already enabled" not in (res.stderr or res.stdout).lower():
        console.print(f"[bold red][!] Erreur de chiffrement natif iOS.[/bold red]"); sys.exit(1)

    raw_backup_dir = f"dump_{device_imei}_{DATE_STR}"
    os.makedirs(raw_backup_dir, exist_ok=True)
    
    console.print("\n[bold cyan][*] Création de la sauvegarde iOS chiffrée (Gardez l'écran allumé)...[/bold cyan]")
    try:
        subprocess.run([bin_backup, "-i", "backup", raw_backup_dir], check=True, env=env)
    except subprocess.CalledProcessError as e:
        console.print(f"\n[bold red][!] Échec de la sauvegarde (Code {e.returncode}). Vérifiez le câble et le PIN.[/bold red]"); sys.exit(1)
            
    try:
        udid_folder = next(os.walk(raw_backup_dir))[1][0]
        full_backup_path = os.path.join(raw_backup_dir, udid_folder)
    except Exception:
        console.print("[bold red][!] Échec : Dossier UDID introuvable.[/bold red]"); sys.exit(1)
        
    mvt_out_dir = f"ios_mvt_results_{DATE_STR}"
    os.makedirs(mvt_out_dir, exist_ok=True)
    log_file = "mvt_log.txt"
    
    with console.status("[bold purple]Analyse des IOC en cours...[/bold purple]", spinner="dots"):
        with open(log_file, "w") as f:
            subprocess.run(["mvt-ios", "check-backup", "-p", password, "--fast", "--iocs", IOCS_DIR, "--output", mvt_out_dir, full_backup_path], stdout=f, stderr=subprocess.STDOUT)
            
    return [raw_backup_dir, mvt_out_dir], log_file, device_imei

# ==========================================
# Post-Processing & Reporting (Strict IOC)
# ==========================================
def generate_reports(log_file, imei):
    console.print("[dim][*] Structuration du rapport d'analyse...[/dim]")
    
    categories = {
        "Logiciels Espions Ciblés (Pegasus, Predator...)": {
            "keywords": ["pegasus", "predator", "finspy", "candiru", "cytrox", "reign"],
            "desc": "Signature détectée d'un logiciel espion de niveau gouvernemental. L'appareil est la cible d'une surveillance avancée et furtive.",
            "reco": "DANGER IMMÉDIAT : Mettez l'appareil en Mode Avion. Une simple réinitialisation peut ne pas suffire. Consultez un expert en sécurité.",
            "alerts": []
        },
        "Stalkerwares & Applications Espionnes": {
            "keywords": ["stalkerware", "mspy", "cerberus", "flexispy", "package", "app", "apk", "bundle"],
            "desc": "Une application d'espionnage commercial (souvent utilisée pour le harcèlement) correspond à un identifiant (Package Name) de la base d'Amnesty.",
            "reco": "Désinstallez immédiatement l'application correspondante au nom de paquet affiché. Modifiez tous vos mots de passe depuis un autre appareil.",
            "alerts": []
        },
        "Domaines & Serveurs de Contrôle (C2)": {
            "keywords": ["domain", "url", "http", "ip address"],
            "desc": "L'historique Web, DNS ou réseau a révélé des communications vers des serveurs contrôlés par des hackers pour héberger ou commander des malwares.",
            "reco": "Isolez l'appareil du réseau. Un logiciel espion tente potentiellement d'exfiltrer vos données vers l'infrastructure d'un attaquant.",
            "alerts": []
        },
        "Fichiers & Processus Compromis (Malware)": {
            "keywords": ["file", "hash", "macho", "binary", "process"],
            "desc": "L'empreinte cryptographique (Hash) d'un fichier physique ou d'un processus en cours correspond exactement à la signature d'un virus connu.",
            "reco": "Ne lancez plus de nouvelles applications. Une compromission du système de fichiers est confirmée.",
            "alerts": []
        },
        "Communications Malveillantes (Phishing)": {
            "keywords": ["sms", "message", "mail", "whatsapp", "telegram", "email", "phone number"],
            "desc": "Un message ciblé (lien de phishing ou exploit 'Zero-Click') lié à une campagne d'espionnage active a été détecté dans les bases de communication.",
            "reco": "Ne cliquez sur aucun lien dans vos messages. Ne répondez pas et supprimez le fil de discussion suspect.",
            "alerts": []
        },
        "Autres Indicateurs": {
            "keywords": [],
            "desc": "Correspondance stricte avec une base de données de Threat Intelligence (Indicateurs STIX2) nécessitant une analyse experte.",
            "reco": "L'outil a identifié une signature complexe. Analysez les journaux MVT de l'archive chiffrée pour plus de détails.",
            "alerts": []
        }
    }

    criticals_count = 0
    warnings_count = 0

    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            clean = line.strip()
            if len(clean) < 10: continue
            
            lower_clean = clean.lower()
            
            is_ioc_match = any(kw in lower_clean for kw in ["match found", "matched stix2", "matched indicator", "malicious indicator", "indicator match"])
            
            if not is_ioc_match:
                continue

            is_crit = "CRITICAL" in clean
            severity = "CRITIQUE" if is_crit else "ALERTE IOC"
            
            if is_crit: criticals_count += 1
            else: warnings_count += 1
            
            matched = False
            for cat_name, cat_data in categories.items():
                if cat_name == "Autres Indicateurs STIX2":
                    continue
                if any(kw.lower() in clean.lower() for kw in cat_data["keywords"]):
                    cat_data["alerts"].append((severity, clean))
                    matched = True
                    break
                    
            if not matched:
                categories["Autres Indicateurs STIX2"]["alerts"].append((severity, clean))

    total_alerts = criticals_count + warnings_count
    
    if total_alerts == 0: status_color, status_text = "#27ae60", "Aucun indicateur de compromission détecté"
    elif criticals_count > 0: status_color, status_text = "#e74c3c", "Appareil Compromis"
    else: status_color, status_text = "#f39c12", "Menaces Potentielles"

    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><title>Rapport d'Analyse IoC - IMEI: {imei}</title>
    <style>
        @page {{ size: A4; margin: 1.5cm; }} body {{ font-family: sans-serif; font-size: 12px; color: #333; }}
        h1 {{ color: #2C3E50; border-bottom: 2px solid #3498DB; padding-bottom: 5px; }}
        .dash {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
        .dash td {{ padding: 15px; border: 1px solid #ECF0F1; text-align: center; background-color: #FAFAFA; width: 33%; }}
        .val {{ font-size: 24px; font-weight: bold; }} .lab {{ font-size: 10px; color: #7F8C8D; margin-top: 5px; }}
        .box {{ background: {status_color}; color: white; padding: 12px; text-align: center; font-weight: bold; font-size: 14px; border-radius: 3px; margin-bottom: 20px; }}
        .cat-card {{ border: 1px solid #BDC3C7; border-radius: 4px; margin-bottom: 25px; overflow: hidden; }}
        .cat-header {{ background: #2C3E50; color: white; padding: 10px 15px; font-weight: bold; font-size: 13px; }}
        .cat-desc {{ padding: 12px 15px; font-size: 11px; background: #ECF0F1; color: #34495E; }}
        .cat-reco {{ padding: 12px 15px; font-size: 11px; background: #D5F5E3; color: #1E8449; border-top: 1px solid #BDC3C7; }}
        .cat-alerts {{ padding: 0; margin: 0; list-style-type: none; }}
        .cat-alerts li {{ padding: 10px 15px; border-top: 1px solid #ECF0F1; font-family: monospace; font-size: 10px; word-wrap: break-word; background: #FFFFFF; }}
        .crit-text {{ color: #e74c3c; font-weight: bold; }}
        .warn-text {{ color: #f39c12; font-weight: bold; }}
    </style></head><body>
    
    <h1>Rapport d'Analyse IoC - Appareil (IMEI: {imei})</h1>
    <div class="box">STATUT : {status_text.upper()}</div>

    <table class="dash"><tr>
        <td><div class="val">{total_alerts}</div><div class="lab">Total d'IoC Détectés</div></td>
        <td><div class="val" style="color:#e74c3c;">{criticals_count}</div><div class="lab">Critiques</div></td>
        <td><div class="val" style="color:#f39c12;">{warnings_count}</div><div class="lab">Avertissements</div></td>
    </tr></table>
    
    <p style="font-size: 11px; color: #7F8C8D; margin-bottom: 30px;"><strong>Date de l'analyse :</strong> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
    
    <h2>Détail des Signatures Malveillantes</h2>
    """

    if total_alerts == 0: 
        html += '<div style="text-align:center; padding:20px; color:#27ae60; background:#F9FFF9; border: 1px solid #27ae60;">Aucune trace de logiciel espion, Stalkerware ou signature malveillante connue n\'a été trouvée sur l\'appareil. L\'analyse des IOC est vierge.</div>'
    else:
        for cat_name, cat_data in categories.items():
            if len(cat_data["alerts"]) > 0:
                html += f"""
                <div class="cat-card">
                    <div class="cat-header">{cat_name} - ({len(cat_data["alerts"])} alertes)</div>
                    <div class="cat-desc"><strong>Explication de la menace :</strong><br/>{cat_data["desc"]}</div>
                    <div class="cat-reco"><strong>Recommandation :</strong><br/>{cat_data["reco"]}</div>
                    <ul class="cat-alerts">
                """
                for sev, alert_text in cat_data["alerts"]:
                    color_class = "crit-text" if sev == "CRITIQUE" else "warn-text"
                    html += f'<li><span class="{color_class}">[{sev}]</span> {alert_text}</li>'
                
                html += "</ul></div>"

    html += "</body></html>"

    report_base = f"Report_{imei}_{DATE_STR}"
    report_html = f"{report_base}.html"
    report_pdf = f"{report_base}.pdf"

    with open(report_html, "w", encoding="utf-8") as f: f.write(html)
    with console.status("[bold cyan]Génération du rapport d'analyse...[/bold cyan]", spinner="dots"):
        try:
            with open(report_html, "r", encoding="utf-8") as s_html, open(report_pdf, "w+b") as r_pdf:
                pisa.CreatePDF(s_html, dest=r_pdf)
        except Exception as e: console.print(f"[bold red]Erreur PDF : {e}[/bold red]")
        
    return report_html, report_pdf

# ==========================================
# Protection & Destruction Sécurisée
# ==========================================
def secure_direct_packaging(folders_to_archive, password, dest_choice, ext_dir, imei, folders_to_delete, log_file, html_rep, pdf_rep):
    session_name = f"Dump_{imei}_{DATE_STR}"
    
    if dest_choice == "2" and ext_dir:
        primary_dir = os.path.join(ext_dir, "results", session_name)
    else:
        primary_dir = os.path.join(LOCAL_DEST_DIR, session_name)
        
    os.makedirs(primary_dir, exist_ok=True)
    
    tar_path = os.path.join(primary_dir, f"{session_name}.tar.gz")
    enc_path = os.path.join(primary_dir, f"{session_name}.tar.gz.aes")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn(), TimeElapsedColumn(), console=console) as progress:
        
        task_tar = progress.add_task(f"[cyan]Création de l'archive (-> {primary_dir})...", total=None)
        with tarfile.open(tar_path, "w:gz") as tar:
            for folder in folders_to_archive:
                if os.path.exists(folder): tar.add(folder, arcname=os.path.basename(folder))
        progress.update(task_tar, completed=100, total=100)

        file_size = os.path.getsize(tar_path)
        task_aes = progress.add_task("[magenta]Chiffrement AES-256...", total=file_size)
        pyAesCrypt.encryptFile(tar_path, enc_path, password, AES_BUFFER_SIZE)
        progress.update(task_aes, completed=file_size)

    os.remove(tar_path)

    for f in [html_rep, pdf_rep]:
        if os.path.exists(f): shutil.move(f, os.path.join(primary_dir, f))
    if os.path.exists(log_file): os.remove(log_file)
    
    readme_src = os.path.join(SCRIPT_DIR, "README.md")
    if os.path.exists(readme_src): shutil.copy(readme_src, primary_dir)

    if dest_choice == "3" and ext_dir:
        with console.status("[bold yellow]Copie redondante vers le stockage externe...[/bold yellow]"):
            ext_session = os.path.join(ext_dir, "results", session_name)
            shutil.copytree(primary_dir, ext_session, dirs_exist_ok=True)

    with console.status("[bold yellow]Purge des dossiers bruts...[/bold yellow]"):
        for folder in folders_to_delete:
            if os.path.exists(folder): 
                subprocess.run(["sudo", "rm", "-rf", folder], stderr=subprocess.DEVNULL)

    console.print(Panel(
        f"[bold green]Opération terminée ![/bold green]\n"
        f"L'appareil (IMEI: [cyan]{imei}[/cyan]) a été analysé avec succès.\n"
        f"L'archive chiffrée et les rapports d'analyse sont conservés dans :\n[dim]{primary_dir}[/dim]\n",
        border_style="green"
    ))

# ==========================================
# Main
# ==========================================
if __name__ == "__main__":
    os.system('cls' if SYSTEM == 'Windows' else 'clear')
    show_banner()

    dev_type, dest, ext, pwd = get_user_inputs()

    if dev_type == "1":
        folders, log, imei_val = run_android()
    else:
        folders, log, imei_val = run_ios(pwd)

    html_file, pdf_file = generate_reports(log, imei_val)
    
    secure_direct_packaging(
        folders_to_archive=folders[:2],
        password=pwd,
        dest_choice=dest,
        ext_dir=ext,
        imei=imei_val,
        folders_to_delete=folders,
        log_file=log,
        html_rep=html_file,
        pdf_rep=pdf_file
    )