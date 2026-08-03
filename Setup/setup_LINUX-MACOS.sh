#!/bin/bash
set -e

cd "$(dirname "$0")/.."

[ "$EUID" -ne 0 ] && echo "[!] Lancez avec sudo" && exit 1
REAL_USER=${SUDO_USER:-$USER}

echo "[*] Vérification de l'hôte..."
export DEBIAN_FRONTEND=noninteractive

if ! command -v vagrant >/dev/null 2>&1 || ! vagrant --version | grep -q "2.4"; then
    echo "[*] Installation de la dernière version officielle de Vagrant..."
    apt-get update
    apt-get install -y wget gnupg
    
    wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor --yes -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com bookworm main" > /etc/apt/sources.list.d/hashicorp.list
    
    apt-get update
    apt-get install -y vagrant
else
    echo "[+] Vagrant déjà installé."
fi

REQUIRES_REBOOT=false

if ! command -v virtualbox >/dev/null 2>&1; then
    echo "[*] Utilisation de l'installateur universel Oracle indépendant de APT..."
    
    VBOX_VER="7.0.20"
    VBOX_BUILD="163906"
    
    echo "[*] Installation des prérequis de compilation du noyau (DKMS)..."
    apt-get update
    apt-get install -y dkms build-essential linux-headers-amd64 wget

    echo "[*] Téléchargement de VirtualBox ${VBOX_VER}..."
    wget -q --show-progress "https://download.virtualbox.org/virtualbox/${VBOX_VER}/VirtualBox-${VBOX_VER}-${VBOX_BUILD}-Linux_amd64.run" -O vbox.run
    wget -q --show-progress "https://download.virtualbox.org/virtualbox/${VBOX_VER}/Oracle_VM_VirtualBox_Extension_Pack-${VBOX_VER}.vbox-extpack" -O extpack.vbox-extpack

    echo "[*] Compilation et installation de VirtualBox (Patientez quelques minutes)..."
    chmod +x vbox.run
    ./vbox.run || true

    if ! command -v vboxmanage >/dev/null 2>&1; then
        echo "[!] L'installation de VirtualBox a échoué. Vérifiez que votre noyau est à jour."
        rm -f vbox.run extpack.vbox-extpack
        exit 1
    fi

    echo "[*] Installation de l'Extension Pack (Support USB)..."
    echo "y" | vboxmanage extpack install --replace extpack.vbox-extpack
    
    rm -f vbox.run extpack.vbox-extpack
    REQUIRES_REBOOT=true
else
    echo "[+] VirtualBox est déjà installé."
fi

echo "[*] Libération du processeur (Désactivation des modules KVM conflictuels)..."
modprobe -r kvm_intel 2>/dev/null || true
modprobe -r kvm_amd 2>/dev/null || true
modprobe -r kvm 2>/dev/null || true

if [ ! -f /etc/modprobe.d/blacklist-kvm.conf ]; then
    echo -e "blacklist kvm\nblacklist kvm_intel\nblacklist kvm_amd" > /etc/modprobe.d/blacklist-kvm.conf
    echo "[*] Mise à jour de l'image de démarrage (Patientez)..."
    update-initramfs -u > /dev/null 2>&1 || true
    REQUIRES_REBOOT=true
fi

if ! id -nG "$REAL_USER" | grep -qw "vboxusers"; then
    echo "[*] Ajout de '$REAL_USER' au groupe 'vboxusers'..."
    usermod -aG vboxusers "$REAL_USER"
    REQUIRES_REBOOT=true
else
    echo "[+] Droits USB déjà configurés."
fi

echo "[*] Génération du script de lancement (start_analysis.sh)..."
cat << 'EOF' > start_analysis.sh
#!/bin/bash
set -e

export VAGRANT_DEFAULT_PROVIDER=virtualbox
SNAPSHOT_NAME="VM_clean"

cleanup() {
    echo -e "\n[*] Clôture de la session. Sécurisation et extinction de la VM..."
    if vagrant snapshot list 2>/dev/null | grep -q "$SNAPSHOT_NAME"; then
        vagrant snapshot restore "$SNAPSHOT_NAME" >/dev/null 2>&1 || true
    fi
    vagrant halt -f >/dev/null 2>&1 || true
    killall -9 adb >/dev/null 2>&1 || true
    sudo -n killall -9 adb >/dev/null 2>&1 || true
    echo "[+] Sandbox immaculée et éteinte. Vos données sont en sécurité."
}

trap cleanup EXIT INT TERM HUP

echo "[*] ==================================================="
echo "[*] Lancement de l'environnement Forensique Sécurisé"
echo "[*] ==================================================="

if [ ! -f ".vagrant/machines/default/virtualbox/id" ]; then
    vboxmanage unregistervm "sandbox_forensic_light" --delete >/dev/null 2>&1 || true
fi

echo "[*] Vérification et démarrage de la Sandbox..."
vagrant up

if ! vagrant snapshot list | grep -q "$SNAPSHOT_NAME"; then
    echo "[*] 1er lancement détecté. Création du Snapshot (Image figée)..."
    vagrant snapshot save "$SNAPSHOT_NAME"
else
    echo "[*] Restauration préventive de la VM à son état vierge..."
    vagrant snapshot restore "$SNAPSHOT_NAME"
fi

echo "[+] Environnement isolé prêt et sécurisé."
echo "[*] Branchez le téléphone suspect par USB maintenant."

if ! read -t 900 -p "[>] Appuyez sur Entrée quand le téléphone est branché (Extinction auto dans 15 min)... "; then
    echo -e "\n[!] Délai d'inactivité dépassé. Arrêt de sécurité du système."
    exit 0 
fi

echo -e "\n[*] Libération du port USB sur l'hôte physique..."
killall adb >/dev/null 2>&1 || true
sudo -n killall adb >/dev/null 2>&1 || true

echo "[*] Entrée dans la Sandbox..."
vagrant ssh -t -c "cd /vagrant && ./sandbox_env.sh"
EOF

chmod +x start_analysis.sh
chown "$REAL_USER":"$REAL_USER" start_analysis.sh
echo "[+] 'start_analysis.sh' généré avec succès à la racine."

if [ "$REQUIRES_REBOOT" = true ]; then
    echo -e "\n[!] Redémarrage système requis pour finaliser l'installation (Pilotes USB/Groupes)."
    read -p "[>] Appuyez sur Entrée pour redémarrer l'ordinateur immédiatement..."
    reboot
else
    echo -e "\n[+] Environnement hôte prêt. Vous pouvez lancer './start_analysis.sh' à la racine."
fi