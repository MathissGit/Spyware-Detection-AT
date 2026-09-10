#!/usr/bin/env python3
"""Benchmark de l'analyse MVT : séquentiel vs parallélisé par module.

Usage :
    scripts/benchmark_mvt.py android <dump_dir> [--timeout N] [--output-prefix P]
    scripts/benchmark_mvt.py ios <backup_complet> [--timeout N] [--output-prefix P]

Mesure le temps réel (et le succès) de `run_mvt_check` pour MVT_PARALLEL
= 0 (séquentiel), 2 et 4 workers sur le même cible, puis nettoie.
"""
import argparse
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from gui import workers  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["android", "ios"])
    parser.add_argument("target", help="dump AndroidQF ou sauvegarde iOS (dossier UDID)")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--output-prefix", default="bench_mvt")
    args = parser.parse_args()

    if args.mode == "android":
        base = ["mvt-android", "check-androidqf", args.target]
    else:
        base = ["mvt-ios", "check-backup", "--fast", args.target]

    for workers_n in (0, 2, 4):
        workers.MVT_PARALLEL = workers_n
        out = f"{args.output_prefix}_p{workers_n}"
        log = f"{args.output_prefix}_p{workers_n}.txt"
        os.makedirs(out, exist_ok=True)
        t0 = time.monotonic()
        ok = workers.run_mvt_check(base, workers.IOC_FILES, out, log,
                                   timeout=args.timeout)
        dur = time.monotonic() - t0
        label = "séquentiel" if workers_n == 0 else f"{workers_n} workers"
        print(f"{label:>10} : {dur:8.1f}s  ->  ok={ok}")
        shutil.rmtree(out, ignore_errors=True)
        if os.path.exists(log):
            os.remove(log)


if __name__ == "__main__":
    main()