"""Interfaz de línea de comandos.

Uso:
    python -m footy init-db      Crea la base de datos.
    python -m footy fetch        Descarga partidos (pasados y futuros).
    python -m footy predict      Entrena y registra predicciones de los próximos partidos.
    python -m footy evaluate     Evalúa las predicciones cuyo partido ya terminó.
    python -m footy report       Muestra el histórico de aciertos y métricas.
    python -m footy export       Vuelca el histórico a track_record/track_record.csv.
    python -m footy webdata      Genera web/public/data.json para la web (PWA).
    python -m footy run          fetch -> predict -> evaluate -> export -> webdata -> report.
"""
from __future__ import annotations

import argparse
import sys

from . import __version__, config, db, evaluate, export, predict, report, webdata


def _log(msg=""):
    print(msg, flush=True)


def cmd_init_db(cfg):
    db.init_db(cfg["database_path"])
    _log(f"Base de datos lista en {cfg['database_path']}")


def cmd_fetch(cfg):
    from . import ingest  # import perezoso: no requiere red salvo aquí
    db.init_db(cfg["database_path"])
    # Temporada actual + las anteriores indicadas, para tener datos de entrenamiento.
    season = cfg["season"]
    if season is None:
        seasons = [None]
    else:
        seasons = [season - k for k in range(cfg["history_seasons"] + 1)]
    _log(f"Descargando partidos (temporadas: {seasons})...")
    ingest.fetch_all(
        cfg["database_path"], cfg["api_key"], cfg["competitions"], seasons,
        request_delay=cfg["ingest"]["request_delay_seconds"], log=_log,
    )


def cmd_predict(cfg):
    db.init_db(cfg["database_path"])
    _log("Generando predicciones...")
    n = predict.run(cfg["database_path"], cfg, log=_log)
    _log(f"Total: {n} predicciones nuevas.")


def cmd_evaluate(cfg):
    db.init_db(cfg["database_path"])
    _log("Evaluando predicciones terminadas...")
    evaluate.run(cfg["database_path"], log=_log)


def cmd_report(cfg):
    _log(report.build(cfg["database_path"]))


def cmd_export(cfg):
    out = export.default_out_path()
    n = export.export_csv(cfg["database_path"], out)
    _log(f"Exportadas {n} filas a {out}")


def cmd_webdata(cfg):
    out = webdata.export_json(cfg["database_path"])
    _log(f"Datos de la web escritos en {out}")


def cmd_run(cfg):
    """Ciclo completo pensado para ejecución programada."""
    cmd_fetch(cfg)
    cmd_predict(cfg)
    cmd_evaluate(cfg)
    cmd_export(cfg)
    cmd_webdata(cfg)
    _log("")
    cmd_report(cfg)


COMMANDS = {
    "init-db": cmd_init_db,
    "fetch": cmd_fetch,
    "predict": cmd_predict,
    "evaluate": cmd_evaluate,
    "report": cmd_report,
    "export": cmd_export,
    "webdata": cmd_webdata,
    "run": cmd_run,
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="footy", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"footy {__version__}")
    parser.add_argument("-c", "--config", default=None, help="Ruta a config.yaml")
    parser.add_argument("command", choices=list(COMMANDS), help="Acción a ejecutar")
    args = parser.parse_args(argv)

    cfg = config.load_config(args.config)
    try:
        COMMANDS[args.command](cfg)
    except Exception as exc:  # mensaje limpio en vez de traceback para errores esperables
        _log(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
