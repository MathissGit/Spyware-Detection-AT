@echo off
setlocal

set VENV_DIR=.venv_forensics
set PYTHON_CMD=python
set SCRIPT_NAME=main.py

echo [*] Initializing the isolated environment...

REM 
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [+] Creating the Virtual Environment (%VENV_DIR%)...
    %PYTHON_CMD% -m venv %VENV_DIR%
    echo [+] Installation of Outbuildings...
    call "%VENV_DIR%\Scripts\activate.bat"
    python -m pip install --upgrade pip >nul 2>nul
    pip install pyAesCrypt mvt xhtml2pdf rich questionary >nul 2>nul
    echo [+] Environment ready !
) else (
    call "%VENV_DIR%\Scripts\activate.bat"
)

REM 
python %SCRIPT_NAME%

REM 
call "%VENV_DIR%\Scripts\deactivate.bat"
endlocal
pause