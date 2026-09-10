"""Client de communication avec la VM sandbox (VirtualBox/Vagrant).

L'interface graphique et le CLI tournent sur l'hôte ; l'accès USB, les
extractions (AndroidQF, sauvegarde iOS) et les analyses MVT s'exécutent dans
la VM via `vagrant ssh`. Les résultats circulent par le dossier partagé
/vagrant (= racine du projet côté hôte).

Chaque commande distante exécute `scripts/sandbox_tasks.py` et retourne un
JSON sur sa dernière ligne (`RESULT_JSON {...}`).
"""
import os
import json
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VM_ROOT = "/vagrant"
VM_TASKS = "/vagrant/scripts/sandbox_tasks.py"
# L'environnement virtuel est créé DANS la VM lors du provisioning
# (le venv partagé de l'hôte n'est pas portable).
VM_PYTHON = "/opt/venv_forensics/bin/python"


class SandboxError(RuntimeError):
    pass


class SandboxClient:
    def __init__(self, root=None):
        self._root = root or SCRIPT_DIR

    # ------------------------------------------------------------ VM state
    def ensure_up(self):
        """Vérifie que la VM est démarrée. Lève SandboxError sinon."""
        try:
            res = subprocess.run(
                ["vagrant", "status", "--machine-readable"],
                cwd=self._root, capture_output=True, text=True, timeout=30,
            )
        except FileNotFoundError:
            raise SandboxError("Vagrant introuvable : installez Vagrant puis relancez `sudo ./setup.sh`.")
        except subprocess.TimeoutExpired:
            raise SandboxError("Impossible d'interroger l'état de la VM (timeout).")

        if res.returncode != 0:
            raise SandboxError("`vagrant status` a échoué : le fichier Vagrantfile est-il présent ?")

        out = res.stdout
        if ",state,running" not in out:
            raise SandboxError(
                "La VM sandbox n'est pas démarrée. Lancez `./start_analysis.sh` "
                "(ou `vagrant up`) avant de lancer une analyse."
            )
        return True

    # ------------------------------------------------------------- runner
    def run(self, subcommand, args=None, password=None, live_cb=None,
            stop_event=None, timeout=None):
        """Exécute une tâche sandbox. Retourne (returncode, stdout complet)."""
        args = args or []
        argv = [VM_PYTHON, VM_TASKS, subcommand] + [str(a) for a in args]
        # Échappement simple : les valeurs contrôlées ne contiennent pas de
        # simple quote/méta-caractère.
        safe = ""
        for tok in argv:
            safe += " '" + tok.replace("'", "'\\''") + "'"
        command = f"cd {VM_ROOT} && {safe}"

        proc = subprocess.Popen(
            ["vagrant", "ssh", "-c", command, "--",
             "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=120"],
            cwd=self._root,
            stdin=subprocess.PIPE if password is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        if password is not None:
            try:
                proc.stdin.write(password + "\n")
            finally:
                proc.stdin.close()

        chunks = []
        try:
            for line in proc.stdout:
                chunks.append(line)
                if live_cb:
                    live_cb(line.rstrip("\n"))
                if stop_event is not None and stop_event.is_set():
                    proc.terminate()
                    break
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(timeout=10)
            raise SandboxError(f"Tâche sandbox '{subcommand}' en timeout.")
        return proc.returncode, "".join(chunks)

    @staticmethod
    def last_json(stdout):
        """Extrait le RESULT_JSON final d'une sortie distante."""
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if line.startswith("RESULT_JSON "):
                try:
                    return json.loads(line[len("RESULT_JSON "):])
                except ValueError:
                    return None
        return None

    def _vm_state_text(self):
        """Interroge l'état réel de la VM (best-effort) pour le diagnostic."""
        try:
            res = subprocess.run(
                ["vagrant", "status", "--machine-readable"],
                cwd=self._root, capture_output=True, text=True, timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "indisponible"
        for line in (res.stdout or "").splitlines():
            fields = line.strip().split(",")
            if len(fields) >= 4 and fields[2] == "state":
                return fields[3]
        return "inconnu"

    # ------------------------------------------------------------- actions
    def detect_android(self):
        rc, out = self.run("detect-android")
        data = self.last_json(out) or {}
        return bool(data.get("found")), data.get("msg", "Erreur détection Android"), data.get("imei", "")

    def detect_ios(self):
        rc, out = self.run("detect-ios")
        data = self.last_json(out) or {}
        return bool(data.get("found")), data.get("msg", "Erreur détection iOS"), data.get("imei", "")

    def analyze(self, device_type, password, live_cb=None, stop_event=None, timeout=None):
        if device_type == "android":
            sub = "analyze-android"
            pwd = None
        else:
            sub = "analyze-ios"
            pwd = password or ""
        rc, out = self.run(sub, password=pwd, live_cb=live_cb,
                           stop_event=stop_event, timeout=timeout)
        data = self.last_json(out)
        if data is None:
            tail = " | ".join(out.rstrip().splitlines()[-15:]) or "(aucune sortie)"
            state = self._vm_state_text()
            raise SandboxError(
                f"Réponse de la VM invalide (rc {rc}). Dernières lignes : "
                f"{tail}. État VM : {state}. Vérifiez que la VM est démarrée "
                "(`vagrant status` / `vagrant up`) et que l'hôte ne s'est pas "
                "mis en veille pendant l'analyse."
            )
        if not data.get("ok"):
            raise SandboxError(data.get("error", "Échec de la tâche sandbox."))
        return data


def _client():
    return SandboxClient()