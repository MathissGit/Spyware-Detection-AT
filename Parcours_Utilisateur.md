# Parcour Utilisateur
## Phase 1 : Lancement (~8 min)

L'utilisateur lance `start_analysis.sh` ou `start_analysis.bat`.

**Ce qui se passe :**
1. Le script detecte le mode d'installation (Sandbox ou Direct).
2. **(Sandbox)** Les bases IOC sont verifiees sur l'hote. Si absentes ou vieilles de plus de 7 jours, elles sont telechargées une seule fois (mirroir hote/VM). Puis la VM est demarrée ou restaurée depuis son snapshot.
3. **(Mode direct)** Le script verifie les dependances systeme (adb, libimobiledevice), cree l'environnement Python si besoin, et met a jour les IOC si necessaire.
4. L'invite de branchage USB apparait.

**Sortie type (sandbox) :**
```shell
[*] ===================================================
[*] Lancement de l'environnement d'analyse (Sandbox)
[*] ===================================================
[*] Bases IOC deja a jour (72h). Telechargement ignore.
[*] Verification et demarrage de la Sandbox...
[*] Restauration du snapshot...
[+] Environnement isole pret et securise.
[+] Bases IOC : deja a jour
[*] Branchez le telephone par USB maintenant.
[>] Appuyez sur Entree quand le telephone est branche...
```

**Decision :** Brancher le telephone USB, puis appuyer sur **Entree**.

## Phase 2 : Selection du type d'appareil

Menu interactif avec les fleches du clavier.

```shell
? Quel type d'appareil souhaitez-vous analyser ?
  > Android
    iOS / iPhone
    -- Quitter l'application --
```

| Selection | Action |
|-----------|--------|
| **Android** | Poursuit vers la selection de destination |
| **iOS / iPhone** | Poursuit vers la selection de destination |
| **Quitter** | Ferme l'application |

## Phase 3 : Selection de la destination

```shell
? Ou souhaitez-vous sauvegarder l'archive chiffree ?
  > Uniquement en local (./results)
    Uniquement sur un peripherique externe
    Les deux (Copie Local + Externe)
    -- Retour --
```

| Selection | Action |
|-----------|--------|
| **Local** | Fichiers dans `results/` du projet |
| **Externe** | Sous-menu de detection automatique des peripheriques |
| **Les deux** | Copie redondante locale + externe |
| **Retour** | Revient au choix du type d'appareil |

**Si "Externe" ou "Les deux" :** L'outil detecte automatiquement les peripheriques montes et propose :

```shell
? Selectionnez le peripherique externe :
  > /media/user/USB_DRIVE
    Entrer un autre chemin manuellement...
    -- Retour --
```

## Phase 4 : Mot de passe de chiffrement

```
? Créez le mot de passe de chiffrement AES-256 : ********
? Confirmez le mot de passe : ********
```

> [!IMPORTANT]
> Ce mot de passe est NECESSAIRE pour dechiffrer l'archive. Il n'est PAS stocke. Notez-le en lieu sur.

## Phase 5 : Extraction des donnees (5min à 30min+)

### Android

```shell
[*] Initialisation du pont USB...
[*] Lancement d'AndroidQF...
[+] Extraction terminee (IMEI/Serial: [num_IMEI]).
```

1. **ADB start-server** : Demarrage du serveur ADB
2. **Extraction IMEI** : L'outil recupèrer l'identifiant unique du téléphone. 
3. **AndroidQF** : Extraction des donnees. L'outil détecte automatiquement le nouveau dossier crée.
4. L'utilisateur peut debrancher le telephone dès que l'outil l'indique.

### iOS

```shell
[*] Branchez l'appareil, deverrouillez-le et appuyez sur 'Faire confiance'...
[+] Appareil appaire avec succes.
[*] Creation de la sauvegarde iOS chiffree (Gardez l'ecran allume)...
```

1. **Appairage iOS** : Boucle tant que le telephone n'est pas appaire. L'utilisateur doit deverrouiller et accepter.
2. **Extraction IMEI** : L'outil recupèrer l'identifiant unique du téléphone.
3. **Backup iOS** (5-30min+) : Sauvegarde chiffree native. **L'ecran du telephone doit rester allumé.**

## Phase 6 : Analyse des IOC (1-10min)

```shell
[*] Analyse des IOC en cours...
```

1. `mvt-android check-androidqf` ou `mvt-ios check-backup` compare les donnees aux bases MVT d'Amnesty International.
2. Les logs sont rediriges dans `mvt_log.txt`.

## Phase 7 : Generation du rapport

```shell
[*] Structuration du rapport d'analyse...
[*] Generation du rapport PDF...
```

1. **Parsing du log** : Chaque IoC est classe dans 6 categories.
2. **Generation HTML** : Fichier `Report_[IMEI]_[DATE].html` avec dashboard et couleurs de séverité.
3. **Generation PDF** : Conversion du HTML en PDF.

**Categories de menaces :**

| Categorie | Mots-cles | Signification |
|-----------|-----------|---------------|
| Logiciels Espions Cibles | pegasus, predator, finspy, candiru, cytrox, reign | Logiciel espion gouvernemental |
| Stalkerwares | stalkerware, mspy, cerberus, flexispy, package, app | Surveillance commerciale |
| Domaines & Serveurs C2 | domain, url, http, ip address | Serveur de commande et controle |
| Fichiers & Processus | file, hash, macho, binary, process | Binaire ou hash malveillant |
| Communications | sms, message, mail, whatsapp, telegram | Phishing ou exploit zero-click |
| Autres STIX2 | (tous les autres) | Threat Intelligence non classee |

**Statut de l'appareil :**
- **Vert** : "Aucun indicateur de compromission detecte" (0 IoC)
- **Orange** : "Menaces Potentielles" (IoC non-critiques)
- **Rouge** : "Appareil Compromis" (au moins 1 IoC critique)

## Phase 8 : Securisation et archivage (~2 min)

```shell
Creation de l'archive... ━━━━━━━━━━━━━━━━━━━━━━━━ 100%
Chiffrement AES-256...   ━━━━━━━━━━━━━━━━━━━━━━━━ 100%
```

1. **Creation de l'archive en "tar.gz"** : Archive des dossiers d'extraction
2. **Chiffrement AES-256** : Chiffrement de l'archive
3. **Déplacement des rapports** vers le dossier de destination
4. **(Si externe)** Copie redondante vers le peripherique externe
5. **Purge** : Suppression definitive des dossiers temporaires

**Sortie finale :**
```shell
╭──────────────────────────────────────────────────────────────╮
│  Operation terminee !                                        │
│  L'appareil (IMEI: [num_IMEI]) a ete analyse.                │
│  L'archive chiffree et les rapports sont conserves dans :    │
│  ./results/Dump_[num_IMEI]_2025-01-15_14-30-00               │
╰──────────────────────────────────────────────────────────────╯
```

## Phase 10 : Nettoyage - Mode Sandbox

Apres la fin du script Python, le script bash de lancement effectue automatiquement :
1. **Suppression complete de la VM d'analyse** (`vagrant destroy -f`) — pas de trace residuelle
2. Suppression des processus ADB résiduels

L'utilisateur n'a **rien a faire** : la VM est detruite entierement, qu'il y ait eu succes ou interruption de l'analyse. Aucun snapshot n'est conservé.
