#!/usr/bin/env python3
"""Construit les bases IOC STIX2 utilisees par MVT.

- Lit ioc_sources.json (sources externes) et ioc_personal.json (indicateurs
  personnels, format AssoEchap/stalkerware-indicators).
- Telecharge les sources et convertit le format YAML/JSON AssoEchap en bundles
  STIX2 (objets malware / indicator / relationship) lisibles par MVT.
- Ecrit les fichiers .stix2 dans mvt_iocs/ (dossier analyse par MVT via MVT_STIX2).

Sous-commandes :
  update           (defaut) reconstruit les bases IOC dans mvt_iocs/
                   depuis ioc_personal.json + ioc_sources.json.
                   --dry-run : personnel + fichiers locaux uniquement (hors ligne).
  check            inspecte localement l'etat des bases (age, compteurs,
                   bases officielles MVT) et retourne 0 si a jour, 1 sinon.
                   Aucun acces reseau, aucune ecriture.

Usage :
  .venv_forensics/bin/python scripts/build_iocs.py [update] [--out DIR] [--dry-run]
  .venv_forensics/bin/python scripts/build_iocs.py check [--out DIR]
"""

import argparse
import datetime
import glob
import json
import os
import sys
import uuid
from typing import Any, Dict, List, Optional

import yaml

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_FILE = os.path.join(SCRIPT_DIR, "ioc_sources.json")
PERSONAL_FILE = os.path.join(SCRIPT_DIR, "ioc_personal.json")
DEFAULT_OUT = os.path.join(SCRIPT_DIR, "mvt_iocs")

GITHUB_RAW = "https://raw.githubusercontent.com/{}/{}/{}/{}"

# Age au-dela duquel les bases IOC sont considerees comme perimees (7 jours),
# coherent avec le seuil utilise par launch.sh / setup.sh.
MAX_AGE_HOURS = 168

DEFAULT_MVT_INDICATORS = os.path.expanduser("~/.local/share/mvt/indicators")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}--{uuid.uuid4()}"


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def source_content(source: dict) -> Optional[str]:
    """Retourne le contenu brut d'une source : fichier local, url, ou github.

    Le champ 'file' (chemin local) a la priorite : il permet d'ajouter un
    fichier IOC (.stix2, .yaml ou .json) de facon simple, sans reseau.
    """
    file = source.get("file")
    if file:
        path = file if os.path.isabs(file) else os.path.join(SCRIPT_DIR, file)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read()
        except OSError as exc:
            print(f"[!] Echec lecture fichier {source.get('name')} ({path}) : {exc}")
            return None

    if requests is None:
        print("[!] Module 'requests' indisponible. Installez-le dans le venv.")
        return None

    github = source.get("github")
    url = source.get("url", "")
    if github:
        url = GITHUB_RAW.format(
            github.get("owner", ""),
            github.get("repo", ""),
            github.get("branch", "main"),
            github.get("path", ""),
        )
    if not url:
        print(f"[!] Source sans file/url/github : {source.get('name')}")
        return None

    try:
        res = requests.get(url, timeout=20)
        if res.status_code != 200:
            print(f"[!] Echec {source.get('name')} ({res.status_code}) : {url}")
            return None
        return res.text
    except Exception as exc:  # noqa: BLE001
        print(f"[!] Echec {source.get('name')} : {exc}")
        return None


def indicators_from_yaml(content: str) -> List[dict]:
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        print(f"[!] YAML invalide : {exc}")
        return []
    if not isinstance(data, list):
        print("[!] Format YAML attendu : liste d'indicateurs (ioc.yaml AssoEchap).")
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def _stix_object(prefix: str, **fields) -> dict:
    if "id" not in fields:
        fields["id"] = _new_id(prefix)
    fields.setdefault("type", prefix)
    fields.setdefault("spec_version", "2.1")
    fields.setdefault("created", _now())
    fields.setdefault("modified", fields["created"])
    return fields


def _pattern(key: str, value: str) -> str:
    return f"[{key}='{value}']"


