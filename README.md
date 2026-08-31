# Spyware Detection Automated Tool

Un outil d'automatisation d'extraction forensique et d'analyse de compromission (Spyware) pour smartphones **Android** et **iOS**.

Ce projet est un outil d'investigation numerique (DFIR) concu pour automatiser l'extraction et l'analyse de smartphones (iOS & Android) suspectes d'etre compromis par des logiciels espions. Ce projet s'appuie sur le [Mobile Verification Toolkit (MVT)](https://github.com/mvt-project/mvt) d'Amnesty International et sur [AndroidQF](https://github.com/mvt-project/androidqf).
Il automatise de bout en bout l'extraction, l'analyse des indicateurs de compromission (IOCs), la generation de rapports (HTML/PDF) et la securisation des donnees extraites via un chiffrement AES-256.

Afin de proteger la machine de l'analyste contre les attaques physiques, de type BadUSB ou les rebonds de malwares, l'outil s'execute integralement dans une machine virtuelle ephemere (sandboxing) pilotee automatiquement par Vagrant.

## Fonctionnalites

* **Support Multi-OS :** Fonctionne sur Linux, macOS et Windows (via virtualisation de l'outil).
* **Multi-Appareils :** Prise en charge d'Android (via `AndroidQF`) et iOS (via `idevicebackup2`).
* **IOC :** Bases de menaces connues.
* **Generation de Rapports :** Synthese automatique des alertes en formats HTML et PDF.
* **Securite de stockage :** Chiffrement AES-256 de l'archive de l'appareil.
* **Isolation Python :** Environnement virtuel Python (`.venv_forensics`).
* **Sandboxing Ephemere :** La VM Debian 12 utilise un snapshot propre, restaure a chaque session.

## Pre-requis

**Systeme :**
- Linux, macOS ou Windows
- Python 3.10+

**Mode Sandbox (recommande) :**
- [VirtualBox](https://www.virtualbox.org/) 7.0+
- [Vagrant](https://www.vagrantup.com/) 2.4+

**Mode Direct :**
- `python3`, `pip`, `adb` (Android Debug Bridge)
- `libimobiledevice-utils` et `usbmuxd`

## Contenu du Depot

```plaintext
Spyware-Detection-AT/
├── androidqf_linux_amd64_*   # Binaire AndroidQF (a telecharger)
├── Setup/
│   ├── setup_LINUX-MACOS.sh  # Script d'installation hote (Linux/macOS)
│   └── setup_WINDOWS.ps1     # Script d'installation hote (Windows)
├── main.py                   # Script principal (extraction, analyse, chiffrement)
├── Vagrantfile               # Configuration de la VM Debian 12 ephemere
├── sandbox_env.sh            # Script interne a la VM (mode sandbox)
├── direct_env.sh             # Script d'execution en mode direct (sans VM)
├── mvt_iocs/                 # Bases de menaces IOC (miroir partage hote/VM)
├── results/                  # Repertoire de sortie des dumps et rapports
│   └── Dump_[IMEI]_[DATE]/
│       ├── Dump_...tar.gz.aes
│       ├── Report_...html
│       └── Report_...pdf
├── .venv_forensics/          # Environnement virtuel Python (auto-gere)
└── README.md
```

> [!WARNING]
> **Binaire AndroidQF :** Le binaire `androidqf_linux_amd64_*` **doit etre telecharge manuellement** depuis les [Releases officielles](https://github.com/mvt-project/androidqf/releases). Telechargez la version **LINUX** meme si vous etes sous Windows ou macOS. Placez-le a la racine et rendez-le executable : `chmod +x androidqf_*`. Voir à l'étape 2 de l'installation.

## Installation

### Etape 1 : Cloner le depot
```bash
git clone https://github.com/MathissGit/Spyware-Detection-AT
cd Spyware-Detection-AT
```

### Etape 2 : Telecharger AndroidQF
- Rendez-vous sur la page des [Releases d'AndroidQF](https://github.com/mvt-project/androidqf/releases).
- **[!!!]** Telechargez la version **LINUX** (*exemple : `androidqf_v1.8.3_linux_amd64`*), MEME SI vous etes sous Windows ou macOS.
- Placez le fichier a la racine du dossier clone et rendez-le executable : `chmod +x androidqf_*`

### Etape 3 : Configurer la machine Hote
*A ne faire qu'une seule fois.*

| Mode | Description | Securite | Vitesse |
|------|-------------|----------|---------|
| **Sandbox (VM)** | Execution dans une VM VirtualBox Debian 12 | Maximale (isolation totale) | Plus lent (demarrage VM) |
| **Mode direct** | Installation locale directement sur l'hote | Standard | Rapide (pas de VM) |

**Linux / macOS :**
```bash
chmod +x Setup/setup_LINUX-MACOS.sh
sudo ./Setup/setup_LINUX-MACOS.sh
```

**Windows :** Clic droit sur `setup_WINDOWS.ps1` > **Executer avec PowerShell**.

> [!NOTE]
> Le script `start_analysis.sh` (ou `.bat` sous Windows) apparait automatiquement a la racine. Un redemarrage peut etre requis (sandbox uniquement).

## Preparation des Appareils Cibles

### Android
1. **Parametres > A propos du telephone** > Tapotez 7 fois sur **Numero de build**
2. **Systeme > Options pour les developpeurs** > Activez le **Debogage USB**
3. Acceptez **"Faire confiance a cet ordinateur"** et entrez le PIN

### iOS (iPhone/iPad)
1. Verifiez que le **Lockdown Mode** est desactive
2. Deverrouillez l'appareil, branchez-le, acceptez la confiance, entrez le PIN

## Utilisation

> [!WARNING]
> Ne lancez jamais `main.py` directement. Utilisez toujours `start_analysis.sh` ou `start_analysis.bat`.

**Linux / macOS :** `./start_analysis.sh`

**Windows :** Double-cliquez sur `start_analysis.bat`

## Resultats de sortie

```
Dump_[IMEI]_[DATE]/
├── Dump_[IMEI]_[DATE].tar.gz.aes   # Archive chiffree AES-256
├── Report_[IMEI]_[DATE].html       # Rapport d'analyse HTML
└── Report_[IMEI]_[DATE].pdf        # Rapport d'analyse PDF
```

### Comment dechiffrer l'archive ?

**Linux / macOS :**
```bash
python3 -m venv .venv_decrypt
source .venv_decrypt/bin/activate
pip install pyAesCrypt
pyAesCrypt -d ./results/Dump_XXXX/Dump_XXXX.tar.gz.aes ./results/Dump_XXXX/DUMP_CLAIR.tar.gz
deactivate
```

**Windows :**
```bash
python -m venv .venv_decrypt
.venv_decrypt\Scripts\activate.bat
pip install pyAesCrypt
pyAesCrypt -d C:\chemin\vers\Dump_XXXX.tar.gz.aes C:\chemin\vers\DUMP_CLAIR.tar.gz
.venv_decrypt\Scripts\deactivate.bat
```

**Script Python :**
```python
import pyAesCrypt
pyAesCrypt.decryptFile("Dump_XXXX.tar.gz.aes", "DUMP_CLAIR.tar.gz", "VOTRE_MDP", 8 * 1024 * 1024)
```

**Extraction :**
```bash
tar -xzf DUMP_CLAIR.tar.gz
```

## Architecture des IOC

Les bases IOC sont téléchargées **une seule fois** sur l'hôte dans `mvt_iocs/` et partagées avec la VM via le dossier monté Vagrant (`/vagrant/`).

```plaintext
Hote (start_analysis.sh)                    VM (sandbox_env.sh)
┌─────────────────────┐                       ┌──────────────────────┐
│  mvt_iocs/          │  ← montage Vagrant →  │  /vagrant/mvt_iocs/  │
│  (téléchargement)   │                       │  (lecture seule)     │
└─────────────────────┘                       └──────────────────────┘
         │                                          │
         ▼                                          ▼
  mvt-ios download-iocs                       mvt-android check-androidqf
  mvt-android download-iocs                   mvt-ios check-backup
```

**Mise à jour des indicateurs :** Les IOC sont considérés comme à jour si le fichier le plus recent à moins de 7 jours (168h). Sinon, un re-téléchargement est déclenche sur l'hote avant le démarrage de la VM.

## Depannage

| Probleme | Solution |
|----------|----------|
| `androidqf introuvable` | Verifiez que le binaire est a la racine et executable (`chmod +x`) |
| Telephone non detect | Debogage USB active + telephone deverrouille |
| `adb: no devices found` | Rebranchez, acceptez la confiance, reessayez |
| Erreur Vagrant/VirtualBox | VirtualBox et Vagrant installes et a jour. Desactivez Hyper-V (Windows) |
| `mvt-android` introuvable | L'environnement virtuel sera recreate automatiquement |
| Delai depasse | Timeout de 500s. Relancez et branchez plus rapidement |

### Reinstallation propre
```bash
rm -rf .venv_forensics/ .vagrant/
vagrant destroy -f 2>/dev/null
./start_analysis.sh
```

## Avertissement Legal & Credits

Cet outil a ete concu **exclusivement** pour l'analyse forensique consensuelle. Il ne doit pas etre utilise pour extraire des donnees d'appareils n'appartenant pas à l'analyste, ou sans le consentement explicite du proprietaire.

Merci a **Amnesty International Security Lab** pour le developpement et la maintenance de MVT et AndroidQF.
