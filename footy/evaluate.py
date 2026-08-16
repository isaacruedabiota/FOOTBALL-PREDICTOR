"""Compara cada predicción con el resultado real y guarda las métricas."""
from __future__ import annotations

from . import db, metrics


def run(db_path: str, log=print) -> int:
    n = 0
    with db.connect(db_path) as conn:
        pending = db.pending_evaluations(conn)
        for p in pending:
            hg, ag = p["home_goals"], p["away_goals"]
            actual = metrics.result_1x2(hg, ag)
            onehot = metrics.onehot_1x2(actual)
            probs = (p["p_home"], p["p_draw"], p["p_away"])

            actual_ou = "O" if (hg + ag) >= 3 else "U"
            correct_score = int(p["pred_home_goals"] == hg and p["pred_away_goals"] == ag)

            ev = {
                "prediction_id": p["id"],
                "match_id": p["match_id"],
                "evaluated_at": db.utcnow(),
                "actual_home_goals": hg,
                "actual_away_goals": ag,
                "actual_1x2": actual,
                "correct_1x2": int(p["pick_1x2"] == actual),
                "actual_ou": actual_ou,
                "correct_ou": int(p["pick_ou"] == actual_ou),
                "correct_score": correct_score,
                "brier_1x2": metrics.brier_multiclass(probs, onehot),
                "logloss_1x2": metrics.logloss(probs, onehot),
                "rps_1x2": metrics.rps(probs, onehot),
                "brier_ou": metrics.brier_binary(p["p_over25"], int(actual_ou == "O")),
            }
            db.insert_evaluation(conn, ev)
            n += 1
    log(f"  {n} predicciones evaluadas.")
    return n
