#!/usr/bin/env python3
"""Tâches exécutées DANS la VM sandbox (via `vagrant ssh`).

Chaque sous-commande effectue une opération sur l'appareil capturé en USB
par VirtualBox (le téléphone n'est jamais visible par l'hôte) et se termine
par une ligne sur stdout :
    RESULT_JSON {...}

La sortie standard porte aussi des lignes de journal relayées à l'interface
(hôte). Le mot de passe de sauvegarde iOS est lu sur la première ligne de
stdin (ne transparaît jamais dans un listing de processus).

Usage (dans la VM, dossier /vagrant) :
    /opt/venv_forensics/bin/python scripts/sandbox_tasks.py detect-android
    /opt/venv_forensics/bin/python scripts/sandbox_tasks.py detect-ios
    /opt/venv_forensics/bin/python scripts/sandbox_tasks.py analyze-android
    /opt/venv_forensics/bin/python scripts/sandbox_tasks.py analyze-ios
"""
import json
import os
import sys
import re
import glob
import time
import shutil
import datetime
import subprocess

VM_ROOT = "/vagrant"
IDENTITY_DIR = os.path.join(VM_ROOT, "mvt_iocs")
DATE_STR = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
VENV_BIN = os.path.dirname(sys.executable)


def _bin(name):
    local = f"/usr/local/bin/{name}"
    return local if os.path.exists(local) else name


def _mvt_bin(name):
    local = os.path.join(VENV_BIN, name)
    return local if os.path.exists(local) else name


def _run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, **kwargs)


def _sudo(cmd):
    return ["sudo"] + cmd


def _result(data):
    sys.stdout.write("RESULT_JSON " + json.dumps(data) + "\n")
    sys.stdout.flush()


