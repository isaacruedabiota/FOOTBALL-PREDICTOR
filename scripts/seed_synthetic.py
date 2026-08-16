"""Genera una liga sintética para probar el pipeline SIN API key.

Crea 12 equipos con fuerzas conocidas y una liga ida/vuelta con marcadores
deterministas (semilla fija). Los partidos ya "jugados" quedan FINISHED; los
del futuro quedan SCHEDULED (sin goles), para que el modelo los prediga.

    python scripts/seed_synthetic.py            # siembra la liga
    python scripts/seed_synthetic.py --reveal   # revela resultados de los futuros
                                                # (simula que pasa el tiempo)

Con --reveal, los SCHEDULED pasan a FINISHED con su marcador real, de modo que
`python -m footy evaluate` pueda comparar.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from footy import config, db  # noqa: E402

COMP = "SYN"
SEASON = 2026
N_TEAMS = 12
MATCHDAY_INTERVAL_DAYS = 10
HOME_ADV = 0.30


def _teams():
    # (nombre, ataque, defensa). Ataque alto marca más; defensa alta encaja menos.
    rng = np.random.default_rng(7)
    names = [f"Equipo {chr(65 + i)}" for i in range(N_TEAMS)]
    attack = rng.normal(0.0, 0.35, N_TEAMS)
    defense = rng.normal(0.0, 0.30, N_TEAMS)
    attack -= attack.mean()
    defense -= defense.mean()
    return names, attack, defense


def _round_robin(n: int):
    """Calendario ida/vuelta (método del círculo). Lista de jornadas de pares (i, j)."""
    teams = list(range(n))
    rounds = []
    for _ in range(n - 1):
        pairs = []
        for k in range(n // 2):
            a, b = teams[k], teams[n - 1 - k]
            pairs.append((a, b))
        rounds.append(pairs)
        teams.insert(1, teams.pop())
    # vuelta: mismos emparejamientos con local/visitante intercambiados
    second = [[(b, a) for (a, b) in rnd] for rnd in rounds]
    return rounds + second


def _simulate():
    names, attack, defense = _teams()
    schedule = _round_robin(N_TEAMS)
    rng = np.random.default_rng(2024)
    base = datetime.now(timezone.utc) - timedelta(days=180)

    matches = []
    mid = 1
    for md, pairs in enumerate(schedule):
        date = base + timedelta(days=md * MATCHDAY_INTERVAL_DAYS)
        for (h, a) in pairs:
            lam = float(np.exp(attack[h] - defense[a] + HOME_ADV))
            mu = float(np.exp(attack[a] - defense[h]))
            hg = int(rng.poisson(lam))
            ag = int(rng.poisson(mu))
            matches.append({
                "id": mid, "matchday": md + 1, "date": date,
                "home": names[h], "away": names[a], "home_id": 1000 + h, "away_id": 1000 + a,
                "hg": hg, "ag": ag,
            })
            mid += 1
    return matches


def seed(db_path: str, reveal: bool):
    db.init_db(db_path)
    matches = _simulate()
    now = datetime.now(timezone.utc)
    n_fin, n_sch = 0, 0
    with db.connect(db_path) as conn:
        for m in matches:
            played = m["date"] <= now
            if reveal:
                played = True  # revela todo
            row = {
                "id": m["id"], "competition": COMP, "season": SEASON, "matchday": m["matchday"],
                "utc_date": m["date"].isoformat(), "status": "FINISHED" if played else "SCHEDULED",
                "home_team_id": m["home_id"], "away_team_id": m["away_id"],
                "home_team": m["home"], "away_team": m["away"],
                "home_goals": m["hg"] if played else None,
                "away_goals": m["ag"] if played else None,
                "updated_at": db.utcnow(),
            }
            db.upsert_team(conn, m["home_id"], m["home"], COMP)
            db.upsert_team(conn, m["away_id"], m["away"], COMP)
            db.upsert_match(conn, row)
            n_fin += int(played)
            n_sch += int(not played)
    print(f"Liga sintética '{COMP}': {n_fin} jugados, {n_sch} pendientes "
          f"({'REVELADO' if reveal else 'normal'}).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reveal", action="store_true", help="Marca los futuros como jugados")
    ap.add_argument("-c", "--config", default=None)
    args = ap.parse_args()
    cfg = config.load_config(args.config)
    seed(cfg["database_path"], args.reveal)
