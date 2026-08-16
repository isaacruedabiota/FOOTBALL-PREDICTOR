"""Genera y almacena predicciones para los partidos futuros.

Regla de "congelado": para cada partido se guarda UNA sola predicción (la
primera que se hace, cuando el partido aparece como próximo). Así el registro
del año es honesto: refleja lo que el modelo predijo por adelantado, no un
ajuste a posteriori.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from . import BASELINE_VERSION, MODEL_VERSION, baseline as baseline_mod, db, model as model_mod


def _horizon_cutoff(cfg: dict) -> str:
    """Fecha ISO límite: 'ahora + predict_horizon_days'."""
    days = cfg["model"]["predict_horizon_days"]
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def markets_from_matrix(m: np.ndarray) -> dict:
    """Deriva 1X2, más/menos 2.5 y marcador más probable de la matriz de goles."""
    p_home = float(np.tril(m, -1).sum())   # local marca más (fila > columna)
    p_draw = float(np.trace(m))
    p_away = float(np.triu(m, 1).sum())

    n = m.shape[0]
    idx = np.add.outer(np.arange(n), np.arange(n))  # x + y (total de goles)
    p_over = float(m[idx >= 3].sum())
    p_under = float(m[idx <= 2].sum())

    hg, ag = np.unravel_index(int(np.argmax(m)), m.shape)
    p_score = float(m[hg, ag])

    pick_1x2 = "H" if p_home >= max(p_draw, p_away) else ("D" if p_draw >= p_away else "A")
    pick_ou = "O" if p_over >= p_under else "U"

    return {
        "p_home": p_home, "p_draw": p_draw, "p_away": p_away, "pick_1x2": pick_1x2,
        "p_over25": p_over, "p_under25": p_under, "pick_ou": pick_ou,
        "pred_home_goals": int(hg), "pred_away_goals": int(ag), "p_correct_score": p_score,
    }


def predict_competition(conn, competition: str, cfg: dict, log=print) -> int:
    """Entrena con el histórico de la competición y predice sus partidos futuros."""
    mcfg = cfg["model"]
    finished = db.finished_matches(conn, competition)
    if len(finished) < mcfg["min_matches"]:
        log(f"  {competition}: solo {len(finished)} partidos jugados "
            f"(mín. {mcfg['min_matches']}). Se omite.")
        return 0

    fitted = model_mod.fit([dict(r) for r in finished],
                           half_life_days=mcfg["half_life_days"])
    upcoming = db.upcoming_unpredicted(conn, MODEL_VERSION, competition, _horizon_cutoff(cfg))
    created_at = db.utcnow()
    n_new = 0

    for row in upcoming:
        home, away = row["home_team"], row["away_team"]
        if not (fitted.has_team(home) and fitted.has_team(away)):
            continue  # equipo sin histórico (recién ascendido); esperamos a tener datos
        lam, mu = fitted.expected_goals(home, away)
        mat = model_mod.score_matrix(lam, mu, fitted.rho, mcfg["max_goals"])
        markets = markets_from_matrix(mat)

        pred = {
            "match_id": row["id"], "model_version": MODEL_VERSION, "created_at": created_at,
            "lambda_home": lam, "lambda_away": mu, **markets,
        }
        db.insert_prediction(conn, pred)
        n_new += 1

    log(f"  {competition}: {n_new} predicciones nuevas "
        f"(modelo con {fitted.n_matches} partidos, {len(fitted.teams)} equipos).")
    return n_new


def baseline_competition(conn, competition: str, cfg: dict, log=print) -> int:
    """Genera las predicciones del baseline Elo para los mismos partidos futuros."""
    finished = db.finished_matches(conn, competition)
    if len(finished) < cfg["model"]["min_matches"]:
        return 0

    elo = baseline_mod.fit([dict(r) for r in finished])
    upcoming = db.upcoming_unpredicted(conn, BASELINE_VERSION, competition, _horizon_cutoff(cfg))
    created_at = db.utcnow()
    n_new = 0

    for row in upcoming:
        markets = elo.predict(row["home_team"], row["away_team"])
        pred = {
            "match_id": row["id"], "model_version": BASELINE_VERSION, "created_at": created_at,
            **markets,
        }
        db.insert_prediction(conn, pred)
        n_new += 1
    log(f"  {competition}: {n_new} predicciones del baseline Elo.")
    return n_new


def run(db_path: str, cfg: dict, log=print) -> int:
    total = 0
    with db.connect(db_path) as conn:
        for comp in cfg["competitions"]:
            total += predict_competition(conn, comp, cfg, log)
            baseline_competition(conn, comp, cfg, log)
    return total
