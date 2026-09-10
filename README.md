# Spyware Detection Automated Tool

Un outil d'automatisation d'extraction forensique et d'analyse de compromission (Spyware) pour smartphones **Android** et **iOS**.

Ce projet est un outil d'investigation numérique (DFIR) conçu pour automatiser l'extraction et l'analyse de smartphones (iOS & Android) suspectés d'être compromis par des logiciels espions. Ce projet s'appuie sur le [Mobile Verification Toolkit (MVT)](https://github.com/mvt-project/mvt) d'Amnesty International et sur [AndroidQF](https://github.com/mvt-project/androidqf).
Il automatise de bout en bout l'extraction, l'analyse des indicateurs de compromission (IOC), la génération de rapports (HTML/PDF) et la sécurisation des données extraites via un chiffrement AES-256.

Afin de protéger la machine de l'analyste contre les attaques physiques, de type BadUSB ou les rebonds de malwares, les accès USB, les extractions (AndroidQF, sauvegarde iOS) et les analyses MVT s'exécutent dans une **machine virtuelle éphémère** (Debian 12) pilotée par Vagrant, tandis que **l'interface** (IHM ou CLI) et la génération des rapports/chiffrement restent sur la **machine hôte**. Les échanges se font par SSH (`vagrant ssh`) et le dossier partagé `/vagrant`. L'interface se lance donc directement sur le bureau, pas dans la VM.

## Fonctionnalités

* **IHM graphique (GUI) :** interface moderne avec détection automatique des périphériques, sélection du mode d'analyse (avec ou sans sandbox), barre de progression par étapes et tableau de bord de résultats. Lancement en quelques clics.
* **Support multi-OS :** fonctionne sur Linux et macOS. Windows n'est pas supporté nativement (utilisez WSL).
* **Multi-appareils :** prise en charge d'Android (via `AndroidQF`) et iOS (via `idevicebackup2`).
* **Détection de périphériques :** détection automatique du téléphone branché en USB (Android via ADB, iOS via libimobiledevice).
* **IOC :** bases de menaces connues.
* **Génération de rapports :** synthèse automatique des alertes en formats HTML et PDF.
* **Sécurité de stockage :** chiffrement AES-256 de l'archive de l'appareil.
* **Isolation Python :** environnement virtuel Python (`.venv_forensics` en mode direct, `/opt/venv_forensics` dans la VM en mode sandbox).
* **Sandboxing éphémère :** la VM Debian 12 utilise un instantané propre, restauré à chaque session.
* **Double interface :** le CLI et l'IHM graphique — choix au lancement.

## Pré-requis

**Système :**
- Linux ou macOS (Windows non supporté nativement — utilisez WSL)
- Python 3.10+

**Mode sandbox (recommandé) :**
- [VirtualBox](https://www.virtualbox.org/) 7.0+
- [Vagrant](https://www.vagrantup.com/) 2.4+

**Mode direct :**
- `python3`, `pip`, `python3-tk`, `adb` (Android Debug Bridge)
- `libimobiledevice-utils` et `usbmuxd`

## Contenu du dépôt

Fichiers sources du projet (le reste est généré à l'installation, voir la note plus bas) :

```plaintext
Spyware-Detection-AT/
├── main.py                   # Script principal CLI (extraction, analyse, chiffrement)
├── gui.py                    # Point d'entrée de l'interface graphique
├── setup.sh                  # Script d'installation unique (Linux/macOS, rollback auto)
├── Vagrantfile               # Configuration de la VM Debian 12 éphémère
├── icon.png                  # Icône de l'interface graphique
├── ioc_personal.json         # Vos indicateurs personnels
├── ioc_sources.json          # Sources externes d'IOC
├── Parcours_Utilisateur.md   # Guide pas à pas d'utilisation
├── README.md                 # Ce fichier
├── gui/                      # Package de l'IHM CustomTkinter
│   ├── app.py                # Fenêtre principale et navigation
│   ├── theme.py              # Charte graphique (couleurs, polices)
│   ├── workers.py            # Threads d'analyse en arrière-plan
│   ├── sandbox_client.py     # Couche SSH vers la VM (mode sandbox)
│   ├── pages/                # Écrans (accueil, mode, détection, analyse...)
│   └── widgets/              # Composants réutilisables (barre de progression...)
├── scripts/
│   ├── launch.sh             # Lanceur unifié direct/sandbox (cli ou gui)
│   ├── sandbox_tasks.py      # Tâches exécutées DANS la VM (détection, extraction, MVT)
│   ├── update_iocs.sh        # Vérifier & mettre à jour les IoC
│   ├── build_iocs.py         # Construction des bases IOC STIX2 (check / update)
│   └── setup_hook.sh         # Installe le hook pre-commit
├── tests/                    # Tests de non-régression (pytest)
└── .githooks/pre-commit      # Hook git : bash -n + pytest
```

> [!NOTE]
> Les éléments **générés** par `setup.sh` et le lancement ne font pas partie du dépôt : `start_analysis.sh`, le binaire AndroidQF (téléchargé), l'environnement `.venv_forensics/`, les bases `mvt_iocs/` et les résultats `results/`. Ils sont recréés automatiquement à l'installation et au lancement.

## Installation

### Étape 1 : cloner le dépôt
```bash
git clone https://github.com/MathissGit/Spyware-Detection-AT
cd Spyware-Detection-AT
```

### Étape 2 : installer l'outil
Le script `setup.sh` installe toutes les dépendances, récupère la dernière version d'AndroidQF, crée l'environnement Python, construit les bases IOC et génère `start_analysis.sh`. Aucun téléchargement manuel requis.
```bash
./setup.sh
```

### Étape 3 : configurer la machine hôte
*À ne faire qu'une seule fois.*

| Mode | Description | Sécurité | Vitesse |
|------|-------------|----------|---------|
| **Sandbox (VM)** | Exécution dans une VM VirtualBox Debian 12 | Maximale (isolation totale) | Plus lente (démarrage VM) |
| **Mode direct** | Installation locale directement sur l'hôte | Standard | Rapide (pas de VM) |

**Linux / macOS :**
```bash
chmod +x setup.sh
sudo ./setup.sh
```

> [!NOTE]
> Windows n'est pas supporté nativement (MVT ne fonctionne pas sur Windows). Utilisez **WSL (Windows Subsystem for Linux)** et suivez les instructions Linux.

> [!NOTE]
> Le script `start_analysis.sh` apparaît automatiquement à la racine. Un redémarrage peut être requis (sandbox uniquement).

> [!NOTE]
> L'interface se lance uniquement via `./start_analysis.sh` à la racine du projet. Aucun raccourci bureau n'est créé.

### Où exécuter les commandes ?

Toutes les commandes (installation, lancement) se font **dans le dossier du projet** (celui qui contient `setup.sh`, `main.py`, ...) :

1. Ouvrez un terminal (fenêtre de commandes).
2. Naviguez jusqu'au dossier du projet :
   ```bash
   cd /chemin/vers/Spyware-Detection-AT
   ```
   *Si vous avez cloné le dépôt dans `~/Bureau`, la commande devient : `cd ~/Bureau/Spyware-Detection-AT`.*
3. Vérifiez que vous êtes au bon endroit en tapant :
   ```bash
   pwd
   ```
   Le chemin affiché doit se terminer par `Spyware-Detection-AT`.

> [!IMPORTANT]
> **Après un redémarrage** (parfois demandé en mode sandbox), ouvrez **à nouveau un terminal dans le même dossier** (voir le point 2) puis lancez :
> ```bash
> ./start_analysis.sh
> ```
> Toutes ces commandes se font **dans le dossier du projet** — ne les lancez pas depuis n'importe où.

### Prérequis matériel : virtualisation (mode sandbox uniquement)

Le mode sandbox installe VirtualBox + Vagrant et démarre une **VM Debian 12**. Pour que cela fonctionne :

- **Activez la virtualisation dans le BIOS/UEFI** de votre machine :
  - **Intel** : `VT-x` (parfois appelé `Intel Virtualization Technology`).
  - **AMD** : `AMD-V` (parfois appelé `SVM Mode`).
  - Dans le menu BIOS/UEFI (touche `F2`, `Suppr` ou `F10` au démarrage), cherchez les options *Virtualization / Virtualisation* et mettez-les sur **Enabled**, puis enregistrez et redémarrez. *C'est possible même si vous avez déjà un système installé : l'activation est réversible.*
- **KVM** : le script désactive automatiquement les modules `kvm` pour libérer la virtualisation imbriquée (utile dans une machine virtuelle). Un redémarrage est demandé la première fois.
- **Secure Boot** : si le module `vboxdrv` de VirtualBox n'est pas signé, désactivez **Secure Boot** dans le BIOS/UEFI ou signez le module.
- **Carte / noyau** : les `linux-headers` correspondant à votre noyau sont installés automatiquement. En cas d'échec de `vboxdrv`, **mettez à jour le noyau, puis redémarrez**.

Le mode **direct** n'a besoin d'aucune de ces prérogatives de virtualisation.

## Préparation des appareils cibles

### Android
1. **Paramètres > À propos du téléphone** > tapez 7 fois sur **Numéro de build** (le mode développeur est alors débloqué).
2. **Système > Options pour les développeurs** > activez le **Débogage USB**.
3. Branchez le téléphone : un message **« Autoriser le débogage USB ? »** apparaît, acceptez-le.
4. Lors du couplage, Android demande **« Faire confiance à cet ordinateur ? »** : acceptez.

> [!IMPORTANT]
> **Mode développeur et mot de passe du téléphone.**
> Pour activer chaque étape ci-dessus (déverrouiller le message de confiance, accepter le débogage USB, appairer ADB), Android vous demandera de **saisir le code PIN / mot de passe de l'écran de verrouillage du téléphone** — c'est-à-dire le code qui déverrouille le téléphone lui-même, **pas** le mot de passe de chiffrement AES-256 créé plus tard à l'étape 6 du flux d'analyse. Gardez donc le téléphone déverrouillé pendant toute l'analyse.

### iOS (iPhone/iPad)
1. Vérifiez que le **Lockdown Mode** est désactivé.
2. Déverrouillez l'appareil, branchez-le, acceptez la confiance, entrez le PIN.
   > Le PIN demandé ici est également le **code de l'écran de verrouillage de l'iPhone**, pas le mot de passe AES-256 de l'analyse.

## Utilisation

> [!WARNING]
> Ne lancez jamais `main.py` ou `gui.py` directement. Utilisez toujours `start_analysis.sh`.

**Linux / macOS :** `./start_analysis.sh`

### Interface graphique (IHM)

Au lancement de `start_analysis.sh`, choisissez l'interface souhaitée :
- **1) Interface graphique (IHM)** — s'ouvre **sur l'hôte** ; en mode sandbox, la VM reste chargée de l'accès USB et de l'analyse.
- **2) Interface en ligne de commande (CLI)** — idem via `main.py --mode direct|sandbox`.

> [!NOTE]
> **Architecture hôte / VM** : en mode sandbox, l'interface (IHM ou CLI) tourne sur l'hôte et communique avec la VM via `vagrant ssh` (`gui/sandbox_client.py` → `scripts/sandbox_tasks.py` dans la VM). L'appareil n'est visible que par la VM (filtres USB VirtualBox) ; le téléphone branché est capturé automatiquement. Les données extraites passent par `/vagrant` (dossier partagé) puis le rapport et l'archive AES-256 sont produits sur l'hôte, dans `results/`.

Le flux de l'IHM :
1. **Accueil** — Nouvelle analyse ou installation des dépendances.
2. **Mode d'analyse** — Sandbox (sécurisé, VM) ou Direct (rapide).
3. **Type d'appareil** — Android ou iOS.
4. **Détection** — Branchez le téléphone, l'outil détecte automatiquement l'OS (ADB / libimobiledevice) et affiche l'IMEI.
5. **Destination** — Local, externe ou les deux (avec détection des périphériques de stockage).
6. **Mot de passe** — Création du mot de passe AES-256 avec indicateur de force.
7. **Analyse** — Barre de progression par étapes (connexion, extraction, analyse IOC, rapport, chiffrement, finalisation) avec journal en direct.
8. **Résultats** — Tableau de bord récapitulatif avec ouverture des rapports HTML/PDF.

> [!TIP]
> Un guide pas à pas détaillé de l'ensemble du flux est disponible dans **`Parcours_Utilisateur.md`**.

## Résultats de sortie

```
Dump_[IMEI]_[DATE]/
├── Dump_[IMEI]_[DATE].tar.gz.aes   # Archive chiffrée AES-256
├── Report_[IMEI]_[DATE].html       # Rapport d'analyse HTML
└── Report_[IMEI]_[DATE].pdf        # Rapport d'analyse PDF
```

### Comment déchiffrer l'archive ?

**Linux / macOS :**
```bash
python3 -m venv .venv_decrypt
source .venv_decrypt/bin/activate
pip install pyAesCrypt
pyAesCrypt -d ./results/Dump_XXXX/Dump_XXXX.tar.gz.aes ./results/Dump_XXXX/DUMP_CLAIR.tar.gz
deactivate
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

L'outil combine **trois sources d'IOC**, toutes utilisées pendant l'analyse :

1. **IOC personnels** — vos propres indicateurs dans `ioc_personal.json` (noms, paquets, certificats, sites web, C2, e-mails...). Ajoutez librement vos entrées : elles sont converties en STIX2 et exploitées automatiquement. *Ce fichier ne contient que VOS indicateurs : les grands jeux publics (ex. AssoEchap) sont chargés via les sources externes pour éviter la duplication.*
2. **Sources externes** — listées dans `ioc_sources.json` (par défaut : `AssoEchap/stalkerware-indicators`, à la fois son `ioc.yaml` et son STIX2 généré). Chaque source s'intègre via **un** de ces trois champs :
   - `"github": {"owner", "repo", "branch", "path"}` — dépôt distant (YAML AssoEchap ou STIX2).
   - `"url": "https://..."` — fichier distant direct (`.stix2` ou `.yaml`/`.json`).
   - `"file": "chemin/local.stix2"` — fichier local `.stix2`, `.yaml` ou `.json`.
3. **Bases officielles MVT** — téléchargées automatiquement par `mvt download-iocs` dans le dossier de données MVT (`~/.local/share/mvt/indicators/`).

Le script `scripts/build_iocs.py` récupère/convertit/déduplique toutes les sources et produit les fichiers `.stix2` dans `mvt_iocs/`, partagés avec la VM via le dossier monté Vagrant (`/vagrant/`).

```plaintext
ioc_personal.json ─┐
ioc_sources.json ──┤→ scripts/build_iocs.py ─→ mvt_iocs/*.stix2 ─┐
   (github/url/file)                        (dédupliqués)         │
mvt download-iocs ─┘                    dossier officiel MVT ─────┤ MVT (MVT_STIX2 + auto-load)
                                                                   ▼
                                        mvt-android check-androidqf
                                        mvt-ios check-backup
```

**Mise à jour des indicateurs :** les IOC sont considérés à jour si le plus récent fichier `.stix2` de `mvt_iocs/` a moins de 7 jours (168h). Sinon, `build_iocs.py` relance la construction avant le démarrage de l'analyse (déclenchement automatique dans `launch.sh` / `setup.sh`).

### Vérifier et mettre à jour les IoC

Un workflow explicite permet de vérifier l'état des bases puis de les régénérer à la demande :

```bash
scripts/update_iocs.sh                # vérifie l'état (inspection locale, hors ligne)
scripts/update_iocs.sh check          # idem (alias)
scripts/update_iocs.sh update         # régénère si périmé (> 7 j)
scripts/update_iocs.sh --force        # force la régénération même si à jour
```

Le script `check` (aussi accessible via `build_iocs.py check`) **n'écrit rien et n'accède pas au réseau** : il liste chaque `.stix2` de `mvt_iocs/` avec son âge et son nombre d'indicateurs, recense les bases officielles présentes dans `~/.local/share/mvt/indicators/`, puis retourne **0** si tout est à jour (sinon **1**). Le wrapper `update` ne retravaille que si nécessaire (sauf `--force`).

De façon équivalente, `build_iocs.py` s'utilise avec des sous-commandes :

```bash
.venv_forensics/bin/python scripts/build_iocs.py            # = update (défaut)
.venv_forensics/bin/python scripts/build_iocs.py update     # reconstruit tout
.venv_forensics/bin/python scripts/build_iocs.py check      # inspection locale
.venv_forensics/bin/python scripts/build_iocs.py update --dry-run  # hors ligne
```

> Note : `update` reconstruit toujours (c'est une commande d'écriture explicite). La logique « ne régénérer que si périmé » (et la variante `--force`) vit dans le wrapper `scripts/update_iocs.sh` et le déclenchement automatique de `launch.sh` / `setup.sh`.

**Chaînes de caractères supportées :** `app:id` (paquets Android), `app:cert.sha1` (certificats), `domain-name:value` et `url:value` (sites web, C2), `ipv4-addr:value` (C2 IP), `email-addr:value`, `process:name`, `file:hashes.*`.

### Ajouter une source ou un fichier IOC

Ajoutez une entrée dans `ioc_sources.json`. Trois exemples :

```jsonc
{ "name": "Ma liste locale", "type": "yaml", "file": "iocs/mes_indicateurs.yaml" }
{ "name": "Fichier STIX2 téléchargé", "type": "stix2", "file": "iocs/custom.stix2" }
{ "name": "Source distante", "type": "stix2", "url": "https://exemple.org/indicators.stix2" }
```

Puis reconstruisez :
```bash
scripts/update_iocs.sh update        # régénère (ou : .venv_forensics/bin/python scripts/build_iocs.py)
```
*(ou `--dry-run` pour uniquement vos IOC personnels + fichiers locaux, sans accès réseau.)*

## Tests de non-régression

Un jeu de tests **pytest** est fourni dans `tests/` et s'exécute automatiquement à chaque `git commit` via un **hook pre-commit** ainsi que sur la **CI GitHub Actions** (`.github/workflows/ci.yml`). Si un test échoue — ou si la couverture tombe sous **100 %** — le commit / le push est bloqué.

La stratégie détaillée figure dans **[TEST_STRATEGY.md](TEST_STRATEGY.md)**. En résumé, chaque fonctionnalité est démontrée à **3 niveaux** :

1. **Couche 1 – tests unitaires** : chaque fonction et branche isolée.
2. **Couche 2 – tests d'intégration simulée** : workflows complets sans matériel (fake subprocess, FS, réseau).
3. **Couche 3 – non-régression et couverture** : **100 % des lignes** de `main/`, `gui/`, `scripts/`.

Les tests nécessitant un appareil réel (`@pytest.mark.real_android` / `real_ios`) sont **auto-skip** quand aucun appareil n'est branché : la suite reste 100 % verte partout, et s'exécute réellement dès qu'un appareil est présent.

### Installation du hook (une seule fois par clone)

```bash
./scripts/setup_hook.sh
```

Le hook installe un lien symbolique `pre-commit` dans `git/hooks/` (pointant vers `.githooks/pre-commit`) et exécute ensuite automatiquement :
1. **Vérification de la syntaxe** des scripts shell (`bash -n`)
2. **Exécution complète de pytest avec couverture 100 %** (aucune désélection)

### Exécution manuelle des tests

```bash
./scripts/run_tests.sh            # choisit l'environnement et xvfb si besoin
# ou, en direct dans l'environnement virtuel :
.venv_tests/bin/python -m pytest tests/ --cov=main --cov=gui --cov=scripts \
    --cov-report=term-missing --cov-fail-under=100
```

### Ajouter un test

Créez un fichier `tests/test_*.py` (auto-découvert par pytest). Pour toute nouvelle branche ajoutée au code livré, ajoutez le test correspondant afin de maintenir la couverture à **100 %**.

## Dépannage

| Problème | Solution |
|----------|----------|
| `androidqf introuvable` | Relancez `sudo ./setup.sh` qui télécharge la dernière version automatiquement |
| Téléphone non détecté | Débogage USB activé + téléphone déverrouillé |
| `adb: no devices found` | Rebranchez, acceptez la confiance, réessayez |
| Sandbox : `Temporary failure resolving 'deb.debian.org'` / `no installation candidate` | Résolution DNS de la VM : le `Vagrantfile` active le résolveur hôte (NAT) et fixe `resolv.conf`. En VPN/entreprise, exportez `http_proxy`/`https_proxy` (et `no_proxy`) avant de lancer — ils sont transmis à la VM (apt + pip). Puis `vagrant destroy -f && ./start_analysis.sh`. |
| Erreur Vagrant/VirtualBox | VirtualBox et Vagrant installés et à jour |
| `mvt-android` introuvable | L'environnement virtuel sera recréé automatiquement |
| Délai dépassé | Timeout de 500s. Relancez et branchez plus rapidement |

### Réinstallation propre
```bash
rm -rf .venv_forensics/ .vagrant/
vagrant destroy -f 2>/dev/null
./start_analysis.sh
```

## Avertissement légal & crédits

Cet outil a été conçu **exclusivement** pour l'analyse forensique consensuelle. Il ne doit pas être utilisé pour extraire des données d'appareils n'appartenant pas à l'analyste, ou sans le consentement explicite du propriétaire.

Merci à **Amnesty International Security Lab** pour le développement et la maintenance de MVT et AndroidQF.