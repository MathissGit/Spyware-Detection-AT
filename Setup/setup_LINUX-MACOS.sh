#!/bin/bash
set -e

cd "$(dirname "$0")/.."

[ "$EUID" -ne 0 ] && echo "[!] Lancez avec sudo" && exit 1
REAL_USER=${SUDO_USER:-$USER}

echo "[*] ==================================================="
echo "[*]   Installation du Spyware Detection Automated Tool"
echo "[*] ==================================================="
echo ""
echo "[*] Choisissez le mode d'installation :"
echo "  1) Sandbox (VM VirtualBox) - Recommande pour l'analyse d'appareils suspects"
echo "  2) Mode direct              - Installation locale plus rapide, sans isolation"
echo ""
read -p "[>] Votre choix (1 ou 2) : " MODE_CHOICE

if [ "$MODE_CHOICE" = "2" ]; then
    MODE="direct"
    echo "[*] Mode direct sélectionné."
else
    MODE="sandbox"
    echo "[*] Mode sandbox sélectionné."
fi

export DEBIAN_FRONTEND=noninteractive
REQUIRES_REBOOT=false

if [ "$MODE" = "sandbox" ]; then
    echo "[*] Vérification de l'hôte (sandbox)..."

    if ! command -v vagrant >/dev/null 2>&1 || ! vagrant --version | grep -q "2.4"; then
        echo "[*] Installation de la dernière version de Vagrant..."
        apt-get update
        apt-get install -y wget gnupg

        wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor --yes -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
        echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com bookworm main" > /etc/apt/sources.list.d/hashicorp.list

        apt-get update
        apt-get install -y vagrant
    fi

    if ! command -v virtualbox >/dev/null 2>&1; then

        VBOX_VER="7.0.20"
        VBOX_BUILD="163906"

        echo "[*] Installation des prérequis DKMS..."
        apt-get update
        apt-get install -y dkms build-essential linux-headers-$(uname -r) wget libelf-dev libssl-dev

        echo "[*] Téléchargement de VirtualBox ${VBOX_VER}..."
        wget -q --show-progress "https://download.virtualbox.org/virtualbox/${VBOX_VER}/VirtualBox-${VBOX_VER}-${VBOX_BUILD}-Linux_amd64.run" -O vbox.run
        wget -q --show-progress "https://download.virtualbox.org/virtualbox/${VBOX_VER}/Oracle_VM_VirtualBox_Extension_Pack-${VBOX_VER}.vbox-extpack" -O extpack.vbox-extpack

        echo "[*] Compilation et installation..."
        chmod +x vbox.run
        ./vbox.run || true

        echo "[*] Vérification de l'intégration au noyau..."
        /sbin/vboxconfig || true

        if ! command -v vboxmanage >/dev/null 2>&1; then
            echo "[!] L'installation de VirtualBox a échoué. Vérifiez que votre noyau est à jour."
            rm -f vbox.run extpack.vbox-extpack
            exit 1
        fi

        echo "[*] Installation de l'Extension Pack..."
        echo "y" | vboxmanage extpack install --replace extpack.vbox-extpack

        rm -f vbox.run extpack.vbox-extpack
        REQUIRES_REBOOT=true
    fi

    VM_NAME="sandbox_forensics"
    VM_EXISTS=false
    if command -v vboxmanage >/dev/null 2>&1; then
        if vboxmanage list vms 2>/dev/null | grep -q "\"${VM_NAME}\""; then
            VM_EXISTS=true
        fi
    fi

    if [ "$VM_EXISTS" = true ]; then
        echo ""
        echo "[!] Une VM '${VM_NAME}' existe déjà sur cette machine."
        echo "    Réutiliser la VM existante peut causer des problèmes de performance"
        echo "    ou des conflits lors de l'analyse."
        echo ""
        read -p "[>] Voulez-vous détruire la VM et tout réinstaller proprement ? (O/n) : " REINSTALL_CHOICE
        REINSTALL_CHOICE=${REINSTALL_CHOICE:-O}

        if [ "$REINSTALL_CHOICE" = "O" ] || [ "$REINSTALL_CHOICE" = "o" ]; then
            echo "[*] Arrêt et suppression de la VM existante..."
            vagrant destroy -f 2>/dev/null || true
            vboxmanage unregistervm "${VM_NAME}" --delete 2>/dev/null || true
            rm -rf .vagrant

            echo "[*] Nettoyage de l'environnement Python..."
            rm -rf .venv_forensics

            echo "[+] VM supprimée. Réinstallation propre..."
        else
            echo "[*] Conservation de la VM existante."
        fi
    fi

    echo "[*] Libération du processeur..."
    modprobe -r kvm_intel 2>/dev/null || true
    modprobe -r kvm_amd 2>/dev/null || true
    modprobe -r kvm 2>/dev/null || true

    if [ ! -f /etc/modprobe.d/blacklist-kvm.conf ]; then
        echo -e "blacklist kvm\nblacklist kvm_intel\nblacklist kvm_amd" > /etc/modprobe.d/blacklist-kvm.conf
        echo "[*] Mise à jour de l'image de démarrage..."
        update-initramfs -u > /dev/null 2>&1 || true
        REQUIRES_REBOOT=true
    fi

    if ! id -nG "$REAL_USER" | grep -qw "vboxusers"; then
        echo "[*] Ajout de '$REAL_USER' au groupe 'vboxusers'..."
        usermod -aG vboxusers "$REAL_USER"
        REQUIRES_REBOOT=true
    fi

    echo "[*] Génération du script de lancement start_analysis.sh (sandbox)..."
    cat << 'SANDBOX_EOF' > start_analysis.sh
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

