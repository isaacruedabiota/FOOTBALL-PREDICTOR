"""Punto de entrada para la ejecución programada (Programador de tareas de Windows).

Hace el ciclo completo (fetch -> predict -> evaluate -> export -> webdata ->
report), deja registro en logs/ y, si hay un remoto de GitHub configurado,
publica los datos (commit + push) para que la web (Vercel) se actualice sola.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from footy import cli  # noqa: E402


def publish() -> None:
    """Best-effort: publica web/public/data.json y el CSV si hay remoto git."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)

    try:
        if not git("remote").stdout.strip():
            print("Publicación: sin remoto git configurado; se omite.")
            return
        git("add", "web/public/data.json", "track_record/track_record.csv")
        commit = git("commit", "-m", f"datos: actualización {datetime.now():%Y-%m-%d}")
        if commit.returncode != 0:
            print("Publicación: sin cambios que publicar.")
            return
        push = git("push")
        print("Publicación: push OK." if push.returncode == 0
              else f"Publicación: fallo en push -> {push.stderr.strip()}")
    except Exception as exc:  # nunca romper la ejecución por el push
        print(f"Publicación: error -> {exc}")


def main() -> int:
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    logfile = logs / f"run_{datetime.now():%Y-%m-%d_%H%M}.log"

    class Tee:
        def __init__(self, *streams):
            self.streams = streams

        def write(self, data):
            for s in self.streams:
                s.write(data)

        def flush(self):
            for s in self.streams:
                s.flush()

    with open(logfile, "w", encoding="utf-8") as fh:
        old = sys.stdout
        sys.stdout = Tee(old, fh)
        try:
            print(f"=== Ejecución {datetime.now():%Y-%m-%d %H:%M} ===")
            code = cli.main(["run"])
            publish()
        finally:
            sys.stdout = old
    print(f"Log guardado en {logfile}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
