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
        # Reintentos ante errores de conexión/SSL transitorios (la API a veces
        # corta la conexión: "UNEXPECTED_EOF_WHILE_READING").
        last_exc = None
        for attempt in range(4):
            try:
                resp = self.session.get(url, params=params, timeout=30)
                if resp.status_code == 429:
                    raise RuntimeError("Límite de peticiones (429). Sube request_delay_seconds.")
                if resp.status_code == 403:
                    raise RuntimeError(
                        f"Acceso denegado a '{code}' (403). Puede no estar en el plan gratuito "
                        "o la temporada no estar disponible."
                    )
                resp.raise_for_status()
                return resp.json().get("matches", [])
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                    requests.exceptions.ChunkedEncodingError) as exc:
                last_exc = exc
                time.sleep(3 * (attempt + 1))  # espera creciente entre reintentos
        raise RuntimeError(f"No se pudo descargar '{code}' tras varios intentos: {last_exc}")


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
        "home_crest": home.get("crest"),
        "away_crest": away.get("crest"),
        "home_short": home.get("shortName"),
        "away_short": away.get("shortName"),
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
                try:
                    matches = client.competition_matches(code, season)
                except Exception as exc:
                    # Si una liga falla, se omite y se sigue con las demás (no aborta el ciclo).
                    log(f"    ⚠ Fallo en {code}-{season}: {exc}. Se omite.")
                    counts[f"{code}-{season}"] = 0
                    continue
                for raw in matches:
                    m = _normalize(raw, code, season)
                    if m["home_team_id"]:
                        db.upsert_team(conn, m["home_team_id"], m["home_team"], code,
                                       m.get("home_crest"), m.get("home_short"))
                    if m["away_team_id"]:
                        db.upsert_team(conn, m["away_team_id"], m["away_team"], code,
                                       m.get("away_crest"), m.get("away_short"))
                    db.upsert_match(conn, m)
                conn.commit()  # persistir lo descargado de esta liga antes de seguir
                counts[f"{code}-{season}"] = len(matches)
                log(f"    {len(matches)} partidos.")
    return counts
