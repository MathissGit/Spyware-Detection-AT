#!/bin/bash
set -e

# Lanceur unifie des environnements direct / sandbox.
# Usage : launch.sh [cli|gui]   (defaut : gui)
#   - cli : interface en ligne de commande (main.py)
#   - gui : interface graphique (gui.py)
#
# Le contexte est detecte automatiquement :
#   - /vagrant existe       => mode Sandbox (VM), ROOT=/vagrant
#   - sinon                 => mode direct (hote), ROOT=dossier du projet
# En Sandbox sans terminal (provision Vagrant), seul le pre-configuration
# de la VM est effectuee (aucune interface lancee).
#
# Environnement virtuel :
#   - mode direct : $ROOT/.venv_forensics
#   - sandbox     : /opt/venv_forensics (local a la VM : le venv de l'hote,
#     partage via /vagrant, n'est pas portable car il pointe vers le python hote)

SANDBOX=false
if [ -d /vagrant ]; then
    SANDBOX=true
    ROOT="/vagrant"
else
    ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi
cd "$ROOT"

UI="${1:-gui}"

# Mode d'exécution transmis à l'interface (direct|sandbox).
MODE="direct"
shift 2>/dev/null || true
while [ $# -gt 0 ]; do
    case "$1" in
        --mode) MODE="${2:-direct}"; shift 2;;
        *) shift;;
    esac
done

# Les fichiers .stix2 de mvt_iocs/ (personnels + sources externes) sont
# charges par MVT automatiquement via la variable MVT_STIX2.
export MVT_STIX2="$ROOT/mvt_iocs"

# ----- Proxy (VPN / entreprise) & helpers apt fiables -----
APT_PROXY_ARGS=()
if [ -n "${HTTP_PROXY:-}" ] || [ -n "${http_proxy:-}" ]; then
    APT_PROXY_ARGS+=( -o "Acquire::http::Proxy=${HTTP_PROXY:-$http_proxy}" )
fi
if [ -n "${HTTPS_PROXY:-}" ] || [ -n "${https_proxy:-}" ]; then
    APT_PROXY_ARGS+=( -o "Acquire::https::Proxy=${HTTPS_PROXY:-$https_proxy}" )
fi

# En sandbox (VM), on rafraichit la resolution DNS entre les tentatives.
sandbox_fix_dns() {
    rm -f /etc/resolv.conf
    printf '%s\n' 'nameserver 10.0.2.3' 'nameserver 8.8.8.8' 'nameserver 1.1.1.1' > /etc/resolv.conf
}

apt_update_retry() {
    local attempt
    for attempt in 1 2 3; do
        if sudo apt-get update -qq "${APT_PROXY_ARGS[@]}"; then
            return 0
        fi
        echo "[!] apt-get update a échoué (tentative ${attempt}/3). Nouvel essai dans 5s..."
        sleep 5
        if [ "$SANDBOX" = true ]; then
            sandbox_fix_dns
        fi
    done
    return 1
}

if [ "$SANDBOX" = true ]; then
    echo "[*] Vérification de l'environnement interne de la Sandbox..."
else
    echo "[*] Vérification de l'environnement local (mode direct)..."
fi

# ----- Paquets systeeme -----
SYSTEM_PKGS="python3-venv python3-pip adb libimobiledevice-utils usbmuxd"
if [ "$SANDBOX" = true ]; then
    SYSTEM_PKGS="$SYSTEM_PKGS build-essential python3-dev"
fi

if ! command -v adb >/dev/null 2>&1 || ! command -v idevicebackup2 >/dev/null 2>&1; then
    echo "[*] Installation des paquets système de base..."
    export DEBIAN_FRONTEND=noninteractive
    if [ "$SANDBOX" = true ]; then
        sandbox_fix_dns
    fi
    if ! apt_update_retry; then
        echo "[!] ================================================================"
        echo "[!] Échec de apt-get update dans l'environnement d'analyse."
        echo "[!] Vérifiez le réseau (DNS / proxy) :"
        echo "[!]   - VPN/entreprise : exportez http_proxy=https_proxy avant de lancer."
        echo "[!]   - Puis : vagrant destroy -f && ./start_analysis.sh (sandbox)."
        echo "[!] ================================================================"
        exit 1
    fi
    # shellcheck disable=SC2086
    if ! sudo apt-get install -y -qq "${APT_PROXY_ARGS[@]}" $SYSTEM_PKGS; then
        echo "[!] ================================================================"
        echo "[!] Échec de l'installation des paquets système ($SYSTEM_PKGS)."
        echo "[!] Network / proxy : relancez avec le proxy exporté, ou vérifiez DNS."
        echo "[!] ================================================================"
        exit 1
    fi
