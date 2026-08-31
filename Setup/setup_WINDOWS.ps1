
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[!] ERREUR : Vous devez lancer ce script en tant qu'Administrateur." -ForegroundColor Red
    Write-Host "Faites un clic droit sur ce fichier -> 'Exécuter avec PowerShell'." -ForegroundColor Yellow
    Pause
    exit
}

Set-Location $PSScriptRoot\..

Write-Host "[*] ===================================================" -ForegroundColor Cyan
Write-Host "[*]   Installation du Spyware Detection Automated Tool" -ForegroundColor Cyan
Write-Host "[*] ===================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[*] Choisissez le mode d'installation :" -ForegroundColor Yellow
Write-Host "  1) Sandbox (VM VirtualBox) - Recommande pour l'analyse d'appareils suspects"
Write-Host "  2) Mode direct             - Installation locale plus rapide, sans isolation"
Write-Host ""
$modeChoice = Read-Host "[>] Votre choix (1 ou 2)"

if ($modeChoice -eq "2") {
    $mode = "direct"
    Write-Host "[*] Mode direct sélectionné." -ForegroundColor Green
} else {
    $mode = "sandbox"
    Write-Host "[*] Mode sandbox sélectionné." -ForegroundColor Green
}

$RequiresReboot = $false

if ($mode -eq "sandbox") {
    Write-Host "[*] Vérification de l'hôte..." -ForegroundColor Cyan

    if (-Not (Get-Command vagrant -ErrorAction SilentlyContinue)) {
        Write-Host "[*] Installation de Vagrant..."
        winget install Hashicorp.Vagrant --accept-source-agreements --accept-package-agreements --silent
        $RequiresReboot = $true
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

        Write-Host "[*] Installation de VirtualBox..."
        Start-Process -FilePath $vboxExe -ArgumentList "--silent", "--ignore-reboot" -Wait

        if (Test-Path $vboxManage) {
            Write-Host "[*] Installation de l'Extension Pack..."
            & $vboxManage extpack install --replace --accept-license=33d72d096685826d70eb6d8ed4a781af4657159f8ed53412a8b3017a5ea2f37c $extPack | Out-Null
            $RequiresReboot = $true
        } else {
            Write-Host "[!] L'installation de VirtualBox a échoué." -ForegroundColor Red
            exit
        }

        Remove-Item $vboxExe -ErrorAction SilentlyContinue
        Remove-Item $extPack -ErrorAction SilentlyContinue
    }

    Write-Host "[*] Vérification des conflits d'Hyper-V..."
    $hyperv = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -ErrorAction SilentlyContinue
    if ($hyperv.State -eq 'Enabled') {
        Write-Host "`n[!] AVERTISSEMENT : Hyper-V est activé sur votre ordinateur." -ForegroundColor Yellow
        Write-Host "[!] Sur Windows, Hyper-V bloque souvent la capture des téléphones USB par VirtualBox." -ForegroundColor Yellow
        Write-Host "[!] Si le téléphone n'est pas détecté dans la VM, ouvrez un terminal Administrateur et désactivez Hyper-V avec cette commande :" -ForegroundColor Yellow
        Write-Host "    Disable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All`n" -ForegroundColor White
    }

    $VMName = "sandbox_forensics"
    $VMExists = $false
    if (Test-Path $vboxManage) {
        $vmList = & $vboxManage list vms 2>&1
        if ($vmList -match "`"$VMName`"") {
            $VMExists = $true
        }
    }

    if ($VMExists) {
        Write-Host ""
        Write-Host "[!] Une VM '$VMName' existe déjà sur cette machine." -ForegroundColor Yellow
        Write-Host "    Réutiliser la VM existante peut causer des problèmes de performance" -ForegroundColor Yellow
        Write-Host "    ou des conflits lors de l'analyse." -ForegroundColor Yellow
        Write-Host ""
        $reinstall = Read-Host "[>] Voulez-vous détruire la VM et tout réinstaller proprement ? (O/n)"
        if ([string]::IsNullOrEmpty($reinstall)) { $reinstall = "O" }

        if ($reinstall -eq "O" -or $reinstall -eq "o") {
            Write-Host "[*] Arrêt et suppression de la VM existante..." -ForegroundColor Cyan
            vagrant destroy -f 2>$null
            & $vboxManage unregistervm $VMName --delete 2>$null
            Remove-Item -Recurse -Force ".vagrant" -ErrorAction SilentlyContinue

            Write-Host "[*] Nettoyage de l'environnement Python..." -ForegroundColor Cyan
            Remove-Item -Recurse -Force ".venv_forensics" -ErrorAction SilentlyContinue

            Write-Host "[+] VM supprimée. Réinstallation propre." -ForegroundColor Green
        } else {
            Write-Host "[*] Conservation de la VM existante." -ForegroundColor Yellow
        }
    }

    Write-Host "[*] Génération du script de lancement start_analysis..." -ForegroundColor Cyan

    $ps1Content = @'
$ErrorActionPreference = "Stop"
$env:VAGRANT_DEFAULT_PROVIDER="virtualbox"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Cleanup {
    Write-Host "`n[*] Nettoyage de la VM..." -ForegroundColor Yellow
    vagrant destroy -f *>$null
    Stop-Process -Name adb -Force -ErrorAction SilentlyContinue
}

try {
    Write-Host "[*] ===================================================" -ForegroundColor Cyan
    Write-Host "[*] Lancement de l'environnement d'analyse" -ForegroundColor Cyan
    Write-Host "[*] ===================================================" -ForegroundColor Cyan

    $iocDir = Join-Path $ScriptDir "mvt_iocs"
    if (-Not (Test-Path $iocDir)) { New-Item -ItemType Directory -Path $iocDir -Force | Out-Null }

    $iocStale = $true
    $iocFiles = Get-ChildItem -Path $iocDir -File -ErrorAction SilentlyContinue
    if ($iocFiles.Count -gt 0) {
        $newest = ($iocFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
        $ageHours = [math]::Floor(((Get-Date) - $newest).TotalHours)
        if ($ageHours -lt 168) {
            $iocStale = $false
            Write-Host "[*] Bases IOC déjà à jour (${ageHours}h)." -ForegroundColor Green
        }
    }

    if ($iocStale) {
        Write-Host "[*] Téléchargement des bases IOC sur l'hôte..." -ForegroundColor Cyan
        $venvPath = Join-Path $ScriptDir ".venv_forensics"
        if (-Not (Test-Path $venvPath)) {
            python3 -m venv $venvPath
            & "$venvPath\Scripts\pip.exe" install -q mvt
        }
        $mvtIos = Join-Path $venvPath "Scripts\mvt-ios.exe"
        $mvtAndroid = Join-Path $venvPath "Scripts\mvt-android.exe"
        Start-Process -FilePath $mvtIos -ArgumentList "download-iocs", "-f", $iocDir -NoNewWindow -Wait
        Start-Process -FilePath $mvtAndroid -ArgumentList "download-iocs", "-f", $iocDir -NoNewWindow -Wait
        Write-Host "[+] Bases IOC téléchargées." -ForegroundColor Green
    }

    Write-Host "[*] Démarrage de la Sandbox..."
    vagrant up

    Write-Host "[+] Environnement isolé prêt et sécurisé." -ForegroundColor Green

    Write-Host "[*] Branchez le téléphone par USB maintenant."
    Write-Host "[>] Appuyez sur Entrée quand le téléphone est branché... " -NoNewline

    $timeout = 500
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
        Write-Host "`n[!] Délai d'inactivité dépassé. Arrêt du système." -ForegroundColor Red
        exit
    }

    Write-Host "`n[*] Libération du port USB sur l'hôte physique..."
    Stop-Process -Name adb -Force -ErrorAction SilentlyContinue
    vagrant ssh -c "cd /vagrant && ./sandbox_env.sh"

} finally {
    Cleanup
}
'@

    Set-Content -Path "start_analysis.ps1" -Value $ps1Content -Encoding UTF8

} else {
    Write-Host "[*] Installation en mode direct..." -ForegroundColor Cyan

    Write-Host "[*] Vérification de Python3..."
    if (-Not (Get-Command python3 -ErrorAction SilentlyContinue)) {
        Write-Host "[*] Installation de Python3..."
        winget install Python.Python.3.11 --accept-source-agreements --accept-package-agreements --silent
    }

    Write-Host "[*] Vérification de ADB..."
    if (-Not (Get-Command adb -ErrorAction SilentlyContinue)) {
        Write-Host "[*] Téléchargement de Android Platform Tools..."
        $adbZip = "$env:TEMP\platform-tools.zip"
        $adbDir = "$env:LOCALAPPDATA\Android\Sdk\platform-tools"
        Invoke-WebRequest -Uri "https://dl.google.com/android/repository/platform-tools-latest-windows.zip" -OutFile $adbZip
        Expand-Archive -Path $adbZip -DestinationPath "$env:LOCALAPPDATA\Android\Sdk" -Force
        Remove-Item $adbZip -ErrorAction SilentlyContinue
        $env:PATH = "$adbDir;$env:PATH"
        [Environment]::SetEnvironmentVariable("PATH", "$adbDir;$([Environment]::GetEnvironmentVariable('PATH', 'User'))", 'User')
    }

    Write-Host "[*] Génération du script de lancement start_analysis..." -ForegroundColor Cyan

    $ps1Content = @'
$ErrorActionPreference = "Stop"

Write-Host "[*] ===================================================" -ForegroundColor Cyan
Write-Host "[*] Lancement de l'environnement d'analyse" -ForegroundColor Cyan
Write-Host "[*] ===================================================" -ForegroundColor Cyan
Write-Host "[*] Branchez le téléphone par USB maintenant."
Write-Host "[>] Appuyez sur Entrée quand le téléphone est branché... " -NoNewline

$timeout = 500
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
    Write-Host "`n[!] Délai d'inactivité dépassé." -ForegroundColor Red
    exit
}

Stop-Process -Name adb -Force -ErrorAction SilentlyContinue

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$scriptDir\direct_env.sh"
'@

    Set-Content -Path "start_analysis.ps1" -Value $ps1Content -Encoding UTF8

}

$batContent = @'
@echo off
TITLE Analyse Forensique
cd /d "%~dp0"
echo [*] Demarrage de l'environnement...
powershell.exe -ExecutionPolicy Bypass -File "start_analysis.ps1"
pause
'@
Set-Content -Path "start_analysis.bat" -Value $batContent -Encoding Default

Write-Host "[+] 'start_analysis.bat' généré avec succès." -ForegroundColor Green

if ($RequiresReboot) {
    Write-Host "`n[!] Redémarrage système requis pour finaliser l'installation." -ForegroundColor Red
    Write-Host "[>] Appuyez sur Entrée pour redémarrer l'ordinateur immédiatement..." -ForegroundColor Yellow
    Read-Host
    Restart-Computer -Force
} else {
    Write-Host "`n[+] Environnement prêt. Pour lancer l'outil par la suite, double-cliquez simplement sur 'start_analysis.bat'." -ForegroundColor Green
    Pause
}
