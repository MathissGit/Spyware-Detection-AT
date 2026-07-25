# Spyware Detection Automated Tool
Un outil d'automatisation d'extraction forensique et d'analyse de compromission (Spyware) pour smartphones **Android** et **iOS**. 

Ce projet s'appuie sur le [Mobile Verification Toolkit (MVT)](https://github.com/mvt-project/mvt) d'Amnesty International et sur [AndroidQF](https://github.com/mvt-project/androidqf). Il automatise de bout en bout l'extraction, l'analyse des indicateurs de compromission (IOCs), la génération de rapports lisibles (HTML/PDF) et la sécurisation des données extraites via un chiffrement AES-256.

---
## Fonctionnalités

* **Support Multi-OS :** Fonctionne sur Linux, macOS et Windows.
* **Multi-Appareils :** Prise en charge d'Android (via AndroidQF) et iOS (via `idevicebackup2`).
* **Analyse Automatisée :** Téléchargement des derniers IOCs et scan du dump via MVT.
* **Génération de Rapports :** Synthèse automatique des alertes en formats HTML et PDF.
* **Sécurité intégrée :** Chiffrement AES-256 de l'archive brute et nettoyage sécurisé des données temporaires en clair sur la machine hôte.
* **Isolation Python (Sandboxing) :** Les scripts lanceurs (`.sh` ou `.bat`) créent et gèrent automatiquement un environnement virtuel Python (`venv`) éphémère.

---
## Contenu du Dépôt
* `main.py` : Le script principal en Python contenant la logique d'extraction, d'analyse et de chiffrement.
* `launcher_linux_macos.sh` : Le script de lancement pour Linux et macOS (gère le `venv` et les dépendances).
* `launcher_windows.bat` : Le script de lancement pour Windows.
* `README.md` : Cette documentation.

> [!WARNING] 
> **Outil tiers manquant REQUIS :** Le binaire d'extraction `androidqf` **n'est pas inclus** dans ce dépôt afin de garantir que vous utilisiez toujours la version la plus récente et sécurisée. 
> 
> **Action requise :** Vous devez le télécharger manuellement depuis le dépôt officiel d'Amnesty et le placer dans ce dossier avant de lancer l'outil. (Voir l'étape 2 de l'Installation ci-dessous).

**Exemple d'Arborescence**
```plaintext
/
├── androidqf_*
├── launcher_linux_macos.sh
├── launcher_windows.bat
├── main.py
├── README.md
└── Secure_Mobile_Dumps/
    ├── Dump_2024-03-22_16-30-00/
    │   ├── DUMP_SECURE_...tar.gz.aes
    │   ├── rapport_MVT_...html
    │   └── rapport_MVT_...pdf
    └── Dump_2023-02-15_09-15-00/
        └── ...
```

---
## Prérequis Système
Avant d'utiliser cet outil, votre système hôte doit disposer de quelques paquets de base.

**Linux (Debian / Ubuntu)**
```bash
sudo apt update
sudo apt install python3 python3-venv libimobiledevice-utils
```
**MacOS**
```bash
brew install python libimobiledevice
```
**Windows**
- **Python 3** : À installer depuis le site officiel (cocher "Add Python to PATH" lors de l'installation).
- **iTunes** : Requis pour installer les pilotes de communication avec les appareils iOS.

---
## Installation

**1. Cloner le dépôt :**
```bash
git clone https://github.com/MathissGit/Spyware-Detection-AT
cd Spyware-Detection-AT
```
**2. Télécharger AndroidQF :** 
- Rendez-vous sur la page des [Releases d'AndroidQF](https://github.com/mvt-project/androidqf/releases).
- Téléchargez l'exécutable correspondant à votre OS d'analyse (ex: `androidqf_v1.7.0_linux_amd64` pour Linux).
- Placez ce fichier directement à la racine du dossier cloné. Assurez-vous que l'exécutable `androidqf_*` se trouve bien dans le même dossier que `main.py`.
- _(Linux/macOS)_ Rendre le binaire exécutable : `chmod +x androidqf_*`

---
## Préparation des Appareils Cibles

**Android**
1. Allez dans **Paramètres > À propos du téléphone**.
2. Tapotez 7 fois sur **Numéro de build** pour activer les options pour les développeurs.
3. Allez dans **Système > Options pour les développeurs** et activez le **Débogage USB**.
4. Branchez le téléphone à l'ordinateur et acceptez l'invite de sécurité à l'écran.

**iOS (iPhone/iPad)**
1. Déverrouillez l'appareil et branchez-le à l'ordinateur.
2. Acceptez l'invite **"Faire confiance à cet ordinateur"**.
3. Entrez le code PIN sur l'écran de l'appareil.

---
## Utilisation 
Ne lancez pas le script Python directement. Utilisez le lanceur correspondant à votre OS pour garantir l'isolation des dépendances.

**Linux / macOS :**
```bash
./launcher.sh
```
**Windows :**
```bash
./launcher.bat
```
L'outil vous guidera pour la suite :
1. Choix du type de périphérique (Android ou iOS).
2. Choix du répertoire de destination (Local, Lecteur externe/Clé USB, ou les deux).
3. Configuration d'un mot de passe robuste pour le chiffrement AES-256 de l'archive finale.

---
## Résultats de sortie
Une fois le processus terminé, le dossier de travail est nettoyé. Dans votre dossier de destination (par défaut `~/dumps_securises/`), vous trouverez :
1. **`DUMP_SECURE_[DATE].tar.gz.aes`** : L'archive chiffrée contenant toutes les extractions brutes et les logs détaillés JSON de MVT.
2. **`rapport_MVT_[DATE].html / .pdf`** : Le rapport de synthèse (en clair) résumant les alertes majeures ou malveillantes détectées.
### Comment déchiffrer l'archive ?
Si vous souhaitez exploiter le dump ultérieurement, vous devez utiliser la librairie `pyAesCrypt`. 

Pour conserver l'isolation de votre environnement Python et ne pas installer de paquets globaux, **utilisez l'environnement virtuel (`venv`) créé par le lanceur** lors de votre première exécution :

#### Méthodes 
**Linux / macOS :**
Ouvrez un terminal dans le dossier du projet (`Spyware-Detection-AT`) et exécutez :
```bash
# Activer l'environnement isolé
source .venv_forensics/bin/activate

# Déchiffrer l'archive (remplacez les chemins par les vôtres)
pyAesCrypt -d ./results/Dump_XXXX/DUMP_SECURE_XXXX.tar.gz.aes ./results/Dump_XXXX/DUMP_CLAIR.tar.gz
 
# Quitter proprement l'environnement
deactivate
```

**Windows :**
Ouvrez une invite de commande (`cmd`) dans le dossier du projet (`Spyware-Detection-AT`) et exécutez :
```bash
# Activer l'environnement isolé
.venv_forensics\Scripts\activate.bat

# Déchiffrer l'archive (remplacez les chemins par les vôtres)
pyAesCrypt -d C:\chemin\vers\DUMP_SECURE_XXXX.tar.gz.aes C:\chemin\vers\DUMP_CLAIR.tar.gz

# Quitter proprement l'environnement
.venv_forensics\Scripts\deactivate.bat
```
*Note : Le mot de passe de déchiffrement défini lors de l'extraction vous sera demandé de manière interactive par l'outil.*

**Script Python**
Si vous souhaitez automatiser le déchiffrement dans un autre outil forensique, voici le snippet Python à utiliser (à exécuter dans votre environnement isolé) :

```bash
import pyAesCrypt
# Paramètres (à adapter avec vos noms de fichiers)
fichier_chiffre = "DUMP_SECURE_XXXX.tar.gz.aes"
fichier_clair = "DUMP_CLAIR.tar.gz"
mot_de_passe = "VOTRE_MOT_DE_PASSE"
buffer_size = 8 * 1024 * 1024
# Déchiffrement
pyAesCrypt.decryptFile(fichier_chiffre, fichier_clair, mot_de_passe, buffer_size)
print("Déchiffrement terminé !")
```

#### Étape Finale
**Extraction**
Une fois le fichier `DUMP_CLAIR.tar.gz` obtenu, vous pouvez l'extraire avec n'importe quel gestionnaire d'archives standard (7-Zip, WinRAR) ou directement via la commande :
```bash
tar -xzf DUMP_CLAIR.tar.gz
```

---
## Avertissement Légal & Crédits
Cet outil a été conçu **exclusivement** pour l'analyse forensique consensuelle. Il ne doit pas être utilisé pour extraire des données d'appareils n'appartenant pas à l'analyste, ou sans le consentement explicite du propriétaire de l'appareil.

Merci à **Amnesty International Security Lab** pour le développement et la maintenance de MVT et AndroidQF
