#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "[*] Vérification de l'environnement local (mode direct)..."

if ! command -v adb >/dev/null 2>&1; then
    echo "[*] Installation de adb..."
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -qq
    sudo apt-get install -y -qq adb
fi

if ! command -v idevicebackup2 >/dev/null 2>&1; then
    echo "[*] Installation de libimobiledevice..."
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -qq
    sudo apt-get install -y -qq libimobiledevice-utils usbmuxd
fi

mkdir -p "$SCRIPT_DIR/mvt_iocs"

IOC_STALE=true
if [ -d "$SCRIPT_DIR/mvt_iocs" ] && [ "$(ls -A "$SCRIPT_DIR/mvt_iocs" 2>/dev/null)" ]; then
    NEWEST_IOC=$(find "$SCRIPT_DIR/mvt_iocs" -type f -printf '%T@\n' 2>/dev/null | sort -rn | head -1)
    if [ -n "$NEWEST_IOC" ]; then
        AGE_HOURS=$(( ($(date +%s) - ${NEWEST_IOC%.*}) / 3600 ))
        if [ "$AGE_HOURS" -lt 168 ]; then
            IOC_STALE=false
            echo "[*] Bases IOC déjà à jour (${AGE_HOURS}h). Téléchargement ignoré."
        fi
    fi
fi

if [ ! -d ".venv_forensics" ]; then
    echo "[*] Création de l'environnement virtuel Python..."
    python3 -m venv .venv_forensics

    echo "[*] Installation des librairies d'analyse..."
    .venv_forensics/bin/pip install --upgrade pip -q
    .venv_forensics/bin/pip install -q mvt pyAesCrypt xhtml2pdf rich questionary

    echo "[*] Initialisation des bases de menaces (IOCs)..."
    sudo "$SCRIPT_DIR/.venv_forensics/bin/mvt-ios" download-iocs -f "$SCRIPT_DIR/mvt_iocs" >/dev/null 2>&1 &
    sudo "$SCRIPT_DIR/.venv_forensics/bin/mvt-android" download-iocs -f "$SCRIPT_DIR/mvt_iocs" >/dev/null 2>&1 &
    wait
elif [ "$IOC_STALE" = true ]; then
    echo "[*] Mise à jour des bases IOC (plusieurs)..."
    sudo "$SCRIPT_DIR/.venv_forensics/bin/mvt-ios" download-iocs -f "$SCRIPT_DIR/mvt_iocs" >/dev/null 2>&1 &
    sudo "$SCRIPT_DIR/.venv_forensics/bin/mvt-android" download-iocs -f "$SCRIPT_DIR/mvt_iocs" >/dev/null 2>&1 &
    wait
fi

sudo systemctl restart usbmuxd 2>/dev/null || true

echo "[*] Démarrage de l'outil d'analyse..."
sudo PATH="$SCRIPT_DIR/.venv_forensics/bin:$PATH" "$SCRIPT_DIR/.venv_forensics/bin/python" "$SCRIPT_DIR/main.py"
