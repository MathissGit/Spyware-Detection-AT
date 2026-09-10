#!/bin/bash
#
# Setup automatique du Spyware Detection Automated Tool
# ------------------------------------------------------
# Script unique couvrant Linux et macOS, base sur la documentation install.md.
# - Installe toutes les dependances systeme requises
# - Recupere automatiquement la dernière version d'AndroidQF
# - Cree l'environnement virtuel Python + MVT
# - Telecharge les bases IOC
# - Genere le script de lancement start_analysis.sh
#
# Usage :
#   sudo ./setup.sh            # interactif (choix sandbox / direct)
#   sudo ./setup.sh --direct   # mode direct (non interactif)
#   sudo ./setup.sh --sandbox  # mode sandbox (non interactif)
#   sudo ./setup.sh --force    # forcer le re-telechargement d'AndroidQF
#
set -euo pipefail

# ---------------------------------------------------------------- Detection
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ "$EUID" -ne 0 ]; then
    echo "[!] Lancez avec sudo : sudo ./setup.sh"
    exit 1
fi
REAL_USER=${SUDO_USER:-$USER}

# Dossier personnel (portable Linux / macOS)
real_home_of() {
    local u="${1:-}"
    if [ -n "$u" ]; then
        if [ "$(uname -s)" = "Darwin" ]; then
            local h
            h=$(dscl . -read "/Users/$u" NFSHomeDirectory 2>/dev/null || true)
            h="${h##*: }"
            [ -n "$h" ] && { printf '%s' "$h"; return 0; }
        else
            getent passwd "$u" 2>/dev/null | cut -d: -f6
        fi
    fi
    printf '%s' "$HOME"
}
REAL_HOME="$(real_home_of "${SUDO_USER:-}")"
[ -n "$REAL_HOME" ] || REAL_HOME="$HOME"

detect_os() {
    case "$(uname -s)" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "macos" ;;
        *)       echo "unknown" ;;
    esac
}
OS="$(detect_os)"

if [ "$OS" = "unknown" ]; then
    echo "[!] OS non supporte. Ce script fonctionne sur Linux et macOS uniquement."
    exit 1
fi

ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|amd64) AQF_ARCH="amd64" ;;
    aarch64|arm64) AQF_ARCH="arm64" ;;
    *) echo "[!] Architecture non supportee : $ARCH"; exit 1 ;;
esac

# ---------------------------------------------------------------- Arguments
MODE=""
FORCE_AQF=false
for arg in "$@"; do
    case "$arg" in
        --direct)  MODE="direct" ;;
        --sandbox) MODE="sandbox" ;;
        --force)   FORCE_AQF=true ;;
    esac
done

# ---------------------------------------------------------------- Banner
echo "[*] ==================================================="
echo "[*]   Installation du Spyware Detection Automated Tool"
echo "[*]   OS : $OS ($ARCH)"
echo "[*] ==================================================="
echo ""

# ---------------------------------------------------------- Choix du mode
if [ -z "$MODE" ]; then
    echo "[*] Choisissez le mode d'installation :"
    echo "  1) Sandbox (VM VirtualBox) - Recommande pour l'analyse d'appareils suspects"
    echo "  2) Mode direct             - Installation locale plus rapide, sans isolation"
    echo ""
    read -p "[>] Votre choix (1 ou 2) : " MODE_CHOICE
    if [ "$MODE_CHOICE" = "2" ]; then
        MODE="direct"
        echo "[*] Mode direct sélectionné."
    else
        MODE="sandbox"
        echo "[*] Mode sandbox sélectionné."
    fi
else
    echo "[*] Mode $MODE sélectionné."
fi

export DEBIAN_FRONTEND=noninteractive
REQUIRES_REBOOT=false

