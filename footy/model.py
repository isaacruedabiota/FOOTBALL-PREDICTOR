"""Modelo Dixon-Coles (1997): Poisson bivariante con corrección de marcadores
bajos y ponderación temporal.

De un único ajuste salen los goles esperados de cada equipo (lambda_home,
lambda_away). Con ellos se construye la matriz de probabilidades de cada
marcador, y de ahí se derivan TODAS las predicciones: 1X2, más/menos 2.5 goles
y marcador exacto.

Parametrización:
    lambda_local     = exp(ataque_local  + defensa_visitante + ventaja_local)
    lambda_visitante = exp(ataque_visit.  + defensa_local)
Restricción de identificabilidad: suma de ataques = 0 (penalización).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import log

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln


def _parse_dt(iso: str) -> datetime:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _dc_tau(x, y, lam, mu, rho):
    """Corrección Dixon-Coles para los cuatro marcadores bajos (vectorizado)."""
    tau = np.ones_like(lam, dtype=float)
    m00 = (x == 0) & (y == 0)
    m01 = (x == 0) & (y == 1)
    m10 = (x == 1) & (y == 0)
    m11 = (x == 1) & (y == 1)
    tau[m00] = 1.0 - lam[m00] * mu[m00] * rho
    tau[m01] = 1.0 + lam[m01] * rho
    tau[m10] = 1.0 + mu[m10] * rho
    tau[m11] = 1.0 - rho
    return tau


@dataclass
class DixonColesModel:
    teams: list[str]
    attack: np.ndarray
    defense: np.ndarray
    home_adv: float
    rho: float
    n_matches: int

    def _idx(self, team: str) -> int | None:
        try:
            return self.teams.index(team)
        except ValueError:
            return None

    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        """(lambda_local, lambda_visitante). Equipos no vistos -> fuerza media (0)."""
        i, j = self._idx(home), self._idx(away)
        ah = self.attack[i] if i is not None else 0.0
        dh = self.defense[i] if i is not None else 0.0
        aa = self.attack[j] if j is not None else 0.0
        da = self.defense[j] if j is not None else 0.0
        lam = float(np.exp(ah + da + self.home_adv))
        mu = float(np.exp(aa + dh))
        return lam, mu

    def has_team(self, team: str) -> bool:
        return self._idx(team) is not None


def _neg_log_likelihood(params, hi, ai, hg, ag, w, n_teams):
    attack = params[:n_teams]
    defense = params[n_teams:2 * n_teams]
    home_adv = params[2 * n_teams]
    rho = params[2 * n_teams + 1]

    lam = np.exp(attack[hi] + defense[ai] + home_adv)
    mu = np.exp(attack[ai] + defense[hi])

    ll_home = hg * np.log(lam) - lam - gammaln(hg + 1.0)
    ll_away = ag * np.log(mu) - mu - gammaln(ag + 1.0)
    tau = np.clip(_dc_tau(hg, ag, lam, mu, rho), 1e-12, None)

    ll = np.sum(w * (np.log(tau) + ll_home + ll_away))
    # La verosimilitud es invariante a desplazar ataques/defensas; esta
    # penalización fija suma(ataque)=0 sin distorsionar el ajuste.
    penalty = 100.0 * attack.sum() ** 2
    return -ll + penalty


def fit(matches: list, half_life_days: float = 180.0,
        ref_date: datetime | None = None) -> DixonColesModel:
    """Ajusta el modelo a una lista de partidos terminados.

    `matches`: filas con home_team, away_team, home_goals, away_goals, utc_date.
    """
    teams = sorted({m["home_team"] for m in matches} | {m["away_team"] for m in matches})
    tindex = {t: k for k, t in enumerate(teams)}
    n = len(teams)

    hi = np.array([tindex[m["home_team"]] for m in matches])
    ai = np.array([tindex[m["away_team"]] for m in matches])
    hg = np.array([m["home_goals"] for m in matches], dtype=float)
    ag = np.array([m["away_goals"] for m in matches], dtype=float)

    ref = ref_date or datetime.now(timezone.utc)
    xi = log(2.0) / float(half_life_days)  # decaimiento exponencial por día
    days_ago = np.array([(ref - _parse_dt(m["utc_date"])).total_seconds() / 86400.0
                         for m in matches])
    days_ago = np.clip(days_ago, 0.0, None)
    w = np.exp(-xi * days_ago)

    x0 = np.concatenate([np.zeros(n), np.zeros(n), [0.25], [-0.05]])
    bounds = [(-3, 3)] * n + [(-3, 3)] * n + [(-1.0, 1.0), (-0.2, 0.2)]

    res = minimize(
        _neg_log_likelihood, x0, args=(hi, ai, hg, ag, w, n),
        method="L-BFGS-B", bounds=bounds,
        options={"maxiter": 500, "ftol": 1e-8},
    )

    p = res.x
    return DixonColesModel(
        teams=teams,
        attack=p[:n],
        defense=p[n:2 * n],
        home_adv=float(p[2 * n]),
        rho=float(p[2 * n + 1]),
        n_matches=len(matches),
    )


def score_matrix(lam: float, mu: float, rho: float, max_goals: int = 10) -> np.ndarray:
    """Matriz P[x, y] = prob. de marcador (x goles local, y goles visitante)."""
    goals = np.arange(max_goals + 1)
    # Poisson pmf sin depender de scipy.stats: exp(k*ln(l) - l - ln(k!))
    logf = gammaln(goals + 1.0)
    home = np.exp(goals * np.log(lam) - lam - logf)
    away = np.exp(goals * np.log(mu) - mu - logf)
    m = np.outer(home, away)

    m[0, 0] *= 1.0 - lam * mu * rho
    m[0, 1] *= 1.0 + lam * rho
    m[1, 0] *= 1.0 + mu * rho
    m[1, 1] *= 1.0 - rho

    m = np.clip(m, 0.0, None)
    total = m.sum()
    if total > 0:
        m /= total
    return m
