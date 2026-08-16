"""Tests del modelo, los mercados derivados y las métricas."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from footy import metrics, model
from footy.predict import markets_from_matrix


def test_score_matrix_is_a_distribution():
    m = model.score_matrix(1.4, 1.1, -0.05, max_goals=10)
    assert m.shape == (11, 11)
    assert m.min() >= 0
    assert abs(m.sum() - 1.0) < 1e-9


def test_markets_sum_to_one():
    m = model.score_matrix(1.6, 1.0, -0.03, max_goals=10)
    mk = markets_from_matrix(m)
    assert abs(mk["p_home"] + mk["p_draw"] + mk["p_away"] - 1.0) < 1e-9
    assert abs(mk["p_over25"] + mk["p_under25"] - 1.0) < 1e-9
    assert mk["pick_1x2"] in ("H", "D", "A")
    assert mk["pick_ou"] in ("O", "U")


def test_stronger_home_team_favoured():
    strong = model.score_matrix(2.2, 0.7, -0.05)
    mk = markets_from_matrix(strong)
    assert mk["p_home"] > mk["p_away"]
    assert mk["pick_1x2"] == "H"


def _synthetic_matches(n_days=200):
    """Dos equipos: A muy fuerte, B flojo. A debería salir con más ataque."""
    rng = np.random.default_rng(0)
    base = datetime.now(timezone.utc) - timedelta(days=n_days)
    rows = []
    for k in range(120):
        date = base + timedelta(days=k)
        if k % 2 == 0:
            home, away, lam, mu = "A", "B", 2.4, 0.6
        else:
            home, away, lam, mu = "B", "A", 1.0, 1.6
        rows.append({
            "home_team": home, "away_team": away,
            "home_goals": int(rng.poisson(lam)), "away_goals": int(rng.poisson(mu)),
            "utc_date": date.isoformat(),
        })
    return rows


def test_fit_recovers_relative_strength():
    fitted = model.fit(_synthetic_matches(), half_life_days=365)
    ia = fitted.teams.index("A")
    ib = fitted.teams.index("B")
    assert fitted.attack[ia] > fitted.attack[ib]      # A ataca mejor
    assert fitted.home_adv > 0                          # hay ventaja de local
    lam, mu = fitted.expected_goals("A", "B")
    assert lam > mu                                      # A local favorito


def test_unknown_team_is_average():
    fitted = model.fit(_synthetic_matches(), half_life_days=365)
    assert not fitted.has_team("Desconocido")
    lam, mu = fitted.expected_goals("Desconocido", "Otro")
    assert lam > 0 and mu > 0                            # no revienta


# --- Métricas ---

def test_rps_perfect_vs_wrong():
    # Predicción perfecta (prob 1 al resultado real) -> RPS 0
    assert metrics.rps((1, 0, 0), metrics.onehot_1x2("H")) == 0.0
    # Predicción totalmente equivocada -> RPS máximo (1.0 con 3 clases ordenadas)
    assert metrics.rps((0, 0, 1), metrics.onehot_1x2("H")) == pytest.approx(1.0)


def test_brier_and_logloss_bounds():
    oh = metrics.onehot_1x2("D")
    assert metrics.brier_multiclass((1 / 3, 1 / 3, 1 / 3), oh) == pytest.approx(2 / 3)
    # log-loss de una predicción uniforme = ln(3)
    assert metrics.logloss((1 / 3, 1 / 3, 1 / 3), oh) == pytest.approx(np.log(3))


def test_result_1x2():
    assert metrics.result_1x2(2, 0) == "H"
    assert metrics.result_1x2(1, 1) == "D"
    assert metrics.result_1x2(0, 3) == "A"
