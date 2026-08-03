#!/bin/bash
set -e

cd "$(dirname "$0")/.."

[ "$EUID" -ne 0 ] && echo "[!] Lancez avec sudo" && exit 1
REAL_USER=${SUDO_USER:-$USER}

echo "[*] Vérification de l'hôte..."
export DEBIAN_FRONTEND=noninteractive

if ! command -v vagrant >/dev/null 2>&1 || ! vagrant --version | grep -q "2.4"; then
    echo "[*] Installation de la dernière version de Vagrant..."
    apt-get update
    apt-get install -y wget gnupg
    
    wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor --yes -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com bookworm main" > /etc/apt/sources.list.d/hashicorp.list
    
    apt-get update
    apt-get install -y vagrant
fi

REQUIRES_REBOOT=false

if ! command -v virtualbox >/dev/null 2>&1; then
    
    VBOX_VER="7.0.20"
    VBOX_BUILD="163906"
    
    echo "[*] Installation DKMS..."
    apt-get update
    apt-get install -y dkms build-essential linux-headers-$(uname -r) wget

    echo "[*] Téléchargement de VirtualBox ${VBOX_VER}..."
    wget -q --show-progress "https://download.virtualbox.org/virtualbox/${VBOX_VER}/VirtualBox-${VBOX_VER}-${VBOX_BUILD}-Linux_amd64.run" -O vbox.run
    wget -q --show-progress "https://download.virtualbox.org/virtualbox/${VBOX_VER}/Oracle_VM_VirtualBox_Extension_Pack-${VBOX_VER}.vbox-extpack" -O extpack.vbox-extpack

    echo "[*] Compilation et installation..."
    chmod +x vbox.run
    ./vbox.run || true

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

echo "[*] Génération du script de lancement start_analysis.sh..."
cat << 'EOF' > start_analysis.sh
#!/bin/bash
set -e

export VAGRANT_DEFAULT_PROVIDER=virtualbox
SNAPSHOT_NAME="VM_clean"

cleanup() {
    echo -e "\n[*] Clôture de la VM..."
    if vagrant snapshot list 2>/dev/null | grep -q "$SNAPSHOT_NAME"; then
        vagrant snapshot restore "$SNAPSHOT_NAME" >/dev/null 2>&1 || true
    fi
    vagrant halt -f >/dev/null 2>&1 || true
    killall -9 adb >/dev/null 2>&1 || true
    sudo -n killall -9 adb >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM HUP

echo "[*] ==================================================="
echo "[*] Lancement de l'environnement d'analyse"
echo "[*] ==================================================="

if [ ! -f ".vagrant/machines/default/virtualbox/id" ]; then
    vboxmanage unregistervm "sandbox_forensic_light" --delete >/dev/null 2>&1 || true
fi

echo "[*] Vérification et démarrage de la Sandbox..."
vagrant up

if ! vagrant snapshot list | grep -q "$SNAPSHOT_NAME"; then
    echo "[*] Création du snapshot..."
    vagrant snapshot save "$SNAPSHOT_NAME"
else
    echo "[*] Restauration du snapshot..."
    vagrant snapshot restore "$SNAPSHOT_NAME"
fi

echo "[+] Environnement isolé prêt et sécurisé."
echo "[*] Branchez le téléphone par USB maintenant."

if ! read -t 500 -p "[>] Appuyez sur Entrée quand le téléphone est branché... "; then
    echo -e "\n[!] Délai d'inactivité dépassé. Arrêt du système."
    exit 0 
fi

killall adb >/dev/null 2>&1 || true
sudo -n killall adb >/dev/null 2>&1 || true
vagrant ssh -t -c "cd /vagrant && ./sandbox_env.sh"
EOF

chmod +x start_analysis.sh
chown "$REAL_USER":"$REAL_USER" start_analysis.sh

if [ "$REQUIRES_REBOOT" = true ]; then
    echo -e "\n[!] Redémarrage système requis pour finaliser l'installation."
    read -p "[>] Appuyez sur Entrée pour redémarrer l'ordinateur immédiatement..."
    sudo systemctl reboot -i
else
    echo -e "\n[+] Environnement prêt. Vous pouvez lancer './start_analysis.sh' à la racine."
fi