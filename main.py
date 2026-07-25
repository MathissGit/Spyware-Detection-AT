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

# ==========================================
# Configuration initiale & UI
# ==========================================
SYSTEM = platform.system()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DEST_DIR = os.path.join(SCRIPT_DIR, "results")
DATE_STR = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
REPORT_HTML = f"rapport_MVT_{DATE_STR}.html"
REPORT_PDF = f"rapport_MVT_{DATE_STR}.pdf"
AES_BUFFER_SIZE = 8 * 1024 * 1024

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
        subtitle="[dim]Automated Forensics with MVT & AndroidQF Wrapper[/dim]",
        border_style="blue"
    )
    console.print(panel)
    console.print()

def get_external_drives():
    drives = []
    if SYSTEM == "Linux":
        media_path = f"/media/{os.getenv('USER', '')}"
        if os.path.exists(media_path):
            drives = [os.path.join(media_path, d) for d in os.listdir(media_path) if os.path.isdir(os.path.join(media_path, d))]
        mnt_path = "/mnt"
        if os.path.exists(mnt_path):
            drives += [os.path.join(mnt_path, d) for d in os.listdir(mnt_path) if os.path.isdir(os.path.join(mnt_path, d))]
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
                if drive != "C:\\":
                    if os.path.exists(drive):
                        drives.append(drive)
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
            "Quel type d'appareil cible souhaitez-vous extraire ?",
            choices=[
                questionary.Choice("Android (via AndroidQF)", "1"),
                questionary.Choice("iOS / iPhone (via idevicebackup2)", "2"),
                questionary.Choice("-- Quitter l'application --", "EXIT")
            ],
            style=custom_style
        ).ask()

        if not device_type or device_type == "EXIT":
            sys.exit(0)

        dest_choice = questionary.select(
            "Où souhaitez-vous sauvegarder l'archive chiffrée finale ?",
            choices=[
                questionary.Choice(f"Uniquement en local ({LOCAL_DEST_DIR})", "1"),
                questionary.Choice("Uniquement sur un périphérique externe", "2"),
                questionary.Choice("Les deux (Copie redondante Local + Externe)", "3"),
                questionary.Choice("-- Retour à l'étape précédente --", "BACK")
            ],
            style=custom_style
        ).ask()

        if not dest_choice:
            sys.exit(0)
        if dest_choice == "BACK":
            continue

        ext_dir = None
        if dest_choice in ["2", "3"]:
            while True:
                detected_drives = get_external_drives()
                choices = [questionary.Choice(drive, drive) for drive in detected_drives]
                choices.append(questionary.Choice("Entrer un autre chemin manuellement...", "MANUAL"))
                choices.append(questionary.Choice("-- Retour au choix de la destination --", "BACK_DEST"))

                selected_drive = questionary.select(
                    "Sélectionnez le périphérique externe ou l'action :",
                    choices=choices,
                    style=custom_style
                ).ask()

                if not selected_drive or selected_drive == "BACK_DEST":
                    ext_dir = "RESTART_DEST"
                    break

                if selected_drive != "MANUAL":
                    ext_dir = selected_drive
                    break
                else:
                    manual_path = questionary.text("Entrez le chemin absolu du dossier externe (ou tapez 'annuler') :", style=custom_style).ask()
                    if not manual_path or manual_path.lower() == "annuler":
                        continue
                    if os.path.exists(manual_path) and os.path.isdir(manual_path):
                        ext_dir = manual_path
                        break
                    console.print("[bold red][!] Chemin introuvable ou invalide. Réessayez.[/bold red]")

            if ext_dir == "RESTART_DEST":
                continue

        while True:
            pwd1 = questionary.password("Créez le mot de passe de chiffrement (AES-256) (ou tapez 'retour') :", style=custom_style).ask()
            if not pwd1 or pwd1.lower() == "retour":
                pwd1 = "BACK"
                break
                
            pwd2 = questionary.password("Confirmez le mot de passe (ou tapez 'retour') :", style=custom_style).ask()
            if not pwd2 or pwd2.lower() == "retour":
                pwd1 = "BACK"
                break

            if pwd1 == pwd2 and pwd1:
                return device_type, dest_choice, ext_dir, pwd1
            console.print("[bold red][!] Les mots de passe ne correspondent pas. Recommencez.[/bold red]\n")

        if pwd1 == "BACK":
            continue

