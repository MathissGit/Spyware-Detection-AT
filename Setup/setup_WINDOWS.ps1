# ====================================================================
# SCRIPT D'INSTALLATION FORENSIQUE POUR WINDOWS
# Doit être exécuté en tant qu'Administrateur
# ====================================================================

if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[!] ERREUR : Vous devez lancer ce script en tant qu'Administrateur." -ForegroundColor Red
    Write-Host "Faites un clic droit sur ce fichier -> 'Exécuter avec PowerShell'." -ForegroundColor Yellow
    Pause
    exit
}

Set-Location $PSScriptRoot\..

Write-Host "[*] Vérification de l'hôte Windows..." -ForegroundColor Cyan

$RequiresReboot = $false

if (-Not (Get-Command vagrant -ErrorAction SilentlyContinue)) {
    Write-Host "[*] Installation de Vagrant via Winget..."
    winget install Hashicorp.Vagrant --accept-source-agreements --accept-package-agreements --silent
    $RequiresReboot = $true
} else {
    Write-Host "[+] Vagrant déjà installé." -ForegroundColor Green
}

$vboxManage = "${env:ProgramFiles}\Oracle\VirtualBox\VBoxManage.exe"
if (-Not (Test-Path $vboxManage)) {
    $VBOX_VER = "7.0.20"
    $VBOX_BUILD = "163906"
    
    Write-Host "[*] Téléchargement de VirtualBox $VBOX_VER..."
    $vboxExe = "$env:TEMP\vbox.exe"
    $extPack = "$env:TEMP\extpack.vbox-extpack"
    
    Invoke-WebRequest -Uri "https://download.virtualbox.org/virtualbox/$VBOX_VER/VirtualBox-$VBOX_VER-$VBOX_BUILD-Win.exe" -OutFile $vboxExe
    Invoke-WebRequest -Uri "https://download.virtualbox.org/virtualbox/$VBOX_VER/Oracle_VM_VirtualBox_Extension_Pack-$VBOX_VER.vbox-extpack" -OutFile $extPack
    
    Write-Host "[*] Installation de VirtualBox (Patientez quelques minutes)..."
    Start-Process -FilePath $vboxExe -ArgumentList "--silent", "--ignore-reboot" -Wait
    
    if (Test-Path $vboxManage) {
        Write-Host "[*] Installation de l'Extension Pack (Support USB)..."
        & $vboxManage extpack install --replace --accept-license=33d72d096685826d70eb6d8ed4a781af4657159f8ed53412a8b3017a5ea2f37c $extPack | Out-Null
        $RequiresReboot = $true
    } else {
        Write-Host "[!] L'installation de VirtualBox a échoué." -ForegroundColor Red
        exit
    }
    
    Remove-Item $vboxExe -ErrorAction SilentlyContinue
    Remove-Item $extPack -ErrorAction SilentlyContinue
} else {
    Write-Host "[+] VirtualBox est déjà installé." -ForegroundColor Green
}

Write-Host "[*] Vérification des conflits d'hyperviseur (Hyper-V)..."
$hyperv = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -ErrorAction SilentlyContinue
if ($hyperv.State -eq 'Enabled') {
    Write-Host "`n[!] AVERTISSEMENT : Hyper-V est activé sur votre ordinateur." -ForegroundColor Yellow
    Write-Host "[!] Sur Windows, Hyper-V bloque souvent la capture des téléphones USB par VirtualBox." -ForegroundColor Yellow
    Write-Host "[!] Si le téléphone n'est pas détecté dans la VM, ouvrez un terminal Administrateur et désactivez Hyper-V avec cette commande :" -ForegroundColor Yellow
    Write-Host "    Disable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All`n" -ForegroundColor White
}

Write-Host "[*] Génération du script de lancement sécurisé..."

$ps1Content = @'
$ErrorActionPreference = "Stop"
$env:VAGRANT_DEFAULT_PROVIDER="virtualbox"
$SNAPSHOT_NAME="VM_clean"