export VAGRANT_DEFAULT_PROVIDER=virtualbox

cleanup() {
    echo -e "\n[*] Nettoyage de la VM..."
    vagrant destroy -f >/dev/null 2>&1 || true
    killall -9 adb >/dev/null 2>&1 || true
    sudo -n killall -9 adb >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM HUP

echo "[*] ==================================================="
echo "[*] Lancement de l'environnement d'analyse (Sandbox)"
echo "[*] ==================================================="

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

if [ "$IOC_STALE" = true ]; then
    echo "[*] Téléchargement des bases IOC sur l'hôte (partagées avec la VM)..."
    if [ ! -d ".venv_forensics" ]; then
        python3 -m venv .venv_forensics
        .venv_forensics/bin/pip install -q mvt
    fi
    sudo "$SCRIPT_DIR/.venv_forensics/bin/mvt-ios" download-iocs -f "$SCRIPT_DIR/mvt_iocs" >/dev/null 2>&1 &
    sudo "$SCRIPT_DIR/.venv_forensics/bin/mvt-android" download-iocs -f "$SCRIPT_DIR/mvt_iocs" >/dev/null 2>&1 &
    wait
    echo "[+] Bases IOC téléchargées."
fi

echo "[*] Démarrage de la Sandbox..."
vagrant up

echo "[+] Environnement isolé prêt et sécurisé."
echo "[+] Bases IOC : $([ "$IOC_STALE" = true ] && echo 'mises à jour' || echo 'déjà à jour')"
echo "[*] Branchez le téléphone par USB maintenant."

if ! read -t 500 -p "[>] Appuyez sur Entrée quand le téléphone est branché... "; then
    echo -e "\n[!] Délai d'inactivité dépassé. Arrêt du système."
    exit 0
fi

killall adb >/dev/null 2>&1 || true
sudo -n killall adb >/dev/null 2>&1 || true
vagrant ssh -t -c "cd /vagrant && ./sandbox_env.sh"
SANDBOX_EOF

else
    echo "[*] Installation en mode direct (sans VM)..."

    echo "[*] Installation des dépendances système..."
    apt-get update
    apt-get install -y python3 python3-venv python3-pip adb libimobiledevice-utils usbmuxd

    echo "[*] Génération du script de lancement start_analysis.sh (direct)..."
    cat << 'DIRECT_EOF' > start_analysis.sh
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "[*] ==================================================="
echo "[*] Lancement de l'environnement d'analyse (Mode Direct)"
echo "[*] ==================================================="
echo "[*] Branchez le téléphone par USB maintenant."

if ! read -t 500 -p "[>] Appuyez sur Entrée quand le téléphone est branché... "; then
    echo -e "\n[!] Délai d'inactivité dépassé."
    exit 0
fi

killall adb >/dev/null 2>&1 || true
./direct_env.sh
DIRECT_EOF

fi

chmod +x start_analysis.sh
chown "$REAL_USER":"$REAL_USER" start_analysis.sh

if [ "$REQUIRES_REBOOT" = true ]; then
    echo -e "\n[!] Redémarrage système requis pour finaliser l'installation."
    read -p "[>] Appuyez sur Entrée pour redémarrer l'ordinateur immédiatement..."
    sudo systemctl reboot -i
else
    echo -e "\n[+] Environnement prêt. Vous pouvez lancer './start_analysis.sh' à la racine."
fi
