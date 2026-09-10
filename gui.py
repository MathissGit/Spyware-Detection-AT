#!/usr/bin/env python3
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import SpywareDetectionApp


def main():
    parser = argparse.ArgumentParser(description="IHM de détection de spyware")
    parser.add_argument("--mode", choices=["direct", "sandbox"], default="direct",
                        help="Mode d'exécution (défaut: direct)")
    args = parser.parse_args()

    app = SpywareDetectionApp(mode=args.mode)
    app.mainloop()


if __name__ == "__main__":
    main()