def _emit(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def _adb_devices():
    _run(_sudo(["adb", "start-server"]), timeout=15)
    res = _run(_sudo(["adb", "devices"]), text=True, timeout=10)
    lines = [l.strip() for l in res.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]
    if not lines:
        return None
    return lines[0].split("\t")[0]


def _imei_android(serial):
    try:
        r = _run(_sudo(["adb", "-s", serial, "shell", "service", "call",
                        "iphonesubinfo", "1"]), text=True, timeout=10)
        matches = re.findall(r"'([0-9]{15,17})'", r.stdout.replace(".", ""))
        if matches:
            return matches[0]
        r2 = _run(_sudo(["adb", "-s", serial, "shell", "getprop", "ro.serialno"]),
                  text=True, timeout=8)
        if r2.returncode == 0 and r2.stdout.strip():
            return r2.stdout.strip()
    except Exception:
        pass
    return "UNKNOWN"


def _imei_ios():
    r = _run(_sudo([_bin("ideviceinfo"), "-k", "InternationalMobileEquipmentIdentity"]),
             text=True, timeout=8)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "UNKNOWN"


# ----------------------------------------------------------------- detect
def cmd_detect_android():
    serial = _adb_devices()
    if not serial:
        _result({"found": False, "msg": "Aucun appareil Android détecté", "imei": ""})
        return
    imei = _imei_android(serial)
    _result({"found": True, "msg": f"Android connecté (Serial: {serial})", "imei": imei})


def cmd_detect_ios():
    pair = _bin("idevicepair")
    try:
        res = _run(_sudo([pair, "validate"]), timeout=10)
        if res.returncode != 0:
            _run(_sudo([pair, "pair"]), timeout=15)
            res = _run(_sudo([pair, "validate"]), timeout=10)
        if res.returncode == 0:
            imei = _imei_ios()
            _result({"found": True, "msg": "iOS/Appareil connecté", "imei": imei})
            return
    except Exception as e:
        _result({"found": False, "msg": f"Erreur iOS: {e}", "imei": ""})
        return
    _result({"found": False, "msg": "Aucun appareil iOS détecté", "imei": ""})


def _ioc_args(cmd):
    iocs = sorted(glob.glob(os.path.join(IDENTITY_DIR, "*.stix2")))
    for ioc in iocs:
        cmd += ["--iocs", ioc]
    return cmd, iocs


def _stale_tmp_dirs():
    """Supprime les résidus d'exécutions avortées (> 1 h) dans /vagrant."""
    if not os.path.isdir(VM_ROOT):
        return
    cutoff = time.time() - 3600
    for name in os.listdir(VM_ROOT):
        if not name.startswith(("dump_", "ios_mvt_results_")):
            continue
        path = os.path.join(VM_ROOT, name)
        try:
            if os.path.isdir(path) and os.path.getmtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue


# ---------------------------------------------------------------- analyze
def cmd_analyze_android():
    env = os.environ.copy()
    env.setdefault("MVT_STIX2", IDENTITY_DIR)

    _emit("[sandbox] Connexion ADB (dans la VM)...")
    serial = _adb_devices()
    imei = _imei_android(serial) if serial else "UNKNOWN"

    _emit("[sandbox] Extraction AndroidQF (dans la VM)...")
    androidqf = glob.glob(os.path.join(VM_ROOT, "androidqf*"))
    if not androidqf:
        _result({"ok": False, "error": "Binaire AndroidQF introuvable dans /vagrant"})
        return
    os.chdir(VM_ROOT)
    dirs_before = set(next(os.walk("."))[1])
    try:
        subprocess.run(_sudo([androidqf[0]]), cwd=VM_ROOT, check=True, timeout=600)
    except subprocess.CalledProcessError as e:
        _result({"ok": False, "error": f"Échec AndroidQF (code {e.returncode})"})
        return
    new_dirs = set(next(os.walk("."))[1]) - dirs_before
    if not new_dirs:
        _result({"ok": False, "error": "Aucun dossier de dump généré par AndroidQF"})
        return
    dump_dir = list(new_dirs)[0]
    _emit(f"[sandbox] Dump créé : {dump_dir} (IMEI/Serial: {imei})")

    mvt_out = f"{dump_dir}_mvt_results"
    os.makedirs(mvt_out, exist_ok=True)
    log_file = "mvt_log.txt"
    files_csv = os.path.join(dump_dir, "files.csv")
    hidden = os.path.join(dump_dir, "_hidden_files.csv")
    renamed = False
    if os.path.exists(files_csv):
        os.rename(files_csv, hidden)
        renamed = True
    try:
        cmd, _ = _ioc_args([_mvt_bin("mvt-android"), "check-androidqf", dump_dir])
        cmd += ["--output", mvt_out]
        with open(log_file, "w") as f:
            subprocess.run(_sudo(cmd), env=env, stdout=f, stderr=subprocess.STDOUT)
    finally:
        if renamed and os.path.exists(hidden):
            os.rename(hidden, files_csv)

    _result({"ok": True, "imei": imei, "dump_dir": dump_dir,
             "mvt_out": mvt_out, "log_file": log_file})


def cmd_analyze_ios():
    password = sys.stdin.readline().strip()
    _stale_tmp_dirs()
    pair = _bin("idevicepair")
    _emit("[sandbox] Appairage iOS (dans la VM)...")
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if _run(_sudo([pair, "validate"]), timeout=10).returncode == 0:
            break
        _run(_sudo([pair, "pair"]), timeout=15)
        time.sleep(2)
    else:
        _result({"ok": False, "error": "Délai d'appairage iOS dépassé (120s)"})
        return
    imei = _imei_ios()
    _emit(f"[sandbox] Appareil appairé (IMEI: {imei})")

    env = os.environ.copy()
    env["BACKUP_PASSWORD"] = password
    backup_bin = _bin("idevicebackup2")
    os.chdir(VM_ROOT)
    raw_dir = f"dump_{imei}_{DATE_STR}"
    os.makedirs(raw_dir, exist_ok=True)

    _emit("[sandbox] Activation du chiffrement iOS...")
    res = _run(_sudo([backup_bin, "encryption", "on", "-i"]), env=env, text=True, timeout=60)
    if res.returncode != 0 and "already enabled" not in (res.stderr or res.stdout).lower():
        shutil.rmtree(raw_dir, ignore_errors=True)
        _result({"ok": False, "error": "Erreur activation chiffrement iOS"})
        return

    _emit("[sandbox] Sauvegarde iOS chiffrée (gardez l'écran allumé)...")
    try:
        subprocess.run(_sudo([backup_bin, "-i", "backup", raw_dir]), env=env,
                       check=True, timeout=3600)
    except subprocess.CalledProcessError as e:
        shutil.rmtree(raw_dir, ignore_errors=True)
        _result({"ok": False, "error": f"Échec sauvegarde iOS (code {e.returncode})"})
        return
    try:
        udid = next(os.walk(raw_dir))[1][0]
        full_path = os.path.join(raw_dir, udid)
    except Exception:
        shutil.rmtree(raw_dir, ignore_errors=True)
        _result({"ok": False, "error": "Dossier UDID introuvable dans la sauvegarde"})
        return

    _emit("[sandbox] Analyse des IOC (MVT)...")
    mvt_out = f"ios_mvt_results_{DATE_STR}"
    os.makedirs(mvt_out, exist_ok=True)
    log_file = "mvt_log.txt"
    cmd, _ = _ioc_args([_mvt_bin("mvt-ios"), "check-backup", "-p", password, "--fast"])
    cmd += ["--output", mvt_out, full_path]
    with open(log_file, "w") as f:
        subprocess.run(_sudo(cmd), env=env, stdout=f, stderr=subprocess.STDOUT)

    _result({"ok": True, "imei": imei, "raw_dir": raw_dir,
             "mvt_out": mvt_out, "log_file": log_file})


COMMANDS = {
    "detect-android": cmd_detect_android,
    "detect-ios": cmd_detect_ios,
    "analyze-android": cmd_analyze_android,
    "analyze-ios": cmd_analyze_ios,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.stderr.write("usage: sandbox_tasks.py {%s}\n" % "|".join(COMMANDS))
        sys.exit(2)
    try:
        COMMANDS[sys.argv[1]]()
    except Exception as e:
        _result({"ok": False, "error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()