fi

echo "[*] Vérification de python3-tk (interface graphique)..."
if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    if [ "$SANDBOX" = true ]; then
        sandbox_fix_dns
    fi
    if ! apt_update_retry; then
        echo "[!] Échec de apt-get update (python3-tk). Vérifiez le réseau/proxy."
        exit 1
    fi
    sudo apt-get install -y -qq "${APT_PROXY_ARGS[@]}" python3-tk
fi

# ----- Environnement virtuel Python (local a l'environnement) -----
if [ "$SANDBOX" = true ]; then
    VENV="/opt/venv_forensics"
else
    VENV="$ROOT/.venv_forensics"
fi
PY="$VENV/bin/python"

if [ ! -x "$PY" ] || ! "$PY" -m pip --version >/dev/null 2>&1; then
    echo "[*] (Re)Création de l'environnement virtuel Python ($VENV)..."
    rm -rf "$VENV"
    python3 -m venv "$VENV"

    echo "[*] Installation des librairies d'analyse..."
    "$PY" -m pip install --upgrade pip -q
    "$PY" -m pip install -q mvt pyAesCrypt xhtml2pdf rich questionary customtkinter
fi

# ----- Bases IOC (personnelles + sources externes) -----
mkdir -p "$ROOT/mvt_iocs"

IOC_STALE=true
if [ -d "$ROOT/mvt_iocs" ] && [ "$(ls -A "$ROOT/mvt_iocs" 2>/dev/null)" ]; then
    NEWEST_IOC=$(find "$ROOT/mvt_iocs" -type f -name '*.stix2' -printf '%T@\n' 2>/dev/null | sort -rn | head -1)
    if [ -n "$NEWEST_IOC" ]; then
        AGE_HOURS=$(( ($(date +%s) - ${NEWEST_IOC%.*}) / 3600 ))
        if [ "$AGE_HOURS" -lt 168 ]; then
            IOC_STALE=false
            echo "[*] Bases IOC déjà à jour (${AGE_HOURS}h). Mise à jour ignorée."
        fi
    fi
fi

if [ "$IOC_STALE" = true ]; then
    echo "[*] Construction des bases IOC (personnelles + sources externes)..."
    "$PY" "$ROOT/scripts/build_iocs.py"
fi

if [ "$UI" = "gui" ] && ! "$PY" -m pip show customtkinter >/dev/null 2>&1; then
    echo "[*] Installation de customtkinter..."
    "$PY" -m pip install -q customtkinter
fi

sudo systemctl restart usbmuxd 2>/dev/null || true

# En Sandbox sans terminal (provision Vagrant) : pré-configuration uniquement.
if [ "$SANDBOX" = true ] && [ ! -t 1 ]; then
    echo "[+] Pré-configuration de la VM terminée."
    exit 0
fi

# En sandbox, on empêche l'hôte de se mettre en veille pendant l'analyse
# (VirtualBox suspendrait la VM et couperait la connexion ssh sinon).
INHIBIT_PREFIX=""
if [ "$MODE" = "sandbox" ] && command -v systemd-inhibit >/dev/null 2>&1; then
    INHIBIT_PREFIX="systemd-inhibit --what=sleep "
fi

if [ "$UI" = "cli" ]; then
    echo "[*] Démarrage de l'outil d'analyse..."
    if [ "$MODE" = "sandbox" ]; then
        # Mode sandbox : interface sur l'hôte, élevation dans la VM (vagrant ssh).
        PATH="$VENV/bin:$PATH" $INHIBIT_PREFIX "$PY" "$ROOT/main.py" --mode "$MODE"
    else
        sudo PATH="$VENV/bin:$PATH" "$PY" "$ROOT/main.py" --mode "$MODE"
    fi
else
    echo "[*] Démarrage de l'interface graphique..."
    if [ "$MODE" = "sandbox" ]; then
        PATH="$VENV/bin:$PATH" $INHIBIT_PREFIX "$PY" "$ROOT/gui.py" --mode "$MODE"
    else
        sudo PATH="$VENV/bin:$PATH" "$PY" "$ROOT/gui.py" --mode "$MODE"
    fi
fi