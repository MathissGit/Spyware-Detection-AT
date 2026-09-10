#!/bin/bash
# Tests d'intégration réels (Android/iOS) : à exécuter sur un poste
# possédant les appareils branchés. Sans appareil, les tests sont
# auto-skip (voir TEST_STRATEGY.md) — ceci n'est pas une désélection.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY=""
for VENV in "$ROOT/.venv_tests" "$ROOT/.venv_forensics"; do
    if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "import pytest" >/dev/null 2>&1; then
        PY="$VENV/bin/python"
        break
    fi
done
[ -n "$PY" ] || PY="python3"

exec "$PY" -m pytest tests/ -m "real_android or real_ios" \
    --no-header -q -p no:cacheprovider