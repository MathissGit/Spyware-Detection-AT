#!/bin/bash
set -e

# Verifie et met a jour les bases IOC (ioc_personal.json + ioc_sources.json).
# Wrapper user-friendly autour de scripts/build_iocs.py.
#
# Usage :
#   scripts/update_iocs.sh              # verifie l'etat (check), aucun acces reseau
#   scripts/update_iocs.sh update       # reconstruit les bases (depuis tous les IoC
#                                       #   sources, y compris distantes)
#   scripts/update_iocs.sh --force      # force la mise a jour meme si < 7 jours
#   scripts/update_iocs.sh check        # alias de la commande par defaut
#
# Code retour : 0 si les bases sont / deviennent a jour, 1 sinon (erreur ou
#   peremption constatee mais non corrigee).
#
# Le declenchement automatique (a 7 jours) reste assure par launch.sh / setup.sh ;
# ce script sert de declencheur manuel explicite.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv_forensics/bin/python"
BUILD="$ROOT/scripts/build_iocs.py"

MODE="${1:-check}"
FORCE=false
if [ "$MODE" = "--force" ]; then
    MODE="update"
    FORCE=true
fi

if [ ! -x "$PY" ]; then
    echo "[!] Environnement virtuel introuvable : $ROOT/.venv_forensics"
    echo "    Lancez d'abord : sudo ./setup.sh"
    exit 1
fi

case "$MODE" in
    check)
        echo "==> Vérification des bases IOC (inspection locale)..."
        "$PY" "$BUILD" check
        exit $?
        ;;
    update)
        if [ "$FORCE" = false ]; then
            # Si les bases sont deja a jour, on ne retravaille pas sans demande.
            if "$PY" "$BUILD" check >/dev/null 2>&1; then
                echo "[*] Bases IOC déjà à jour. Utilisez 'update --force' pour forcer."
                exit 0
            fi
        else
            echo "[*] Mise à jour forcée des bases IOC."
        fi
        echo "==> Mise à jour des bases IOC (téléchargement + régénération)..."
        "$PY" "$BUILD" update
        exit $?
        ;;
    *)
        echo "Usage: $0 [check|update|--force]" >&2
        exit 2
        ;;
esac
