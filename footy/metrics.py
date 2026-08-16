"""Métricas para evaluar predicciones probabilísticas.

- accuracy : ¿acertó el resultado más probable? (lo intuitivo)
- Brier    : error cuadrático medio de las probabilidades. Menor = mejor. [0, 2] en 1X2.
- log-loss : penaliza fuerte estar seguro y fallar. Menor = mejor.
- RPS       : Ranked Probability Score, la métrica estándar en fútbol para el
             1X2 porque respeta el orden Local < Empate < Visitante. Menor = mejor.
"""
from __future__ import annotations

from math import log

# Orden fijo de clases para 1X2: Home, Draw, Away.
CLASSES_1X2 = ("H", "D", "A")


def onehot_1x2(actual: str) -> tuple[int, int, int]:
    return tuple(1 if c == actual else 0 for c in CLASSES_1X2)  # type: ignore


def result_1x2(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "H"
    if home_goals < away_goals:
        return "A"
    return "D"


def brier_multiclass(probs: tuple[float, ...], onehot: tuple[int, ...]) -> float:
    return sum((p - o) ** 2 for p, o in zip(probs, onehot))


def logloss(probs: tuple[float, ...], onehot: tuple[int, ...], eps: float = 1e-15) -> float:
    for p, o in zip(probs, onehot):
        if o == 1:
            return -log(min(max(p, eps), 1.0))
    return 0.0


def rps(probs: tuple[float, ...], onehot: tuple[int, ...]) -> float:
    """Ranked Probability Score para categorías ordenadas."""
    r = len(probs)
    cum_p = 0.0
    cum_o = 0.0
    total = 0.0
    for i in range(r - 1):
        cum_p += probs[i]
        cum_o += onehot[i]
        total += (cum_p - cum_o) ** 2
    return total / (r - 1)


def brier_binary(p_event: float, occurred: int) -> float:
    return (p_event - occurred) ** 2
