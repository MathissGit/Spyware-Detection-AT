# Stratégie de test — 3 niveaux obligatoires

Chaque **nouvelle fonctionnalité** ou correction doit être démontrée par des tests à
**trois niveaux** avant validation :

| Niveau | Type | But | Échec si |
|---|---|---|---|
| **Couche 1** | Tests unitaires | Chaque fonction/branche isolée (fake de sous-processus, FS, réseau) | un test échoue |
| **Couche 2** | Tests d'intégration simulée | Circulation réelle des données entre modules (workflow complet sans matériel) | un test échoue |
| **Couche 3** | Tests de non-régression + couverture | **100 % des lignes** de `main/`, `gui/`, `scripts/` couvertes à chaque commit | ligne non exécutée |

## Couverture 100 % obligatoire

- `fail_under = 100` est figé dans `pyproject.toml`.
- Source éligible : `main`, `gui`, `scripts` (le code livré). Les tests, `.venv_*` et
  `mvt_iocs/` sont exclus.
- Toute ligne non couverte **bloque** le commit et la CI (`--cov-fail-under=100`).

## Désélection interdite

Aucun test ne peut être désélectionné (`-k`, `-m`, `--ignore`) dans les commandes
officielles (`scripts/run_tests.sh`, `.githooks/pre-commit`, `.github/workflows/ci.yml`).
Les tests qui nécessitent un matériel réel sont **auto-skip** (voir ci-dessous), ce qui
n'est pas une désélection : le test existe et s'exécute sans condition de matériel.

Le workflow on-demand `.github/workflows/real-device.yml` (et le script
`scripts/run_integration_real.sh`) sélectionnent volontairement les seuls tests
`real_android`/`real_ios` pour un run sur machine avec appareils branchés :
il s'agit d'un usage **complémentaire** sur demande, jamais de la barrière officielle.

## Matériel réel : auto-skip

- `@pytest.mark.real_android`  → ignoré automatiquement si aucun appareil Android branché.
- `@pytest.mark.real_ios`      → ignoré automatiquement si aucun appareil iOS branché.
- Détection par `conftest.py` (`android_device_present()` / `ios_device_present()`).
- Résultat : la suite reste **100 % verte** sur n'importe quelle machine, tout en
  s'exécutant "pour de vrai" dès qu'un appareil est présent.

## Points d'entrée

| Commande | Usage |
|---|---|
| `scripts/run_tests.sh` | Suite complète locale (auto `xvfb-run` si pas de DISPLAY) |
| `.githooks/pre-commit` | Verrou sur chaque commit (installé via `scripts/setup_hook.sh`) |
| `.github/workflows/ci.yml` | Verrou CI à chaque push/PR |

Toutes exécutent : `pytest tests/ --cov=main --cov=gui --cov=scripts --cov-fail-under=100`.

## Fichiers de tests utiles

- `tests/test_workers_coverage.py` — branches de `gui/workers.py` (62 tests, couverture 100 %).
- `tests/test_gui_coverage.py` — pages/rouage GUI restants (icône, logs, timers, drives…).
- `tests/test_gui_extended.py` — navigation application + résultats (couche 2).
- `tests/test_main_cli.py` — CLI complète `main.py`.
- `tests/test_workers_public.py` — API publique de `gui/workers.py`.
- `tests/test_scripts_coverage.py` — branches restantes `build_iocs.py` / `sandbox_tasks.py`.
- `tests/test_sandbox*.py`, `tests/test_iocs*.py` — workflows sandbox et IoC.
- `tests/conftest.py` — fixtures partagées + auto-skip matériel + stabilisation CTk.

## Environnement de test

```bash
python3 -m venv .venv_tests
.venv_tests/bin/pip install -r requirements.txt
scripts/run_tests.sh
```

Sous Linux de bureau, une session graphique est requise (`DISPLAY=:0`) ; en CI,
`xvfb-run -a` est utilisé.