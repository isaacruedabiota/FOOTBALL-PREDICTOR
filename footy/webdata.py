"""Genera web/public/data.json: el fichero que consume la web (PWA).

Reúne en un único JSON todo lo que el dashboard necesita: resumen por modelo,
desglose por competición, evolución temporal del acierto, próximos partidos
predichos y resultados recientes. La web lo lee con fetch('/data.json'), así que
no hay servidor que mantener: basta con regenerarlo y volver a publicarlo.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import BASELINE_VERSION, MODEL_LABELS, MODEL_VERSION, config, db

_SUMMARY = """
    SELECT
        COUNT(*)                   AS n,
        AVG(correct_1x2) * 100.0   AS acc_1x2,
        AVG(correct_ou)  * 100.0   AS acc_ou,
        AVG(correct_score) * 100.0 AS acc_score,
        AVG(brier_1x2)             AS brier,
        AVG(logloss_1x2)           AS logloss,
        AVG(rps_1x2)               AS rps
    FROM evaluations e
    JOIN predictions p ON p.id = e.prediction_id
    WHERE p.model_version = ?
"""

_SUMMARY_BY_COMP = """
    SELECT
        m.competition              AS competition,
        COUNT(*)                   AS n,
        AVG(correct_1x2) * 100.0   AS acc_1x2,
        AVG(correct_ou)  * 100.0   AS acc_ou,
        AVG(correct_score) * 100.0 AS acc_score,
        AVG(rps_1x2)               AS rps
    FROM evaluations e
    JOIN predictions p ON p.id = e.prediction_id
    JOIN matches m     ON m.id = e.match_id
    WHERE p.model_version = ?
    GROUP BY m.competition
    ORDER BY m.competition
"""

_TIMELINE = """
    SELECT m.utc_date AS utc_date, e.correct_1x2 AS correct_1x2, e.rps_1x2 AS rps
    FROM evaluations e
    JOIN predictions p ON p.id = e.prediction_id
    JOIN matches m     ON m.id = e.match_id
    WHERE p.model_version = ?
    ORDER BY m.utc_date
"""

_UPCOMING = """
    SELECT m.utc_date, m.competition, m.home_team, m.away_team,
           p.p_home, p.p_draw, p.p_away, p.pick_1x2,
           p.p_over25, p.pred_home_goals, p.pred_away_goals
    FROM predictions p
    JOIN matches m ON m.id = p.match_id
    WHERE p.model_version = ?
      AND m.status IN ('SCHEDULED','TIMED')
    ORDER BY m.utc_date
    LIMIT 40
"""

_RECENT = """
    SELECT m.utc_date, m.competition, m.home_team, m.away_team,
           p.p_home, p.p_draw, p.p_away, p.pick_1x2,
           e.actual_1x2, e.correct_1x2, e.correct_ou, e.correct_score,
           m.home_goals, m.away_goals, e.rps_1x2
    FROM evaluations e
    JOIN predictions p ON p.id = e.prediction_id
    JOIN matches m     ON m.id = e.match_id
    WHERE p.model_version = ?
    ORDER BY m.utc_date DESC
    LIMIT 30
"""


def _summary(conn, version) -> dict | None:
    r = conn.execute(_SUMMARY, (version,)).fetchone()
    if not r or r["n"] == 0:
        return None
    return {k: r[k] for k in ("n", "acc_1x2", "acc_ou", "acc_score", "brier", "logloss", "rps")}


def _round(obj, ndigits=4):
    """Redondea recursivamente los floats para un JSON más limpio."""
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: _round(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v, ndigits) for v in obj]
    return obj


def build_payload(db_path: str) -> dict:
    with db.connect(db_path) as conn:
        summary = {v: _summary(conn, v) for v in (MODEL_VERSION, BASELINE_VERSION)}

        by_comp = {}
        for v in (MODEL_VERSION, BASELINE_VERSION):
            by_comp[v] = [dict(r) for r in conn.execute(_SUMMARY_BY_COMP, (v,)).fetchall()]

        # Evolución temporal acumulada, para cada modelo (acierto y RPS).
        timeline = {}
        for v in (MODEL_VERSION, BASELINE_VERSION):
            serie = []
            hits = 0
            rps_sum = 0.0
            for i, r in enumerate(conn.execute(_TIMELINE, (v,)).fetchall(), start=1):
                hits += r["correct_1x2"]
                rps_sum += r["rps"]
                serie.append({
                    "date": r["utc_date"][:10],
                    "n": i,
                    "acc_1x2": 100.0 * hits / i,
                    "rps": rps_sum / i,
                })
            timeline[v] = serie

        upcoming = [dict(r) for r in conn.execute(_UPCOMING, (MODEL_VERSION,)).fetchall()]
        recent = [dict(r) for r in conn.execute(_RECENT, (MODEL_VERSION,)).fetchall()]

        counts = {
            "predictions": conn.execute(
                "SELECT COUNT(*) c FROM predictions WHERE model_version=?", (MODEL_VERSION,)
            ).fetchone()["c"],
            "evaluated": conn.execute(
                "SELECT COUNT(*) c FROM evaluations e JOIN predictions p ON p.id=e.prediction_id "
                "WHERE p.model_version=?", (MODEL_VERSION,)
            ).fetchone()["c"],
            "pending": conn.execute(
                "SELECT COUNT(*) c FROM predictions p WHERE p.model_version=? AND NOT EXISTS "
                "(SELECT 1 FROM evaluations e WHERE e.prediction_id=p.id)", (MODEL_VERSION,)
            ).fetchone()["c"],
        }

    payload = {
        "generated_at": db.utcnow(),
        "main_model": MODEL_VERSION,
        "baseline_model": BASELINE_VERSION,
        "labels": MODEL_LABELS,
        "summary": summary,
        "by_competition": by_comp,
        "timeline": timeline,
        "upcoming": upcoming,
        "recent": recent,
        "counts": counts,
    }
    return _round(payload)


def default_out_path() -> Path:
    return config.ROOT / "web" / "public" / "data.json"


def export_json(db_path: str, out_path: str | Path | None = None) -> Path:
    out = Path(out_path) if out_path else default_out_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(db_path)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return out
