"""Ingesta de partidos desde football-data.org (API v4) hacia la base de datos.

Documentación de la API: https://www.football-data.org/documentation/quickstart
Plan gratuito: ~10 peticiones/minuto y competiciones principales.
"""
from __future__ import annotations

import time

import requests

from . import db

BASE_URL = "https://api.football-data.org/v4"


class FootballDataClient:
    def __init__(self, api_key: str, request_delay: float = 6.5):
        if not api_key:
            raise ValueError(
                "Falta FOOTBALL_DATA_API_KEY. Copia .env.example a .env y pon tu clave "
                "(gratis en https://www.football-data.org/client/register)."
            )
        self.session = requests.Session()
        self.session.headers.update({"X-Auth-Token": api_key})
        self.request_delay = request_delay

    def competition_matches(self, code: str, season: int | None) -> list[dict]:
        params = {}
        if season is not None:
            params["season"] = season
        url = f"{BASE_URL}/competitions/{code}/matches"
        resp = self.session.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            raise RuntimeError("Límite de peticiones alcanzado (429). Sube request_delay_seconds.")
        if resp.status_code == 403:
            raise RuntimeError(
                f"Acceso denegado a '{code}' (403). Puede no estar en el plan gratuito "
                "o la temporada no estar disponible."
            )
        resp.raise_for_status()
        return resp.json().get("matches", [])


def _normalize(raw: dict, competition: str, season: int | None) -> dict:
    ft = (raw.get("score") or {}).get("fullTime") or {}
    home = raw.get("homeTeam") or {}
    away = raw.get("awayTeam") or {}
    return {
        "id": raw["id"],
        "competition": competition,
        "season": season,
        "matchday": raw.get("matchday"),
        "utc_date": raw["utcDate"],
        "status": raw.get("status", "SCHEDULED"),
        "home_team_id": home.get("id"),
        "away_team_id": away.get("id"),
        "home_team": home.get("name") or home.get("shortName") or "?",
        "away_team": away.get("name") or away.get("shortName") or "?",
        "home_goals": ft.get("home"),
        "away_goals": ft.get("away"),
        "updated_at": db.utcnow(),
    }


def fetch_all(db_path: str, api_key: str, competitions: list[str], seasons: list[int | None],
              request_delay: float = 6.5, log=print) -> dict[str, int]:
    """Descarga los partidos de cada competición y temporada, y los guarda.

    `seasons`: lista de años (la actual + las anteriores para entrenamiento).
    Devuelve el nº de partidos por 'competición-temporada'.
    """
    client = FootballDataClient(api_key, request_delay)
    counts: dict[str, int] = {}
    first = True
    with db.connect(db_path) as conn:
        for code in competitions:
            for season in seasons:
                if not first:
                    time.sleep(request_delay)  # respetar el rate limit del plan gratis
                first = False
                log(f"  Descargando {code} (temporada {season})...")
                matches = client.competition_matches(code, season)
                for raw in matches:
                    m = _normalize(raw, code, season)
                    if m["home_team_id"]:
                        db.upsert_team(conn, m["home_team_id"], m["home_team"], code)
                    if m["away_team_id"]:
                        db.upsert_team(conn, m["away_team_id"], m["away_team"], code)
                    db.upsert_match(conn, m)
                counts[f"{code}-{season}"] = len(matches)
                log(f"    {len(matches)} partidos.")
    return counts
