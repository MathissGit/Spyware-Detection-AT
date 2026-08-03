#!/bin/bash
set -e

cd /vagrant

echo "[*] Vérification de l'environnement interne de la Sandbox..."

if ! command -v adb >/dev/null 2>&1 || ! command -v idevicebackup2 >/dev/null 2>&1; then
    echo "[*] Installation des paquets système de base..."
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update
    sudo apt-get install -y python3-venv python3-pip adb libimobiledevice-utils usbmuxd build-essential python3-dev
fi

mkdir -p /vagrant/mvt_iocs

if [ ! -d ".venv_forensics" ]; then
    echo "[*] Création de l'environnement virtuel Python..."
    python3 -m venv .venv_forensics
    
    echo "[*] Installation des librairies d'analyse..."
    .venv_forensics/bin/pip install --upgrade pip
    .venv_forensics/bin/pip install mvt pyAesCrypt xhtml2pdf rich questionary
    
    echo "[*] Initialisation des bases de menaces (IOCs)..."
    sudo /vagrant/.venv_forensics/bin/mvt-ios download-iocs -f /vagrant/mvt_iocs >/dev/null 2>&1 || true
    sudo /vagrant/.venv_forensics/bin/mvt-android download-iocs -f /vagrant/mvt_iocs >/dev/null 2>&1 || true
else
    sudo /vagrant/.venv_forensics/bin/mvt-ios download-iocs -f /vagrant/mvt_iocs >/dev/null 2>&1 &
    sudo /vagrant/.venv_forensics/bin/mvt-android download-iocs -f /vagrant/mvt_iocs >/dev/null 2>&1 &
fi

sudo systemctl restart usbmuxd 2>/dev/null || true

if [ -t 1 ]; then
    echo "[*] Démarrage de l'outil d'analyse..."
    sudo PATH="/vagrant/.venv_forensics/bin:$PATH" /vagrant/.venv_forensics/bin/python main.py
else
    echo "[+] Pré-configuration de la VM terminée."
fi