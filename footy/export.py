"""Exporta el histórico de predicciones a un CSV versionable y abrible en Excel.

A diferencia de la base de datos SQLite (binaria, no apta para git), el CSV
permite ver los cambios en cada commit y llevar el track record del año bajo
control de versiones.
"""
from __future__ import annotations

import csv
from pathlib import Path

from . import config, db

COLUMNS = [
    "match_id", "competition", "season", "matchday", "utc_date",
    "home_team", "away_team", "model_version", "created_at",
    "p_home", "p_draw", "p_away", "pick_1x2",
    "p_over25", "pick_ou", "pred_home_goals", "pred_away_goals",
    "status", "home_goals", "away_goals",
    "actual_1x2", "correct_1x2", "actual_ou", "correct_ou", "correct_score",
    "brier_1x2", "logloss_1x2", "rps_1x2",
]

_QUERY = """
    SELECT
        m.id AS match_id, m.competition, m.season, m.matchday, m.utc_date,
        m.home_team, m.away_team, p.model_version, p.created_at,
        p.p_home, p.p_draw, p.p_away, p.pick_1x2,
        p.p_over25, p.pick_ou, p.pred_home_goals, p.pred_away_goals,
        m.status, m.home_goals, m.away_goals,
        e.actual_1x2, e.correct_1x2, e.actual_ou, e.correct_ou, e.correct_score,
        e.brier_1x2, e.logloss_1x2, e.rps_1x2
    FROM predictions p
    JOIN matches m       ON m.id = p.match_id
    LEFT JOIN evaluations e ON e.prediction_id = p.id
    ORDER BY m.utc_date, m.id, p.model_version
"""


def export_csv(db_path: str, out_path: str | Path) -> int:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with db.connect(db_path) as conn:
        rows = conn.execute(_QUERY).fetchall()
    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r[c] for c in COLUMNS})
    return len(rows)


def default_out_path() -> Path:
    return config.ROOT / "track_record" / "track_record.csv"
