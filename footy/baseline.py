"""Baseline de referencia: modelo Elo + reglas ingenuas.

Sirve para responder a la pregunta clave: *¿el modelo Dixon-Coles aporta valor
frente a algo simple?* Si tu RPS no mejora al del Elo, el modelo elaborado no
está ganando nada.

- 1X2  -> ratings Elo con ventaja de local.
- O/U  -> "climatología": la tasa histórica de partidos con +2.5 goles.
- Marcador exacto -> el resultado más frecuente del histórico (típicamente 1-1).

El Elo se convierte a probabilidades Local/Empate/Visitante de forma
autoconsistente: W = puntos esperados del local (0..1); el empate es máximo
cuando el partido está igualado y se desvanece en los desequilibrios.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

K_FACTOR = 20.0       # velocidad de actualización de los ratings
HOME_ELO = 65.0       # ventaja de local, en puntos Elo
INIT_RATING = 1500.0


def _parse_key(iso: str) -> str:
    return iso  # las fechas ISO ordenan bien como texto


@dataclass
class EloBaseline:
    ratings: dict[str, float] = field(default_factory=dict)
    draw_base: float = 0.27      # prob. de empate en partido igualado (calibrada)
    over25_base: float = 0.50    # tasa histórica de +2.5 goles
    modal_score: tuple[int, int] = (1, 1)

    def rating(self, team: str) -> float:
        return self.ratings.get(team, INIT_RATING)

    def predict(self, home: str, away: str) -> dict:
        dr = self.rating(home) - self.rating(away) + HOME_ELO
        w = 1.0 / (1.0 + 10.0 ** (-dr / 400.0))         # puntos esperados del local
        p_draw = self.draw_base * (1.0 - abs(2.0 * w - 1.0))
        p_home = w - 0.5 * p_draw
        p_away = 1.0 - p_home - p_draw
        # saneo numérico
        p_home, p_draw, p_away = (max(x, 1e-6) for x in (p_home, p_draw, p_away))
        s = p_home + p_draw + p_away
        p_home, p_draw, p_away = p_home / s, p_draw / s, p_away / s

        pick_1x2 = "H" if p_home >= max(p_draw, p_away) else ("D" if p_draw >= p_away else "A")
        pick_ou = "O" if self.over25_base >= 0.5 else "U"
        return {
            "lambda_home": 0.0, "lambda_away": 0.0,  # el Elo no modela goles
            "p_home": p_home, "p_draw": p_draw, "p_away": p_away, "pick_1x2": pick_1x2,
            "p_over25": self.over25_base, "p_under25": 1.0 - self.over25_base, "pick_ou": pick_ou,
            "pred_home_goals": self.modal_score[0], "pred_away_goals": self.modal_score[1],
            "p_correct_score": 0.0,
        }


def fit(matches: list) -> EloBaseline:
    """Procesa los partidos terminados en orden cronológico y devuelve el Elo."""
    rows = sorted(matches, key=lambda m: _parse_key(m["utc_date"]))
    ratings: dict[str, float] = {}
    draws = 0
    overs = 0
    scores: Counter = Counter()

    for m in rows:
        h, a = m["home_team"], m["away_team"]
        hg, ag = m["home_goals"], m["away_goals"]
        rh = ratings.get(h, INIT_RATING)
        ra = ratings.get(a, INIT_RATING)

        expected_home = 1.0 / (1.0 + 10.0 ** (-(rh - ra + HOME_ELO) / 400.0))
        actual_home = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
        delta = K_FACTOR * (actual_home - expected_home)
        ratings[h] = rh + delta
        ratings[a] = ra - delta

        draws += int(hg == ag)
        overs += int((hg + ag) >= 3)
        scores[(hg, ag)] += 1

    n = max(len(rows), 1)
    draw_base = min(max(draws / n, 0.18), 0.35)
    over25_base = overs / n
    modal_score = scores.most_common(1)[0][0] if scores else (1, 1)
    return EloBaseline(ratings=ratings, draw_base=draw_base,
                       over25_base=over25_base, modal_score=modal_score)
