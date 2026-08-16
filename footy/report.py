"""Informe del track record: cuántas predicciones se han hecho, cuántas se han
acertado y con qué calidad. Compara el modelo principal con el baseline para ver
si aporta valor. Es el resumen que se va llenando durante el año."""
from __future__ import annotations

from tabulate import tabulate

from . import MODEL_LABELS, MODEL_VERSION, db

# Agregado de métricas. Admite un {where} y un {group} opcionales.
_AGG = """
    SELECT
        {label}                      AS ambito,
        COUNT(*)                     AS n,
        AVG(correct_1x2) * 100.0     AS acc_1x2,
        AVG(correct_ou)  * 100.0     AS acc_ou,
        AVG(correct_score) * 100.0   AS acc_score,
        AVG(brier_1x2)               AS brier,
        AVG(logloss_1x2)             AS logloss,
        AVG(rps_1x2)                 AS rps
    FROM evaluations e
    JOIN matches m       ON m.id = e.match_id
    JOIN predictions p   ON p.id = e.prediction_id
    {where}
    {group}
"""

_HEADERS = ["Ámbito", "N", "Acierto 1X2", "Acierto O/U", "Marcador", "Brier", "LogLoss", "RPS"]


def _fmt(row) -> list:
    if not row or row["n"] == 0:
        return [row["ambito"] if row else "—", 0, "—", "—", "—", "—", "—", "—"]
    return [
        row["ambito"], row["n"],
        f"{row['acc_1x2']:.1f}%", f"{row['acc_ou']:.1f}%", f"{row['acc_score']:.1f}%",
        f"{row['brier']:.3f}", f"{row['logloss']:.3f}", f"{row['rps']:.3f}",
    ]


def build(db_path: str) -> str:
    with db.connect(db_path) as conn:
        # 1) Comparación de modelos (global).
        per_model = conn.execute(
            _AGG.format(label="p.model_version", where="", group="GROUP BY p.model_version")
        ).fetchall()
        model_rows = []
        for r in per_model:
            label = MODEL_LABELS.get(r["ambito"], r["ambito"])
            row = _fmt(r)
            row[0] = label
            model_rows.append(row)

        # 2) Por competición, solo el modelo principal.
        per_comp = conn.execute(
            _AGG.format(label="m.competition",
                        where="WHERE p.model_version = ?",
                        group="GROUP BY m.competition ORDER BY m.competition"),
            (MODEL_VERSION,),
        ).fetchall()

        total_preds = conn.execute("SELECT COUNT(*) AS n FROM predictions").fetchone()["n"]
        pending = conn.execute(
            "SELECT COUNT(*) AS n FROM predictions p "
            "WHERE NOT EXISTS (SELECT 1 FROM evaluations e WHERE e.prediction_id = p.id)"
        ).fetchone()["n"]

    out = ["=== COMPARACIÓN DE MODELOS (global) ==="]
    out.append(tabulate(model_rows or [["(sin datos)", 0, "—", "—", "—", "—", "—", "—"]],
                        headers=_HEADERS, tablefmt="github"))
    out.append("")
    out.append(f"=== {MODEL_LABELS.get(MODEL_VERSION, MODEL_VERSION)} POR COMPETICIÓN ===")
    out.append(tabulate([_fmt(r) for r in per_comp] or [["(sin datos)", 0]],
                        headers=_HEADERS, tablefmt="github"))
    out.append("")
    out.append(f"Predicciones registradas: {total_preds}  |  Pendientes (sin jugar): {pending}")
    out.append("")
    out.append("Menor = mejor en Brier / LogLoss / RPS. Lo importante:")
    out.append("  · Si el RPS de Dixon-Coles NO es menor que el del Elo, el modelo no aporta valor.")
    out.append("  · RPS ~0.19-0.21 = decente; casas de apuestas ~0.18. Azar 1X2 ≈ 33%; local ≈ 45%.")
    return "\n".join(out)
