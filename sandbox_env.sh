#!/bin/bash
set -e

cd /vagrant

echo "[*] Vérification de l'environnement interne de la Sandbox..."

if ! command -v adb >/dev/null 2>&1 || ! command -v idevicebackup2 >/dev/null 2>&1; then
    echo "[*] Installation des paquets système de base..."
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3-venv python3-pip adb libimobiledevice-utils usbmuxd build-essential python3-dev
fi

echo "[*] Vérification des bases IOC..."
IOC_COUNT=$(find /vagrant/mvt_iocs -type f 2>/dev/null | wc -l)
if [ "$IOC_COUNT" -gt 0 ]; then
    echo "[+] Bases IOC prêtes depuis l'hôte (${IOC_COUNT} fichiers)."
else
    echo "[!] Aucune base IOC trouvée. Téléchargement depuis la VM..."
    mkdir -p /vagrant/mvt_iocs
    sudo /vagrant/.venv_forensics/bin/mvt-ios download-iocs -f /vagrant/mvt_iocs >/dev/null 2>&1 &
    sudo /vagrant/.venv_forensics/bin/mvt-android download-iocs -f /vagrant/mvt_iocs >/dev/null 2>&1 &
    wait
fi

if [ ! -d ".venv_forensics" ]; then
    echo "[*] Création de l'environnement virtuel Python..."
    python3 -m venv .venv_forensics

    echo "[*] Installation des librairies d'analyse..."
    .venv_forensics/bin/pip install --upgrade pip -q
    .venv_forensics/bin/pip install -q mvt pyAesCrypt xhtml2pdf rich questionary
fi

sudo systemctl restart usbmuxd 2>/dev/null || true

if [ -t 1 ]; then
    echo "[*] Démarrage de l'outil d'analyse..."
    sudo PATH="/vagrant/.venv_forensics/bin:$PATH" /vagrant/.venv_forensics/bin/python main.py
else
    echo "[+] Pré-configuration de la VM terminée."
fi