# ========================================================= ROLLBACK AUTOMATIQUE
# En cas de sortie avec code d'erreur (echec d'une etape), on supprime tout ce
# qui a ete cree pendant ce run et on desinstalle les paquets installes ici.
# Des suggestions de resolution sont ensuite affichees par etape.
TRACK_FILE="$(mktemp)"
APT_LOG="$(mktemp)"
BREW_LOG="$(mktemp)"
VBOX_GROUP_ADDED=false

track_file() {
    printf '%s\n' "$@" >> "$TRACK_FILE"
}

track_apt() {
    printf '%s\n' "$@" >> "$APT_LOG"
}

track_brew() {
    printf '%s\n' "$@" >> "$BREW_LOG"
}

rollback() {
    local status=$?
    [ "$status" -eq 0 ] && { rm -f "$TRACK_FILE" "$APT_LOG" "$BREW_LOG"; return 0; }

    echo ""
    echo "[!] ==============================================="
    echo "[!]   ECHEC D'INSTALLATION - Nettoyage automatique"
    echo "[!] ==============================================="

    # 1) Suppression des fichiers / dossiers crees pendant ce run
    if [ -s "$TRACK_FILE" ]; then
        echo "[*] Suppression des artefacts crees :"
        while IFS= read -r f; do
            [ -e "$f" ] || continue
            rm -rf "$f"
            echo "    - $f"
        done < "$TRACK_FILE"
    fi

    # 2) Les fichiers .stix2 dans mvt_iocs sont toujours generes par build_iocs.py
    if [ -d "$SCRIPT_DIR/mvt_iocs" ]; then
        rm -f "$SCRIPT_DIR"/mvt_iocs/*.stix2
    fi

    # 3) Reversement des modifications systeme du mode sandbox
    if [ -f /etc/modprobe.d/blacklist-kvm.conf ]; then
        rm -f /etc/modprobe.d/blacklist-kvm.conf
        modprobe kvm 2>/dev/null || true
        modprobe kvm_intel 2>/dev/null || true
        modprobe kvm_amd 2>/dev/null || true
        echo "    - blacklist KVM retire, modules KVM recharges"
    fi
    if [ "$VBOX_GROUP_ADDED" = true ] && [ -n "${REAL_USER:-}" ]; then
        gpasswd -d "$REAL_USER" vboxusers >/dev/null 2>&1 && \
            echo "    - $REAL_USER retire du groupe vboxusers"
    fi

    # 4) Desinstallation des paquets installes par ce run
    if [ "$OS" = "linux" ] && [ -s "$APT_LOG" ]; then
        local apt_pkgs=()
        while IFS= read -r p; do
            [ -n "$p" ] && apt_pkgs+=("$p")
        done < "$APT_LOG"
        echo "[*] Desinstallation des paquets apt installes par ce run :"
        echo "    ${apt_pkgs[*]:-aucun}"
        apt-get -y purge "${apt_pkgs[@]}" >/dev/null 2>&1 || true
        apt-get -y autoremove >/dev/null 2>&1 || true
    fi
    if [ "$OS" = "macos" ] && [ -s "$BREW_LOG" ]; then
        local brew_pkgs=()
        while IFS= read -r p; do
            [ -n "$p" ] && brew_pkgs+=("$p")
        done < "$BREW_LOG"
        echo "[*] Desinstallation des formules Homebrew installees par ce run :"
        echo "    ${brew_pkgs[*]:-aucun}"
        [ "${#brew_pkgs[@]}" -gt 0 ] && brew uninstall "${brew_pkgs[@]}" >/dev/null 2>&1 || true
    fi

    echo ""
    echo "[*] ==============================================="
    echo "[*]    COMMENT RESOUDRE LES ERREURS COURANTES"
    echo "[*] ==============================================="
    echo "  - Reseau : verifiez votre connexion / proxy puis relancez le setup."
    echo "  - apt : mettez a jour vos depots (sudo apt-get update) puis relancez."
    echo "  - pip : relancez ; si l'echec persiste, ajoutez un miroir :"
    echo "      .venv_forensics/bin/pip install -q mvt -i https://pypi.org/simple"
    echo "  - VirtualBox : installez linux-headers-$(uname -r) pour vboxdrv,"
    echo "      puis redemarrez pour recompiler le noyau VirtualBox."
    echo "  - Virtualisation : activez VT-x (Intel) / AMD-V dans le BIOS/UEFI,"
    echo "      desactivez Secure Boot si le module vboxdrv n'est pas signe."
    echo "  - AndroidQF : liberez de la place disque et verifiez l'acces a GitHub."
    echo "  - Journal : conservez la sortie du terminal pour diagnostiquer."
    echo ""
    echo "[!] Vous pouvez relancer : sudo ./setup.sh"
    rm -f "$TRACK_FILE" "$APT_LOG" "$BREW_LOG"
}

trap rollback EXIT
trap 'exit 130' INT TERM HUP

# ================================================================ DEPENDANCES
# Base officielle MVT : https://docs.mvt.re/en/latest/install/
echo "[*] Installation des dépendances système ($OS)..."

apt_update() {
    apt-get update >/dev/null 2>&1 || true
}

apt_install() {
    track_apt "$@"
    apt-get install -y -qq "$@" >/dev/null 2>&1 || apt-get install -y "$@"
}

brew_install() {
    track_brew "$@"
    brew install "$@" >/dev/null 2>&1 || brew install "$@"
}

if [ "$OS" = "linux" ]; then
    if ! command -v apt-get >/dev/null 2>&1; then
        echo "[!] Distributions non-APT non gérées automatiquement."
        echo "    Utilisez votre gestionnaire de paquets pour installer :"
        echo "    python3 python3-venv python3-pip sqlite3 libusb-1.0-0 adb \\"
        echo "    libimobiledevice-utils usbmuxd python3-tk wget curl jq git"
        echo "    puis relancez ce script avec --direct."
        exit 1
    fi
    apt_update
    # Paquets requis d'après install.md (Linux) + outils du projet
    apt_install python3 python3-venv python3-pip sqlite3 libusb-1.0-0 \
        adb libimobiledevice-utils usbmuxd python3-tk wget curl jq git

elif [ "$OS" = "macos" ]; then
    if ! command -v brew >/dev/null 2>&1; then
        echo "[*] Homebrew introuvable. Installation de Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    # install.md (macOS) : brew install python3 pipx libusb sqlite3
    # + outils du projet : adb (android-platform-tools), libimobiledevice
    brew update >/dev/null 2>&1 || true
    brew_install python3 pipx libusb sqlite3 libimobiledevice
    if ! command -v adb >/dev/null 2>&1; then
        echo "[*] Installation d'Android Platform Tools (adb)..."
        brew_install --cask android-platform-tools
    fi
fi

echo "[+] Dépendances système installées."

# ================================================================ ANDROIDQF
# Recuperation automatique de la dernière version d'AndroidQF via l'API GitHub
echo ""
echo "[*] Vérification d'AndroidQF..."

_aqf_exists() {
    compgen -G "androidqf_${OS}_${AQF_ARCH}_*" >/dev/null 2>&1 || compgen -G "androidqf_*" >/dev/null 2>&1
}

if $FORCE_AQF || ! _aqf_exists; then
    echo "[*] Récupération de la dernière version d'AndroidQF ($OS/$ARCH)..."
    if ! command -v curl >/dev/null 2>&1; then
        echo "[!] 'curl' requis pour télécharger AndroidQF."
        exit 1
    fi

    # nettoyer les anciens binaires
    rm -f androidqf_* 2>/dev/null || true

    API="https://api.github.com/repos/mvt-project/androidqf/releases/latest"
    ASSET_NAME=""
    VERSION=""

    if [ "$OS" = "linux" ]; then
        ASSET_NAME=$(curl -fsSL "$API" | jq -r --arg a "$AQF_ARCH" \
            '.assets[].name | select(startswith("androidqf_linux_" + $a)) | select(endswith("_signed") | not)' | head -1)
    elif [ "$OS" = "macos" ]; then
        ASSET_NAME=$(curl -fsSL "$API" | jq -r \
            '.assets[].name | select(startswith("androidqf_macos_universal_")) | select(endswith("_signed"))' | head -1)
    fi

    if [ -z "$ASSET_NAME" ] || [ "$ASSET_NAME" = "null" ]; then
        echo "[!] Impossible de localiser l'asset AndroidQF pour $OS/$ARCH."
        if [ "$OS" = "macos" ] && [ "$AQF_ARCH" = "arm64" ]; then
            echo "    AndroidQF macOS est un binaire universel. Vérifiez la page releases."
        fi
        exit 1
    fi

    VERSION=$(echo "$ASSET_NAME" | sed -E 's/.*_([0-9]+\.[0-9]+\.[0-9]+)(_signed)?$/\1/')
    URL="https://github.com/mvt-project/androidqf/releases/download/v${VERSION}/${ASSET_NAME}"

    echo "[*] Téléchargement de $ASSET_NAME"
    echo "    ($URL)"
    DOWNLOAD_NAME="${ASSET_NAME}"
    if [ ! -f "$ASSET_NAME" ]; then
        DOWNLOAD_NAME="androidqf_${OS}_${AQF_ARCH}_${VERSION}"
        curl -fL --progress-bar "$URL" -o "$DOWNLOAD_NAME" \
            || { echo "[!] Échec du téléchargement."; exit 1; }
    fi
    chmod +x "$DOWNLOAD_NAME"
    track_file "$DOWNLOAD_NAME"
    echo "[+] AndroidQF installé : $DOWNLOAD_NAME"
else
    echo "[+] AndroidQF déjà présent : $(ls androidqf_* 2>/dev/null | head -1)"
fi

# ============================================================ ENV PYTHON
echo ""
echo "[*] Vérification de l'environnement virtuel Python..."

if [ ! -d ".venv_forensics" ]; then
    echo "[*] Création de l'environnement virtuel Python (.venv_forensics)..."
    python3 -m venv .venv_forensics
    track_file "$SCRIPT_DIR/.venv_forensics"
    echo "[*] Mise à jour de pip..."
    .venv_forensics/bin/pip install --upgrade pip -q
    # MVT installé depuis PyPI dans le venv (install.md §venv)
    echo "[*] Installation des librairies d'analyse (mvt, rapports, IHM)..."
    .venv_forensics/bin/pip install -q mvt pyAesCrypt xhtml2pdf rich questionary customtkinter
    echo "[+] Environnement Python créé."
else
    echo "[+] Environnement Python déjà présent."
fi

# Assurer que les outils mvt sont disponibles
VEMVT=".venv_forensics/bin"
[ -x "$VEMVT/mvt-ios" ] || .venv_forensics/bin/pip install -q mvt --force-reinstall

# ================================================================ BASES IOC
echo ""
echo "[*] Vérification des bases IOC (mvt_iocs/)..."
mkdir -p "$SCRIPT_DIR/mvt_iocs"

IOC_STALE=true
if [ -d "$SCRIPT_DIR/mvt_iocs" ]; then
    IOC_FRESH=$(find "$SCRIPT_DIR/mvt_iocs" -type f -name '*.stix2' -mtime -7 2>/dev/null | wc -l | tr -d ' ')
    if [ "${IOC_FRESH:-0}" -gt 0 ]; then
        IOC_STALE=false
        echo "[+] Bases IOC déjà à jour (moins de 7 jours)."
    fi
fi

if [ "$IOC_STALE" = true ]; then
    echo "[*] Construction des bases IOC (personnelles + sources externes)..."
    # Utilise ioc_personal.json + ioc_sources.json via scripts/build_iocs.py.
    # Note: MVT charge aussi automatiquement les bases officielles via
    # download-iocs dans le dossier de donnees utilisateur.
    [ -x ".venv_forensics/bin/python" ] || { echo "[!] venv manquant."; exit 1; }
    .venv_forensics/bin/python scripts/build_iocs.py || exit 1
    echo "[+] Bases IOC construites."
fi

# ================================================================= SANDBOX
if [ "$MODE" = "sandbox" ]; then
    echo ""
    echo "[*] Installation des composants Sandbox (Vagrant + VirtualBox)..."

    if [ "$OS" = "linux" ]; then
        # --- Vagrant ---
        if ! command -v vagrant >/dev/null 2>&1 || ! vagrant --version 2>/dev/null | grep -q "2.4"; then
            echo "[*] Installation de la dernière version de Vagrant..."
            apt_install wget gnupg
            wget -qO- https://apt.releases.hashicorp.com/gpg | gpg --dearmor --yes -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
            track_file /usr/share/keyrings/hashicorp-archive-keyring.gpg
            echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com bookworm main" > /etc/apt/sources.list.d/hashicorp.list
            track_file /etc/apt/sources.list.d/hashicorp.list
            apt_update
            apt_install vagrant
        fi

        # --- VirtualBox ---
        if ! command -v virtualbox >/dev/null 2>&1; then
            VBOX_VER="7.0.20"
            VBOX_BUILD="163906"
            echo "[*] Installation des prérequis DKMS..."
            apt_install dkms build-essential linux-headers-$(uname -r) wget libelf-dev libssl-dev
            echo "[*] Téléchargement de VirtualBox ${VBOX_VER}..."
            wget -q --show-progress "https://download.virtualbox.org/virtualbox/${VBOX_VER}/VirtualBox-${VBOX_VER}-${VBOX_BUILD}-Linux_amd64.run" -O /tmp/vbox.run
            wget -q --show-progress "https://download.virtualbox.org/virtualbox/${VBOX_VER}/Oracle_VM_VirtualBox_Extension_Pack-${VBOX_VER}.vbox-extpack" -O /tmp/extpack.vbox-extpack
            echo "[*] Compilation et installation..."
            chmod +x /tmp/vbox.run
            /tmp/vbox.run || true
            /sbin/vboxconfig || true
            if ! command -v vboxmanage >/dev/null 2>&1; then
                echo "[!] L'installation de VirtualBox a échoué. Vérifiez que votre noyau est à jour."
                rm -f /tmp/vbox.run /tmp/extpack.vbox-extpack
                exit 1
            fi
            echo "[*] Installation de l'Extension Pack..."
            echo "y" | vboxmanage extpack install --replace /tmp/extpack.vbox-extpack
            rm -f /tmp/vbox.run /tmp/extpack.vbox-extpack
            REQUIRES_REBOOT=true
        fi

        # libérer le processeur pour la virtualisation imbriquée
        modprobe -r kvm_intel 2>/dev/null || true
        modprobe -r kvm_amd 2>/dev/null || true
        modprobe -r kvm 2>/dev/null || true
        if [ ! -f /etc/modprobe.d/blacklist-kvm.conf ]; then
            echo -e "blacklist kvm\nblacklist kvm_intel\nblacklist kvm_amd" > /etc/modprobe.d/blacklist-kvm.conf
            track_file /etc/modprobe.d/blacklist-kvm.conf
            update-initramfs -u > /dev/null 2>&1 || true
            REQUIRES_REBOOT=true
        fi

        if ! id -nG "$REAL_USER" 2>/dev/null | grep -qw "vboxusers"; then
            usermod -aG vboxusers "$REAL_USER" 2>/dev/null || true
            VBOX_GROUP_ADDED=true
            REQUIRES_REBOOT=true
        fi

    elif [ "$OS" = "macos" ]; then
        echo "[*] Installation de VirtualBox et Vagrant via Homebrew..."
        brew_install --cask virtualbox
        brew_install --cask vagrant
    fi

    # ------------------------- Gestion de la VM existante
    VM_NAME="sandbox_forensics"
    VM_EXISTS=false
    if command -v vboxmanage >/dev/null 2>&1 && vboxmanage list vms 2>/dev/null | grep -q "\"${VM_NAME}\""; then
        VM_EXISTS=true
    fi

    if [ "$VM_EXISTS" = true ]; then
        echo ""
        echo "[!] Une VM '${VM_NAME}' existe déjà sur cette machine."
        echo "    Réutiliser la VM existante peut causer des problèmes de performance ou de conflits."
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

    # ------------------------- Génération de start_analysis.sh (sandbox)
    echo "[*] Génération du script de lancement start_analysis.sh..."
    cat << 'SANDBOX_EOF' > start_analysis.sh
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

export VAGRANT_DEFAULT_PROVIDER=virtualbox

# Les fichiers .stix2 de mvt_iocs/ (personnels + sources externes) sont
# charges par MVT automatiquement via la variable MVT_STIX2.
export MVT_STIX2="$SCRIPT_DIR/mvt_iocs"

cleanup() {
    echo -e "\n[*] Nettoyage de la VM..."
    vagrant destroy -f >/dev/null 2>&1 || true
    killall -9 adb >/dev/null 2>&1 || true
    sudo -n killall -9 adb >/dev/null 2>&1 || true
    rm -f "$SCRIPT_DIR/.sandbox_provision.log"
}

trap cleanup EXIT INT TERM HUP

echo "[*] ==================================================="
echo "[*] Lancement de l'environnement d'analyse"
echo "[*] ==================================================="

mkdir -p "$SCRIPT_DIR/mvt_iocs"

IOC_STALE=true
if [ -d "$SCRIPT_DIR/mvt_iocs" ] && [ "$(ls -A "$SCRIPT_DIR/mvt_iocs" 2>/dev/null)" ]; then
    NEWEST_IOC=$(find "$SCRIPT_DIR/mvt_iocs" -type f -name '*.stix2' -printf '%T@\n' 2>/dev/null | sort -rn | head -1)
    if [ -n "$NEWEST_IOC" ]; then
        AGE_HOURS=$(( ($(date +%s) - ${NEWEST_IOC%.*}) / 3600 ))
        if [ "$AGE_HOURS" -lt 168 ]; then
            IOC_STALE=false
            echo "[*] Bases IOC déjà à jour (${AGE_HOURS}h)."
        fi
    fi
fi

if [ "$IOC_STALE" = true ]; then
    echo "[*] Construction des bases IOC (personnelles + sources externes)..."
    if [ ! -d ".venv_forensics" ]; then
        python3 -m venv .venv_forensics
        .venv_forensics/bin/pip install -q mvt customtkinter
    fi
    .venv_forensics/bin/python scripts/build_iocs.py
    echo "[+] Bases IOC construites."
fi

echo "[*] Démarrage de la Sandbox..."
set +e
vagrant up 2>&1 | tee "$SCRIPT_DIR/.sandbox_provision.log"
VAGRANT_RC=${PIPESTATUS[0]}
set -e
if [ "$VAGRANT_RC" -ne 0 ]; then
    echo -e "\n[!] Échec du démarrage / provisionnement de la Sandbox (code $VAGRANT_RC)."
    echo "[!] Fin du journal (détail complet : .sandbox_provision.log) :"
    tail -n 60 "$SCRIPT_DIR/.sandbox_provision.log" 2>/dev/null || true
    echo -e "\n[!] Causes fréquentes : "
    echo "    - DNS ne peut pas résoudre deb.debian.org dans la VM (VPN/entreprise) :"
    echo "      exportez http_proxy/https_proxy avant de relancer, ou vérifiez le proxy."
    exit 1
fi
rm -f "$SCRIPT_DIR/.sandbox_provision.log"

echo "[+] Environnement isolé prêt et sécurisé."
echo "[+] Bases IOC : $([ "$IOC_STALE" = true ] && echo 'mises à jour' || echo 'déjà à jour')"
echo "[*] Branchez le téléphone par USB maintenant (capturé par la VM)."
echo ""

killall adb >/dev/null 2>&1 || true
sudo -n killall adb >/dev/null 2>&1 || true
echo "[*] Choisissez l'interface :"
echo "  1) Interface graphique (IHM) - Recommandé"
echo "  2) Interface en ligne de commande (CLI)"
echo ""
read -p "[>] Votre choix (1 ou 2) : " UI_CHOICE
if [ "$UI_CHOICE" = "2" ]; then
    echo "[*] Lancement du CLI sur l'hôte (analyse dans la VM)..."
    ./scripts/launch.sh cli --mode sandbox
else
    echo "[*] Lancement de l'interface graphique sur l'hôte (analyse dans la VM)..."
    ./scripts/launch.sh gui --mode sandbox
fi
SANDBOX_EOF
fi

# ================================================================= DIRECT
if [ "$MODE" = "direct" ]; then
    echo ""
    echo "[*] Génération du script de lancement start_analysis.sh (mode direct)..."
    cat << 'DIRECT_EOF' > start_analysis.sh
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Les fichiers .stix2 de mvt_iocs/ (personnels + sources externes) sont
# charges par MVT automatiquement via la variable MVT_STIX2.
export MVT_STIX2="$SCRIPT_DIR/mvt_iocs"

echo "[*] ==================================================="
echo "[*] Lancement de l'environnement d'analyse"
echo "[*] ==================================================="
echo "[*] Choisissez l'interface :"
echo "  1) Interface graphique (IHM) - Recommandé"
echo "  2) Interface en ligne de commande (CLI)"
echo ""
read -p "[>] Votre choix (1 ou 2) : " UI_CHOICE

if [ "$UI_CHOICE" = "2" ]; then
    echo "[*] Branchez le téléphone par USB maintenant."
    if ! read -t 500 -p "[>] Appuyez sur Entrée quand le téléphone est branché... "; then
        echo -e "\n[!] Délai d'inactivité dépassé."
        exit 0
    fi
    killall adb >/dev/null 2>&1 || true
    ./scripts/launch.sh cli
else
    echo "[*] Lancement de l'interface graphique..."
    ./scripts/launch.sh gui
fi
DIRECT_EOF
fi

chmod +x start_analysis.sh
chown "$REAL_USER":"$REAL_USER" start_analysis.sh 2>/dev/null || true
track_file "$SCRIPT_DIR/start_analysis.sh"
echo "[+] start_analysis.sh généré : $SCRIPT_DIR/start_analysis.sh"

# ==================================================== LANCEMENT
echo ""
echo "[*] L'interface se lance via : $SCRIPT_DIR/start_analysis.sh"
echo "[+] Aucun raccourci bureau n'est créé (non fiable en GUI)."

# =================================================================== FIN
echo ""
echo "[*] ==================================================="
echo "[*]   Installation terminée"
echo "[*] ==================================================="
chown "$REAL_USER":"$REAL_USER" icon.png 2>/dev/null || true

if [ "$REQUIRES_REBOOT" = true ]; then
    echo -e "\n[!] Redémarrage système requis pour finaliser l'installation."
    if [ -t 0 ]; then
        read -p "[>] Appuyez sur Entrée pour redémarrer l'ordinateur immédiatement..."
        systemctl reboot -i 2>/dev/null || reboot -i
    else
        echo "[!] Veuillez redémarrer manuellement puis lancer './start_analysis.sh'."
    fi
else
    echo -e "\n[+] Environnement prêt. Vous pouvez lancer './start_analysis.sh' à la racine."
fi
