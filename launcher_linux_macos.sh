#!/bin/bash

# Configuration
VENV_DIR=".venv_forensics"
PYTHON_CMD="python3"
SCRIPT_NAME="main.py"

echo "[*] Initializing the isolated environment..."

if [ ! -d "$VENV_DIR" ]; then
    echo "[+] Creating the Virtual Environment ($VENV_DIR)..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo "[+] Installation of Outbuildings..."
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip > /dev/null 2>&1
    pip install pyAesCrypt mvt xhtml2pdf rich questionary > /dev/null 2>&1
    echo "[+] Environment ready !"
else
    source "$VENV_DIR/bin/activate"
fi

python "$SCRIPT_NAME"

deactivate