def build_stix2(
    indicators: List[dict],
    collection_name: str,
    seen_patterns: Optional[set] = None,
) -> Optional[dict]:
    """Convertit une liste d'entrees format AssoEchap en bundle STIX2.

    Si seen_patterns est fourni, un pattern deja produit par une autre source
    est ignore (deduplication globale).
    """
    objects: List[dict] = []
    created = _now()
    if seen_patterns is None:
        seen_patterns = set()

    for entry in indicators:
        name = entry.get("name", collection_name)
        malware = _stix_object(
            "malware",
            id=_new_id("malware"),
            name=name,
            description=entry.get("type", "") or "",
            is_family=True,
        )
        objects.append(malware)

        patterns: List[str] = []

        for pkg in entry.get("packages", []) or []:
            patterns.append(_pattern("app:id", pkg))

        for cert in entry.get("certificates", []) or []:
            patterns.append(_pattern("app:cert.sha1", cert))

        for site in entry.get("websites", []) or []:
            patterns.append(_site_pattern(site))
        for dist in entry.get("distribution", []) or []:
            patterns.append(_site_pattern(dist))

        c2 = entry.get("c2", {}) or {}
        if isinstance(c2, dict):
            for domain in c2.get("domains", []) or []:
                patterns.append(_pattern("domain-name:value", domain))
            for ip in list(c2.get("ips", []) or []) + list(c2.get("ip", []) or []):
                patterns.append(_pattern("ipv4-addr:value", ip))
        elif isinstance(c2, list):
            for value in c2:
                patterns.append(_pattern("domain-name:value", value))

        for domain in entry.get("domains", []) or []:
            patterns.append(_pattern("domain-name:value", domain))
        for ip in list(entry.get("ips", []) or []) + list(entry.get("ip", []) or []):
            patterns.append(_pattern("ipv4-addr:value", ip))
        for email in entry.get("emails", []) or []:
            patterns.append(_pattern("email-addr:value", email))
        for proc in entry.get("processes", []) or []:
            patterns.append(_pattern("process:name", proc))
        for hashes in entry.get("hashes", []) or []:
            patterns.append(_pattern("file:hashes.sha256", hashes))

        seen: set = set()
        for pattern in patterns:
            if pattern in seen or pattern in seen_patterns:
                continue
            seen.add(pattern)
            seen_patterns.add(pattern)
            indicator = _stix_object(
                "indicator",
                id=_new_id("indicator"),
                indicator_types=["malicious-activity"],
                pattern=pattern,
                pattern_type="stix",
                pattern_version="2.1",
                valid_from=created,
            )
            objects.append(indicator)
            objects.append(
                _stix_object(
                    "relationship",
                    id=_new_id("relationship"),
                    relationship_type="indicates",
                    source_ref=indicator["id"],
                    target_ref=malware["id"],
                )
            )

    if len(objects) == 0:
        return None
    return {"type": "bundle", "id": f"bundle--{uuid.uuid4()}", "objects": objects}


def _site_pattern(value: str) -> str:
    """websites/distribution -> domain-name:value ou url:value selon le contenu."""
    value = value.strip()
    if "://" in value:
        return _pattern("url:value", value)
    if "/" in value and not value.startswith("www."):
        return _pattern("url:value", "https://" + value)
    return _pattern("domain-name:value", value)


def write_stix2(path: str, bundle: dict) -> int:
    count = sum(1 for o in bundle["objects"] if o["type"] == "indicator")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(bundle, handle, indent=2)
    print(f"[+] {os.path.basename(path)} : {count} indicateurs")
    return count


def slugify(name: str) -> str:
    keep = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    return keep.strip("_").lower() or "ioc"


def detect_type(source: dict, content: str) -> str:
    """Detecte le type de contenu d'une source (yaml vs stix2/json)."""
    low = ""
    if source.get("file"):
        low = source["file"].lower()
    elif source.get("github"):
        low = source["github"].get("path", "").lower()
    if low.endswith((".yaml", ".yml")):
        return "yaml"
    if low.endswith((".stix2", ".json")):
        try:
            json.loads(content)
            return "stix2"
        except Exception:  # noqa: BLE001
            return "json"
    try:
        data = yaml.safe_load(content)
    except Exception:  # noqa: BLE001
        return "stix2"
    if isinstance(data, list):
        return "yaml"
    if isinstance(data, dict) and "objects" in data:
        return "stix2"
    return "yaml"


def write_passthrough_source(path: str, content: str) -> int:
    """Ecrit une source STIX2 brute (bundle deja forme) et compte les indicateurs."""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    try:
        count = sum(
            1
            for o in json.loads(content).get("objects", [])
            if o.get("type") == "indicator"
        )
    except Exception:  # noqa: BLE001
        count = -1
    print(f"[+] {os.path.basename(path)} : {count if count >= 0 else '?'} indicateurs")
    return max(count, 0)


def _all_sources_unsafe() -> List[dict]:
    return load_json(SOURCES_FILE).get("sources", [])