def start_iocs_background(device_type):
    cmd = "mvt-android" if device_type == "1" else "mvt-ios"
    console.print(f"[dim][*] Lancement du thread background pour {cmd} download-iocs...[/dim]")
    return subprocess.Popen([cmd, "download-iocs"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ==========================================
# Moteurs d'Extraction
# ==========================================
def run_android(mvt_bg_process):
    if SYSTEM == "Windows":
        androidqf_bin = next(iter(glob.glob("androidqf*.exe") + ["androidqf.exe"]), "androidqf.exe")
    else:
        binaries = [f for f in glob.glob("androidqf*") if os.path.isfile(f) and os.access(f, os.X_OK)]
        androidqf_bin = f"./{binaries[0]}" if binaries else "./androidqf"

    dirs_before = set(next(os.walk('.'))[1])

    console.print("\n[bold cyan][*] Lancement d'AndroidQF...[/bold cyan]")
    console.print("[bold yellow][!] Utilisez les flèches de votre clavier pour répondre aux questions ci-dessous :[/bold yellow]\n")

    try:
        subprocess.run([androidqf_bin], check=True)
    except FileNotFoundError:
        console.print(f"[bold red][!] Erreur : Le binaire {androidqf_bin} est introuvable.[/bold red]")
        sys.exit(1)

    new_dirs = set(next(os.walk('.'))[1]) - dirs_before
    if not new_dirs:
        console.print("[bold red][!] Erreur : Aucun dossier d'extraction n'a été généré.[/bold red]")
        sys.exit(1)

    dump_dir = list(new_dirs)[0]
    console.print(f"\n[bold green][+] Extraction terminée :[/bold green] [dim]{dump_dir}[/dim]")

    with console.status("[bold yellow]Synchronisation des IOCs MVT...[/bold yellow]", spinner="dots"):
        mvt_bg_process.wait()

    mvt_out_dir = f"{dump_dir}_mvt_results"
    os.makedirs(mvt_out_dir, exist_ok=True)
    log_file = "mvt_log.txt"

    with console.status("[bold purple]Analyse heuristique MVT-Android en cours...[/bold purple]", spinner="earth"):
        with open(log_file, "w") as f:
            subprocess.run(["mvt-android", "check-androidqf", dump_dir, "--output", mvt_out_dir], stdout=f, stderr=subprocess.STDOUT)

    return [dump_dir, mvt_out_dir], log_file

def run_ios(password, mvt_bg_process):
    console.print("[bold yellow][!] Déverrouillez l'appareil, branchez-le et acceptez l'ordinateur de confiance.[/bold yellow]")
    subprocess.run(["idevicepair", "pair"], check=False, stdout=subprocess.DEVNULL)

    console.print("[bold red][!] IMPORTANT : Lors de l'invite sur l'appareil, entrez votre code PIN pour valider le chiffrement de la sauvegarde.[/bold red]")
    subprocess.run(["idevicebackup2", "-i", "encryption", "on"], stdout=subprocess.DEVNULL)

    raw_backup_dir = f"ios_raw_backup_{DATE_STR}"
    os.makedirs(raw_backup_dir, exist_ok=True)

    with console.status("[bold cyan]Sauvegarde complète de l'appareil en cours (cela peut prendre plusieurs minutes)...[/bold cyan]", spinner="bouncingBar"):
        subprocess.run(["idevicebackup2", "backup", "--full", raw_backup_dir], stdout=subprocess.DEVNULL)

    try:
        udid_folder = next(os.walk(raw_backup_dir))[1][0]
        full_backup_path = os.path.join(raw_backup_dir, udid_folder)
    except StopIteration:
        console.print("[bold red][!] Échec : Aucune sauvegarde trouvée.[/bold red]")
        sys.exit(1)

    decrypted_dir = f"ios_decrypted_backup_{DATE_STR}"
    os.makedirs(decrypted_dir, exist_ok=True)

    with console.status("[bold blue]Déchiffrement forensique de l'archive...[/bold blue]"):
        subprocess.run(["mvt-ios", "decrypt-backup", "-p", password, "-d", decrypted_dir, full_backup_path], stdout=subprocess.DEVNULL)

    with console.status("[bold yellow]Synchronisation des IOCs MVT...[/bold yellow]", spinner="dots"):
        mvt_bg_process.wait()

    mvt_out_dir = f"ios_mvt_results_{DATE_STR}"
    os.makedirs(mvt_out_dir, exist_ok=True)
    log_file = "mvt_log.txt"

    with console.status("[bold purple]Analyse heuristique MVT-iOS en cours...[/bold purple]", spinner="earth"):
        with open(log_file, "w") as f:
            subprocess.run(["mvt-ios", "check-backup", "--output", mvt_out_dir, decrypted_dir], stdout=f, stderr=subprocess.STDOUT)

    return [decrypted_dir, mvt_out_dir, raw_backup_dir], log_file

# ==========================================
# Post-Processing
# ==========================================
def generate_reports(log_file):
    console.print("[dim][*] Parsing des logs et structuration du rapport...[/dim]")
    criticals = []
    warnings = []

    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for line in lines:
        clean_line = line.strip()
        if len(clean_line) < 10:
            continue
        if any(kw in clean_line for kw in ["CRITICAL", "DETECTED", "Malicious"]):
            criticals.append(clean_line)
        elif any(kw in clean_line for kw in ["WARNING", "Match found"]):
            warnings.append(clean_line)

    total_alerts = len(criticals) + len(warnings)

    if total_alerts == 0:
        status_color = "#27ae60"
        status_text = "Sain (Aucune détection majeure)"
    elif len(criticals) > 0:
        status_color = "#e74c3c"
        status_text = "Compromission Possible (Alertes Critiques)"
    else:
        status_color = "#f39c12"
        status_text = "Avertissements (À vérifier manuellement)"

    console.print(f"\n[bold {'red' if total_alerts else 'green'}]{total_alerts} alertes suspectes détectées.[/bold {'red' if total_alerts else 'green'}]")

    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Rapport Forensique - MVT</title>
    <style>
        @page {{ size: A4; margin: 1.5cm; }}
        body {{ font-family: Helvetica, Arial, sans-serif; font-size: 12px; color: #333; line-height: 1.5; }}
        h1 {{ color: #2C3E50; border-bottom: 2px solid #3498DB; padding-bottom: 5px; margin-bottom: 15px; }}
        h2 {{ color: #34495E; margin-top: 30px; border-bottom: 1px solid #BDC3C7; padding-bottom: 3px; font-size: 14px; }}
        .dashboard {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
        .dashboard td {{ padding: 15px; border: 1px solid #ECF0F1; text-align: center; width: 33%; background-color: #FAFAFA; }}
        .metric-value {{ font-size: 24px; font-weight: bold; }}
        .metric-label {{ font-size: 10px; text-transform: uppercase; color: #7F8C8D; margin-top: 5px; }}
        .status-box {{ background-color: {status_color}; color: white; padding: 12px; text-align: center; font-weight: bold; font-size: 14px; margin-bottom: 20px; border-radius: 3px; }}
        .details-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        .details-table th {{ background-color: #ECF0F1; padding: 10px; text-align: left; font-size: 11px; border: 1px solid #BDC3C7; color: #2C3E50; }}
        .details-table td {{ padding: 10px; border: 1px solid #ECF0F1; font-family: monospace; font-size: 10px; word-wrap: break-word; }}
        .badge-crit {{ color: #e74c3c; font-weight: bold; text-align: center; }}
        .badge-warn {{ color: #f39c12; font-weight: bold; text-align: center; }}
        .no-alerts {{ text-align: center; padding: 20px; color: #27ae60; font-style: italic; border: 1px dashed #27ae60; background-color: #F9FFF9; }}
    </style>
</head>
<body>
    <h1>Analyse Forensique - MVT</h1>
    <div class="status-box">STATUT GLOBAL : {status_text.upper()}</div>
    <table class="dashboard">
        <tr>
            <td><div class="metric-value">{total_alerts}</div><div class="metric-label">Total Alertes</div></td>
            <td><div class="metric-value" style="color: #e74c3c;">{len(criticals)}</div><div class="metric-label">Alertes Critiques</div></td>
            <td><div class="metric-value" style="color: #f39c12;">{len(warnings)}</div><div class="metric-label">Avertissements</div></td>
        </tr>
    </table>
    <p style="font-size: 11px; color: #7F8C8D;"><strong>Date de l'extraction :</strong> {datetime.datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}</p>
    <h2>Détail des Detections</h2>
    """

    if total_alerts == 0:
        html_content += '<div class="no-alerts">Aucun indicateur de compromission (IOC) ou alerte majeure n\'a été détecté dans les logs de cette analyse.</div>'
    else:
        html_content += """
        <table class="details-table">
            <thead>
                <tr><th style="width: 15%; text-align: center;">Sévérité</th><th style="width: 85%;">Description technique de l'alerte</th></tr>
            </thead>
            <tbody>
        """
        for crit in criticals: html_content += f"<tr><td class='badge-crit'>CRITIQUE</td><td>{crit}</td></tr>"
        for warn in warnings: html_content += f"<tr><td class='badge-warn'>WARNING</td><td>{warn}</td></tr>"
        html_content += "</tbody></table>"

    html_content += "</body></html>"

    with open(REPORT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)

    with console.status("[bold cyan]Génération du rapport PDF de synthèse...[/bold cyan]", spinner="dots"):
        try:
            with open(REPORT_HTML, "r", encoding="utf-8") as source_html:
                with open(REPORT_PDF, "w+b") as result_pdf:
                    pisa_status = pisa.CreatePDF(source_html, dest=result_pdf)
            if pisa_status.err:
                console.print("[bold red][!] Erreur interne lors de la génération du PDF.[/bold red]")
        except Exception as e:
            console.print(f"[bold red][!] Erreur lors de la création du PDF : {e}[/bold red]")

def package_and_encrypt(folders_to_archive, password):
    tar_file = f"DUMP_SECURE_{DATE_STR}.tar.gz"
    enc_file = f"{tar_file}.aes"

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn(), TimeElapsedColumn(), console=console) as progress:
        task_tar = progress.add_task("[cyan]Création de l'archive brute...", total=None)
        with tarfile.open(tar_file, "w:gz") as tar:
            for folder in folders_to_archive:
                if os.path.exists(folder):
                    tar.add(folder, arcname=os.path.basename(folder))
        progress.update(task_tar, completed=100, total=100)

        file_size = os.path.getsize(tar_file)
        task_aes = progress.add_task("[magenta]Chiffrement AES-256...", total=file_size)
        pyAesCrypt.encryptFile(tar_file, enc_file, password, AES_BUFFER_SIZE)
        progress.update(task_aes, completed=file_size)

    os.remove(tar_file)
    return enc_file

def distribute_and_cleanup(enc_file, dest_choice, ext_dir, folders_to_delete, log_file):
    session_folder_name = f"Dump_{DATE_STR}"
    local_session_dir = os.path.join(LOCAL_DEST_DIR, session_folder_name)
    ext_session_dir = None

    if dest_choice in ["2", "3"] and ext_dir:
        ext_session_dir = os.path.join(ext_dir, "Secure_Mobile_Dumps", session_folder_name)

    files_to_move = [enc_file, REPORT_HTML]
    if os.path.exists(REPORT_PDF): files_to_move.append(REPORT_PDF)

    readme_src = os.path.join(SCRIPT_DIR, "README.md")

    with console.status("[bold yellow]Déploiement et nettoyage sécurisé...[/bold yellow]"):

        # Local
        if dest_choice in ["1", "3"]:
            os.makedirs(local_session_dir, exist_ok=True)
            for f in files_to_move: shutil.copy(f, local_session_dir)
            if os.path.exists(readme_src): shutil.copy(readme_src, local_session_dir)

        # Externe
        if dest_choice in ["2", "3"] and ext_session_dir:
            os.makedirs(ext_session_dir, exist_ok=True)
            for f in files_to_move: shutil.copy(f, ext_session_dir)
            if os.path.exists(readme_src): shutil.copy(readme_src, ext_session_dir)

        # Purge des données
        for f in files_to_move + [log_file]:
            if os.path.exists(f): os.remove(f)
        for folder in folders_to_delete:
            if os.path.exists(folder): shutil.rmtree(folder)

    console.print(Panel(
        f"[bold green]Opération terminée avec succès ![/bold green]\n"
        f"Les données sont sécurisées et rangées dans le dossier dédié : [cyan]{session_folder_name}[/cyan]\n"
        f"Les instructions de déchiffrement sont décrites dans le README.\n"
        f"L'espace de travail temporaire a été purgé.",
        border_style="green"
    ))

# ==========================================
# Main
# ==========================================
if __name__ == "__main__":
    os.system('cls' if SYSTEM == 'Windows' else 'clear')
    show_banner()

    dev_type, dest, ext, pwd = get_user_inputs()

    mvt_bg_process = start_iocs_background(dev_type)

    if dev_type == "1":
        folders, log = run_android(mvt_bg_process)
    else:
        folders, log = run_ios(pwd, mvt_bg_process)

    generate_reports(log)
    folders_to_archive = folders[:2]

    file_enc = package_and_encrypt(folders_to_archive, pwd)
    distribute_and_cleanup(file_enc, dest, ext, folders, log)