function Cleanup {
    Write-Host "`n[*] Clôture de la session. Sécurisation et extinction de la VM..." -ForegroundColor Yellow
    $vboxManage = "${env:ProgramFiles}\Oracle\VirtualBox\VBoxManage.exe"
    
    $snapshots = vagrant snapshot list 2>&1
    if ($snapshots -match $SNAPSHOT_NAME) {
        vagrant snapshot restore $SNAPSHOT_NAME *>$null
    }
    vagrant halt -f *>$null
    
    Stop-Process -Name adb -Force -ErrorAction SilentlyContinue
    Write-Host "[+] Sandbox immaculée et éteinte. Vos données sont en sécurité." -ForegroundColor Green
}

try {
    Write-Host "[*] ===================================================" -ForegroundColor Cyan
    Write-Host "[*] Lancement de l'environnement Forensique Sécurisé" -ForegroundColor Cyan
    Write-Host "[*] ===================================================" -ForegroundColor Cyan

    $vboxManage = "${env:ProgramFiles}\Oracle\VirtualBox\VBoxManage.exe"
    if (Test-Path ".vagrant\machines\default\virtualbox\id") {
        & $vboxManage unregistervm "sandbox_forensic_light" --delete *>$null 2>&1
    }

    Write-Host "[*] Vérification et démarrage de la Sandbox..."
    vagrant up

    $snapshots = vagrant snapshot list 2>&1
    if ($snapshots -notmatch $SNAPSHOT_NAME) {
        Write-Host "[*] 1er lancement détecté. Création du Snapshot (Image figée)..."
        vagrant snapshot save $SNAPSHOT_NAME
    } else {
        Write-Host "[*] Restauration préventive de la VM à son état vierge..."
        vagrant snapshot restore $SNAPSHOT_NAME
    }

    Write-Host "[+] Environnement isolé prêt et sécurisé." -ForegroundColor Green
    
    Write-Host "[*] Branchez le téléphone suspect par USB maintenant."
    Write-Host "[>] Appuyez sur Entrée quand le téléphone est branché (Extinction auto dans 15 min)... " -NoNewline

    $timeout = 900
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $key = $null
    while ($stopwatch.Elapsed.TotalSeconds -lt $timeout) {
        if ([console]::KeyAvailable) {
            $key = [console]::ReadKey($true)
            if ($key.Key -eq [ConsoleKey]::Enter) { break }
        }
        Start-Sleep -Milliseconds 100
    }

    if ($null -eq $key -or $key.Key -ne [ConsoleKey]::Enter) {
        Write-Host "`n[!] Délai d'inactivité dépassé. Arrêt de sécurité du système." -ForegroundColor Red
        exit
    }

    Write-Host "`n[*] Libération du port USB sur l'hôte physique..."
    Stop-Process -Name adb -Force -ErrorAction SilentlyContinue

    Write-Host "[*] Entrée dans la Sandbox..."
    vagrant ssh -c "cd /vagrant && ./sandbox_env.sh"

} finally {
    Cleanup
}
'@

Set-Content -Path "start_analysis.ps1" -Value $ps1Content -Encoding UTF8

$batContent = @'
@echo off
TITLE Analyse Forensique
cd /d "%~dp0"
echo [*] Demarrage de l'environnement...
powershell.exe -ExecutionPolicy Bypass -File "start_analysis.ps1"
pause
'@
Set-Content -Path "start_analysis.bat" -Value $batContent -Encoding Default

Write-Host "[+] 'start_analysis.bat' généré avec succès à la racine." -ForegroundColor Green

if ($RequiresReboot) {
    Write-Host "`n[!] Redémarrage système requis pour finaliser l'installation des pilotes USB." -ForegroundColor Red
    Write-Host "[>] Appuyez sur Entrée pour redémarrer l'ordinateur immédiatement..." -ForegroundColor Yellow
    Read-Host
    Restart-Computer -Force
} else {
    Write-Host "`n[+] Environnement hôte prêt. Pour lancer l'outil par la suite, double-cliquez simplement sur 'start_analysis.bat'." -ForegroundColor Green
    Pause
}