def cmd_update(out_dir: str, dry_run: bool = False) -> int:
    """Reconstruit les bases IOC dans out_dir. Retourne 0 si ok, sinon 1."""
    os.makedirs(out_dir, exist_ok=True)
    total = 0
    errors = 0

    # ensemble global des patterns deja produits, pour deduplication
    all_patterns: set = set()

    def emit(entries: List[dict], collection_name: str, filename: str) -> int:
        """Convertit des entrees AssoEchap en STIX2 et l'ecrit (deduplique)."""
        bundle = build_stix2(entries, collection_name, seen_patterns=all_patterns)
        if not bundle:
            return 0
        return write_stix2(os.path.join(out_dir, filename), bundle)

    personal = load_json(PERSONAL_FILE)
    personal_list = personal.get("indicators", []) if isinstance(personal, dict) else []
    if personal_list:
        total += emit(personal_list, "indicators-personnels", "personal.stix2")
    else:
        print("[*] ioc_personal.json vide : aucun indicateur personnel (optionnel).")

    # En dry-run (hors ligne) : on traite uniquement les sources locales,
    # jamais les sources distantes (github / url).
    sources = [s for s in _all_sources() if s.get("file")] if dry_run else _all_sources()
    for source in sources:
        content = source_content(source)
        if content is None:
            errors += 1
            continue
        total += process_source(source, content, out_dir, seen_patterns=all_patterns)

    if dry_run:
        print(f"[*] Dry-run termine. {total} indicateurs (personnels + fichiers locaux).")
    else:
        print(f"[*] Termine. {total} indicateurs tous types confondus.")
    return 0 if errors == 0 else 1


def _ioc_files_stats(out_dir: str) -> List[dict]:
    """Liste des .stix2 de out_dir avec age (heures) et nb d'indicateurs."""
    stats: List[dict] = []
    if not os.path.isdir(out_dir):
        return stats
    now = datetime.datetime.now().timestamp()
    for name in sorted(os.listdir(out_dir)):
        if not name.endswith(".stix2"):
            continue
        path = os.path.join(out_dir, name)
        try:
            mtime = os.path.getmtime(path)
            bundle = json.load(open(path, encoding="utf-8"))
            count = sum(
                1 for o in bundle.get("objects", []) if o.get("type") == "indicator"
            )
        except Exception:  # noqa: BLE001
            mtime = 0.0
            count = -1
        stats.append(
            {
                "name": name,
                "age_hours": round((now - mtime) / 3600, 1) if mtime else None,
                "count": count,
            }
        )
    return stats


def cmd_check(out_dir: str, max_age_hours: int = MAX_AGE_HOURS) -> int:
    """Inspecte localement l'etat des bases IOC (aucun acces reseau).

    Retourne 0 si toutes les bases sont a jour (< max_age_hours), sinon 1.
    """
    print(f"[*] Vérification des bases IOC dans : {out_dir}")
    stats = _ioc_files_stats(out_dir)
    if not stats:
        print("[!] Aucune base .stix2 trouvee : les IoC doivent etre construits.")
        stale = True
    else:
        stale = False
        for entry in stats:
            age = entry["age_hours"]
            if age is None:
                print(f"    - {entry['name']} : illisible ({entry['count']} indicateurs)")
                stale = True
                continue
            fresh = age < max_age_hours
            stale = stale or not fresh
            state = "OK" if fresh else "OBSOLETE"
            print(
                f"    - [{state}] {entry['name']} : {entry['count']} indicateurs, "
                f"age {age:.0f}h (seuil {max_age_hours}h)"
            )

    # Bases officielles MVT (si presentes) : simple recensement informatif.
    official = os.path.join(DEFAULT_MVT_INDICATORS, "*.stix2")
    official_files = glob.glob(official)
    print(f"[*] Bases officielles MVT : {len(official_files)} fichier(s) "
          f"dans {DEFAULT_MVT_INDICATORS}")
    for path in official_files:
        size = os.path.getsize(path)
        print(f"    - {os.path.basename(path)} : {size} octets")

    if stale:
        print("[!] Certaines bases sont perimees (> {}h). Lancez "
              "'build_iocs.py update'.".format(max_age_hours))
        return 1
    print("[+] Bases IOC à jour.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        default="update",
        choices=("update", "check"),
        help="Commande a executer (defaut : update).",
    )
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Hors ligne : ioc_personal.json + fichiers locaux uniquement.",
    )
    args = parser.parse_args()

    return cmd_update(args.out, dry_run=args.dry_run) if args.command == "update" \
        else cmd_check(args.out)


def _all_sources() -> List[dict]:
    """Charge la liste des sources depuis ioc_sources.json."""
    if not os.path.exists(SOURCES_FILE):
        print(f"[!] Fichier des sources introuvable : {SOURCES_FILE}")
        return []
    return load_json(SOURCES_FILE).get("sources", [])


def process_source(
    source: dict,
    content: str,
    out_dir: str,
    seen_patterns: Optional[set] = None,
) -> int:
    """Traite une source selon son type (yaml / stix2) et ecrit dans out_dir."""
    slug = slugify(source.get("name", "source"))
    out_path = os.path.join(out_dir, f"{slug}.stix2")
    stype = source.get("type", detect_type(source, content))

    if stype == "stix2":
        return write_passthrough_source(out_path, content)

    entries = indicators_from_yaml(content)
    bundle = build_stix2(entries, source.get("name", "source"), seen_patterns=seen_patterns)
    if not bundle:
        return 0
    return write_stix2(out_path, bundle)


if __name__ == "__main__":
    sys.exit(main())