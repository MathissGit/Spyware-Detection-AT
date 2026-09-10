#!/bin/bash
# Lance la suite de tests complète (3 niveaux) avec couverture obligatoire à 100 %.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY=""
for VENV in "$ROOT/.venv_tests" "$ROOT/.venv_forensics"; do
    if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "import pytest, pytest_cov" >/dev/null 2>&1; then
        PY="$VENV/bin/python"
        break
    fi
done
if [ -z "$PY" ]; then
    PY="python3"
fi

echo "[*] Python : $PY"

# En environnement graphique absent, xvfb-run est nécessaire pour les tests GUI.
RUNNER=()
if [ -n "${DISPLAY:-}" ]; then
    :
elif command -v xvfb-run >/dev/null 2>&1; then
    RUNNER=(xvfb-run -a)
fi

exec "${RUNNER[@]}" "$PY" -m pytest tests/ \
    --cov=main --cov=gui --cov=scripts \
    --cov-report=term-missing --cov-fail-under=100 \
    -q -p no:cacheprovider