#!/bin/bash
# Installation du hook pre-commit de non-régression.
# À exécuter une fois après le clonage (et à chaque nouveau clone) :
#   ./scripts/setup_hook.sh
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SOURCE="$ROOT/.githooks/pre-commit"
TARGET="$ROOT/.git/hooks/pre-commit"

if [ ! -f "$SOURCE" ]; then
    echo "[!] Hook source introuvable : $SOURCE"
    exit 1
fi

chmod +x "$SOURCE"

mkdir -p "$ROOT/.git/hooks"

if [ -L "$TARGET" ] || [ -f "$TARGET" ]; then
    rm -f "$TARGET"
fi

ln -s "$SOURCE" "$TARGET"

echo "[+] Hook pre-commit installé : $TARGET"
echo "[+] Les tests de non-régression s'exécuteront à chaque 'git commit'."
