# Spyware Detection Automated Tool
Un outil d'automatisation d'extraction forensique et d'analyse de compromission (Spyware) pour smartphones **Android** et **iOS**. 

Ce projet est un outil d'investigation numérique (DFIR) conçu pour automatiser l'extraction et l'analyse de smartphones (iOS & Android) suspectés d'être compromis par des logiciels espions avancés. Ce projet s'appuie sur le [Mobile Verification Toolkit (MVT)](https://github.com/mvt-project/mvt) d'Amnesty International et sur [AndroidQF](https://github.com/mvt-project/androidqf). 
Il automatise de bout en bout l'extraction, l'analyse des indicateurs de compromission (IOCs), la génération de rapports (HTML/PDF) et la sécurisation des données extraites via un chiffrement AES-256.

Afin de protéger la machine de l'analyste contre les attaques physiques, de type BadUSB ou les rebonds de malwares, l'outil s'exécute intégralement dans une machine virtuelle éphémère (sandboxing) pilotée automatiquement par Vagrant.

## Fonctionnalités

* **Support Multi-OS :** Fonctionne sur Linux, macOS et Windows (via virtualisation de l'outil).
* **Multi-Appareils :** Prise en charge d'Android (via `AndroidQF`) et iOS (via `idevicebackup2`).
* **Analyse Asynchrone :** Téléchargement et mise à jour des derniers IOCs.
* **Génération de Rapports :** Synthèse automatique des alertes en formats HTML et PDF.
* **Sécurité de stockage :** Chiffrement AES-256 de l'archive brute. L'outil purge systématiquement et irrémédiablement les répertoires d'extraction temporaires. Seule l'archive chiffrée finale est sauvegardée dans le répertoire centralisé results/ (en local ou externe).
* **Isolation Python :** Le script interne configure et gère automatiquement un environnement virtuel Python (.venv_forensics).
* **Sandboxing Éphémère :** L'analyse s'exécute dans une VM Debian 12 à partir d'un snapshot propre, un systeme de sécurité coupe la machine en cas de crash.

## Contenu du Dépôt
* **`Setup/`** : Dossier contenant les scripts de configuration initiale de l'hôte (`setup_LINUX-MACOS.sh` et `setup_WINDOWS.ps1`).
* **`main.py`** : Le script principal en Python contenant la logique d'extraction, d'analyse et de chiffrement.
* **`Vagrantfile`** : La configuration d'infrastructure pour la machine virtuelle Debian 12 éphémaire.
* **`sandbox_env.sh`** : Script interne à la VM (Met à jour les dépendances, charge les IoC et lance l'environnement Python).
* **`README.md`** : Cette documentation.

> [!WARNING] 
> **Outil tiers manquant REQUIS :** Le binaire d'extraction `androidqf` **n'est pas inclus** dans ce dépôt afin de garantir que vous utilisiez toujours la version la plus récente et sécurisée. 
> 
> **Action requise :** Vous devez le télécharger manuellement depuis le dépôt officiel d'Amnesty et le placer dans ce dossier avant de lancer l'outil. (Voir l'étape 2 de l'Installation ci-dessous).

**Exemple d'Arborescence**
```plaintext
/
├── androidqf_*
├── Setup/
│   ├── setup_LINUX-MACOS.sh 
│   └── setup_WINDOWS.ps1
├── main.py
├── sandbox_env.sh
├── Vagrantfile
└── README.md
└── results/
    ├── Dump_[IMEI]_2024-03-22_16-30-00/
    │   ├── Dump_[IMEI]_...tar.gz.aes
    │   ├── Report_[IMEI]_...html
        └── Report_[IMEI]_...pdf
    └── Dump_[IMEI]_2023-02-15_09-15-00/
        └── ...
```

## Installation

**1. Cloner le dépôt :**
```bash
git clone https://github.com/MathissGit/Spyware-Detection-AT
cd Spyware-Detection-AT
```
**2. Télécharger AndroidQF :** 
- Rendez-vous sur la page des [Releases d'AndroidQF](https://github.com/mvt-project/androidqf/releases).
- [!!!] **Téléchargez la version LINUX** (*exemple: `androidqf_v1.7.0_linux_amd64`*), MÊME SI vous êtes sous Windows ou macOS (l'outil s'exécutera à l'intérieur d'une Sandbox Linux Debian).
- Placez ce fichier à la racine du dossier cloné. Assurez-vous que l'exécutable `androidqf_*` se trouve bien dans le même dossier que `main.py`.
- _(Linux/macOS)_ Rendre le binaire exécutable : `chmod +x androidqf_*`

**3. Configurer la machine Hôte :** 
- *À ne faire qu'une seule fois pour installer les hyperviseurs et générer le script de lancement.*
- L'outil vous proposera de redémarrer automatiquement à la fin.
- Une fois le setup terminé, le fichier `start_analysis` apparaîtra automatiquement à la racine de votre projet.

**Linux / macOS :**
```bash
chmod +x Setup/setup_LINUX-MACOS.sh
sudo ./Setup/setup_LINUX-MACOS.sh
```
**Windows :**
- Ouvrez le dossier `Setup/`, faites un clic droit sur `setup_WINDOWS.ps1` et sélectionnez **Exécuter avec PowerShell** (validez la demande d'accès Administrateur).

## Préparation des Appareils Cibles

**Android**
1. Allez dans **Paramètres > À propos du téléphone**.
2. Tapotez 7 fois sur **Numéro de build** pour activer les options pour les développeurs.
3. Allez dans **Système > Options pour les développeurs** et activez le **Débogage USB**.
4. Acceptez l'invite **"Faire confiance à cet ordinateur"**.
5. Entrez le code PIN sur l'écran de l'appareil.

**iOS (iPhone/iPad)**
1. Vérifiez que le mode Isolement (Lockdown Mode) de l'iPhone soit désactivé.
2. Déverrouillez l'appareil et branchez-le à l'ordinateur.
3. Acceptez l'invite **"Faire confiance à cet ordinateur"**.
4. Entrez le code PIN sur l'écran de l'appareil.

## Utilisation 
Ne lancez jamais de script Python directement sur votre machine hôte. Utilisez les lanceurs générés (`start_analysis`) pour garantir l'isolation des dépendances.

**Linux / macOS :**
```bash
./start_analysis.sh
```
**Windows :** *Double-cliquez simplement sur le raccourci généré à la racine :*
```bash
./start_analysis.bat
```
L'outil vous guidera pour la suite :
1. Le script démarre la machine virtuelle. Branchez le téléphone et appuyez sur Entrée.
2. Choix du type de périphérique (Android ou iOS).
3. Choix du répertoire de destination (Local, Lecteur externe/Clé USB, ou les deux).
4. Configuration d'un mot de passe robuste pour le chiffrement AES-256 de l'archive finale.
5. Extraction et analyse. Vous pouvez débrancher le téléphone dès que le rapport vous l'indique.

## Résultats de sortie
Une fois le processus terminé, la machine virtuelle se restaure à un état vierge (snapshot). Dans votre dossier de destination (par défaut `results/` ou `Secure_Mobile_Dumps/` sur un disque externe), vous trouverez :
1. **`Dump_[IMEI]_[DATE].tar.gz.aes`** : Archive chiffrée contenant toutes les extractions brutes et les logs détaillés JSON de MVT.
2. **`Report_[IMEI]_[DATE].html / .pdf`** : Rapport d'analyse des IoC listant les signatures malveillantes trouvées, classées par sévérité.

### Comment déchiffrer l'archive ?
Si vous souhaitez exploiter le dump ultérieurement ou lire l'intégralité des logs MVT, vous devez utiliser la librairie `pyAesCrypt`. 

Pour conserver un environnement propre sur votre machine hôte, nous recommandons de créer un environnement virtuel (venv) dédié au déchiffrement :

#### Méthodes 
**Linux / macOS :**
Ouvrez un terminal et exécutez en remplacant par le nom de votre archive :
```bash
# Créer et activer un environnement isolé
python3 -m venv .venv_decrypt
source .venv_decrypt/bin/activate
pip install pyAesCrypt

# Déchiffrer l'archive
pyAesCrypt -d ./results/Dump_XXXX/Dump_XXXX.tar.gz.aes ./results/Dump_XXXX/DUMP_CLAIR.tar.gz
 
# Quitter l'environnement
deactivate
```

**Windows :**
Ouvrez une invite de commande (cmd) et exécutez en remplacant par le nom de votre archive :
```bash
# Créer et activer un environnement isolé
python -m venv .venv_decrypt
.venv_decrypt\Scripts\activate.bat
pip install pyAesCrypt

# Déchiffrer l'archive
pyAesCrypt -d C:\chemin\vers\Dump_XXXX.tar.gz.aes C:\chemin\vers\DUMP_CLAIR.tar.gz

# Quitter l'environnement
.venv_decrypt\Scripts\deactivate.bat
```
*Note : Le mot de passe de déchiffrement défini lors de l'extraction vous sera demandé par le programme ou via la ligne de commande.*

**Script Python**
Si vous souhaitez automatiser le déchiffrement dans un autre outil forensique, voici le snippet Python à utiliser :

```bash
import pyAesCrypt
# Paramètres à adapter 
fichier_chiffre = "Dump_XXXX.tar.gz.aes"
fichier_clair = "DUMP_CLAIR.tar.gz"
mot_de_passe = "VOTRE_MOT_DE_PASSE"
buffer_size = 8 * 1024 * 1024
# Déchiffrement
pyAesCrypt.decryptFile(fichier_chiffre, fichier_clair, mot_de_passe, buffer_size)
print("Déchiffrement terminé !")
```
#### Etape Finale
**Extraction**
Une fois le fichier `DUMP_CLAIR.tar.gz` obtenu, vous pouvez l'extraire avec n'importe quel gestionnaire d'archives standard (7-Zip, WinRAR) ou directement via la commande :
```bash
tar -xzf DUMP_CLAIR.tar.gz
```

## Avertissement Légal & Crédits
Cet outil a été conçu **exclusivement** pour l'analyse forensique consensuelle. Il ne doit pas être utilisé pour extraire des données d'appareils n'appartenant pas à l'analyste, ou sans le consentement explicite du propriétaire de l'appareil.

Merci à **Amnesty International Security Lab** pour le développement et la maintenance de MVT et AndroidQF. 
