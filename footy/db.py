"""Capa de acceso a datos: esquema SQLite y utilidades de lectura/escritura.

Tablas:
  - teams        : equipos vistos en las competiciones.
  - matches      : todos los partidos (pasados y futuros) con su estado y goles.
  - predictions  : una fila por predicción "congelada" antes del partido.
  - evaluations  : resultado real vs predicción + métricas, cuando el partido acaba.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    competition TEXT,
    crest       TEXT,
    short_name  TEXT
);

CREATE TABLE IF NOT EXISTS matches (
    id            INTEGER PRIMARY KEY,      -- id de football-data.org
    competition   TEXT NOT NULL,
    season        INTEGER,
    matchday      INTEGER,
    utc_date      TEXT NOT NULL,            -- ISO 8601 (UTC)
    status        TEXT NOT NULL,            -- SCHEDULED/TIMED/FINISHED/...
    home_team_id  INTEGER,
    away_team_id  INTEGER,
    home_team     TEXT NOT NULL,
    away_team     TEXT NOT NULL,
    home_goals    INTEGER,                  -- NULL hasta que se juega
    away_goals    INTEGER,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id          INTEGER NOT NULL REFERENCES matches(id),
    model_version     TEXT NOT NULL,
    created_at        TEXT NOT NULL,        -- cuándo se hizo la predicción
    lambda_home       REAL NOT NULL,        -- goles esperados local
    lambda_away       REAL NOT NULL,        -- goles esperados visitante
    p_home            REAL NOT NULL,
    p_draw            REAL NOT NULL,
    p_away            REAL NOT NULL,
    pick_1x2          TEXT NOT NULL,        -- 'H' / 'D' / 'A'
    p_over25          REAL NOT NULL,
    p_under25         REAL NOT NULL,
    pick_ou           TEXT NOT NULL,        -- 'O' / 'U'
    pred_home_goals   INTEGER NOT NULL,     -- marcador más probable
    pred_away_goals   INTEGER NOT NULL,
    p_correct_score   REAL NOT NULL,
    UNIQUE(match_id, model_version)
);

CREATE TABLE IF NOT EXISTS evaluations (
    prediction_id      INTEGER PRIMARY KEY REFERENCES predictions(id),
    match_id           INTEGER NOT NULL REFERENCES matches(id),
    evaluated_at       TEXT NOT NULL,
    actual_home_goals  INTEGER NOT NULL,
    actual_away_goals  INTEGER NOT NULL,
    actual_1x2         TEXT NOT NULL,
    correct_1x2        INTEGER NOT NULL,    -- 0/1
    actual_ou          TEXT NOT NULL,
    correct_ou         INTEGER NOT NULL,
    correct_score      INTEGER NOT NULL,
    brier_1x2          REAL NOT NULL,
    logloss_1x2        REAL NOT NULL,
    rps_1x2            REAL NOT NULL,
    brier_ou           REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_comp   ON matches(competition, season);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        # Migración: añadir columnas nuevas a 'teams' si no existen.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(teams)")]
        if "crest" not in cols:
            conn.execute("ALTER TABLE teams ADD COLUMN crest TEXT")
        if "short_name" not in cols:
            conn.execute("ALTER TABLE teams ADD COLUMN short_name TEXT")


# --- Escritura de partidos / equipos --------------------------------------

def upsert_team(conn: sqlite3.Connection, team_id: int, name: str, competition: str,
                crest: str | None = None, short_name: str | None = None) -> None:
    conn.execute(
        "INSERT INTO teams(id, name, competition, crest, short_name) VALUES(?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET name=excluded.name, competition=excluded.competition, "
        "crest=COALESCE(excluded.crest, teams.crest), "
        "short_name=COALESCE(excluded.short_name, teams.short_name)",
        (team_id, name, competition, crest, short_name),
    )


def upsert_match(conn: sqlite3.Connection, m: dict) -> None:
    """Inserta o actualiza un partido. `m` con claves del esquema de matches."""
    conn.execute(
        """
        INSERT INTO matches (id, competition, season, matchday, utc_date, status,
                             home_team_id, away_team_id, home_team, away_team,
                             home_goals, away_goals, updated_at)
        VALUES (:id, :competition, :season, :matchday, :utc_date, :status,
                :home_team_id, :away_team_id, :home_team, :away_team,
                :home_goals, :away_goals, :updated_at)
        ON CONFLICT(id) DO UPDATE SET
            status     = excluded.status,
            matchday   = excluded.matchday,
            utc_date   = excluded.utc_date,
            home_goals = excluded.home_goals,
            away_goals = excluded.away_goals,
            updated_at = excluded.updated_at
        """,
        m,
    )


# --- Lecturas usadas por modelo / predicción / evaluación -----------------

def finished_matches(conn: sqlite3.Connection, competition: str | None = None) -> list[sqlite3.Row]:
    q = ("SELECT * FROM matches WHERE status IN ('FINISHED','AWARDED') "
         "AND home_goals IS NOT NULL AND away_goals IS NOT NULL")
    args: tuple = ()
    if competition:
        q += " AND competition = ?"
        args = (competition,)
    q += " ORDER BY utc_date"
    return conn.execute(q, args).fetchall()


def upcoming_unpredicted(conn: sqlite3.Connection, model_version: str,
                         competition: str, before_iso: str | None = None) -> list[sqlite3.Row]:
    """Partidos aún no jugados de una competición sin predicción registrada.

    `before_iso`: si se indica, solo los que se juegan hasta esa fecha (horizonte).
    """
    q = """
        SELECT m.* FROM matches m
        WHERE m.competition = ?
          AND m.status IN ('SCHEDULED','TIMED')
          AND NOT EXISTS (
              SELECT 1 FROM predictions p
              WHERE p.match_id = m.id AND p.model_version = ?
          )
    """
    args: list = [competition, model_version]
    if before_iso is not None:
        q += " AND m.utc_date <= ?"
        args.append(before_iso)
    q += " ORDER BY m.utc_date"
    return conn.execute(q, args).fetchall()


def pending_evaluations(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Predicciones cuyo partido ya terminó pero aún no se han evaluado."""
    return conn.execute(
        """
        SELECT p.*, m.home_goals, m.away_goals
        FROM predictions p
        JOIN matches m ON m.id = p.match_id
        WHERE m.status IN ('FINISHED','AWARDED')
          AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM evaluations e WHERE e.prediction_id = p.id)
        """
    ).fetchall()


def insert_prediction(conn: sqlite3.Connection, pred: dict) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO predictions
            (match_id, model_version, created_at, lambda_home, lambda_away,
             p_home, p_draw, p_away, pick_1x2, p_over25, p_under25, pick_ou,
             pred_home_goals, pred_away_goals, p_correct_score)
        VALUES
            (:match_id, :model_version, :created_at, :lambda_home, :lambda_away,
             :p_home, :p_draw, :p_away, :pick_1x2, :p_over25, :p_under25, :pick_ou,
             :pred_home_goals, :pred_away_goals, :p_correct_score)
        """,
        pred,
    )


def insert_evaluation(conn: sqlite3.Connection, ev: dict) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO evaluations
            (prediction_id, match_id, evaluated_at, actual_home_goals, actual_away_goals,
             actual_1x2, correct_1x2, actual_ou, correct_ou, correct_score,
             brier_1x2, logloss_1x2, rps_1x2, brier_ou)
        VALUES
            (:prediction_id, :match_id, :evaluated_at, :actual_home_goals, :actual_away_goals,
             :actual_1x2, :correct_1x2, :actual_ou, :correct_ou, :correct_score,
             :brier_1x2, :logloss_1x2, :rps_1x2, :brier_ou)
        """,
        ev,
    )
