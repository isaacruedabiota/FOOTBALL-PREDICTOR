"""Carga de configuración (config.yaml) y secretos (.env)."""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Raíz del proyecto = carpeta que contiene el paquete `footy`.
ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str | os.PathLike | None = None) -> dict:
    """Devuelve la configuración como dict, con la API key y rutas resueltas."""
    load_dotenv(ROOT / ".env")

    cfg_path = Path(path) if path else ROOT / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}

    cfg["api_key"] = os.getenv("FOOTBALL_DATA_API_KEY", "")

    db_rel = cfg.get("database", "data/footy.db")
    db_path = (ROOT / db_rel).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    cfg["database_path"] = str(db_path)

    cfg.setdefault("competitions", [])
    cfg.setdefault("season", None)
    cfg.setdefault("history_seasons", 1)
    cfg.setdefault("model", {})
    cfg["model"].setdefault("max_goals", 10)
    cfg["model"].setdefault("half_life_days", 180)
    cfg["model"].setdefault("min_matches", 30)
    cfg["model"].setdefault("predict_horizon_days", 10)
    cfg.setdefault("ingest", {})
    cfg["ingest"].setdefault("request_delay_seconds", 6.5)

    return cfg
