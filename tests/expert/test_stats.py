"""Agreement statistics against published worked examples and limiting cases."""

from __future__ import annotations

import math
import random

import pytest

from ezhuthu.expert.stats import (
    cluster_bootstrap_ci,
    cohen_kappa,
    fleiss_kappa,
    percent_agreement,
    sign_test_p,
    spearman,
)


def test_cohen_kappa_textbook_example():
    # 50 units: both yes 20, A yes/B no 5, A no/B yes 10, both no 15 -> p_o 0.7, p_e 0.5, kappa 0.4
    a = ["y"] * 20 + ["y"] * 5 + ["n"] * 10 + ["n"] * 15
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert cohen_kappa(a, b) == pytest.approx(0.4)
    assert percent_agreement(a, b) == pytest.approx(0.7)


def test_cohen_kappa_limits_and_weights():
    x = [1, 2, 3, 4, 4, 3, 2, 1]
    assert cohen_kappa(x, x, categories=[1, 2, 3, 4]) == pytest.approx(1.0)
    assert cohen_kappa(x, x, categories=[1, 2, 3, 4], weights="quadratic") == pytest.approx(1.0)
    # with two categories, linear and quadratic weights equal the unweighted kappa
    a, b = [1, 1, 2, 2, 1, 2, 1, 1], [1, 2, 2, 2, 1, 1, 1, 2]
    k = cohen_kappa(a, b, categories=[1, 2])
    assert cohen_kappa(a, b, categories=[1, 2], weights="quadratic") == pytest.approx(k)
    assert cohen_kappa(a, b, categories=[1, 2], weights="linear") == pytest.approx(k)
    # near misses are penalised less with weights: 1 vs 2 disagreements only
    a, b = [1, 2, 3, 4] * 5, [2, 2, 3, 3] * 5
    assert cohen_kappa(a, b, categories=[1, 2, 3, 4], weights="quadratic") > cohen_kappa(a, b, categories=[1, 2, 3, 4])
    # both raters always say the same single category: undefined
    assert math.isnan(cohen_kappa([3, 3, 3], [3, 3, 3], categories=[1, 2, 3, 4]))
    with pytest.raises(ValueError):
        cohen_kappa([1, 2], [1])


def test_cohen_kappa_quadratic_hand_computed():
    # four units over categories 1..3: units (1,1), (2,3), (3,2), (3,3); weights ((i-j)/2)^2
    a, b = [1, 2, 3, 3], [1, 3, 2, 3]
    # observed disagreement: two cells with weight 0.25, each 1/4 -> 0.125
    # marginals (1/4, 1/4, 1/2) for both; expected = sum w_ij pa_i pb_j
    #   |i-j| = 1: 2 * 0.25 * (1/16) + 2 * 0.25 * (1/8) = 0.09375 ; |i-j| = 2: 2 * 1 * (1/8) = 0.25 -> 0.34375
    assert cohen_kappa(a, b, categories=[1, 2, 3], weights="quadratic") == pytest.approx(1 - 0.125 / 0.34375)


def test_fleiss_kappa_fleiss_1971_worked_example():
    # Wikipedia / Fleiss (1971): 10 subjects, 14 raters, 5 categories -> kappa 0.210
    table = [
        [0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1],
        [7, 7, 0, 0, 0], [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7],
    ]
    units = [[c for c, n in enumerate(row) for _ in range(n)] for row in table]
    r = fleiss_kappa(units, categories=range(5))
    assert r["p_observed"] == pytest.approx(0.378, abs=1e-3)
    assert r["p_expected"] == pytest.approx(0.213, abs=1e-3)
    assert r["kappa"] == pytest.approx(0.210, abs=1e-3)
    assert r["units"] == 10 and r["ratings"] == 140


def test_fleiss_kappa_perfect_random_and_variable_raters():
    assert fleiss_kappa([[1, 1, 1], [2, 2, 2], [4, 4, 4]])["kappa"] == pytest.approx(1.0)
    rng = random.Random(7)
    units = [[rng.randint(1, 4) for _ in range(4)] for _ in range(3000)]
    assert abs(fleiss_kappa(units, categories=[1, 2, 3, 4])["kappa"]) < 0.03
    # variable rater counts: single-rating units are dropped, perfect agreement stays 1
    r = fleiss_kappa([[1, 1], [2, 2, 2], [3], [4, 4, 4, 4]])
    assert r["units"] == 3 and r["kappa"] == pytest.approx(1.0)
    # two raters: Fleiss equals Scott's pi; with equal marginals it equals Cohen's kappa
    a, b = [1, 2, 1, 2, 1, 2], [2, 1, 1, 2, 1, 2]
    assert fleiss_kappa(list(zip(a, b, strict=True)))["kappa"] == pytest.approx(cohen_kappa(a, b))
    assert math.isnan(fleiss_kappa([])["kappa"])


def test_spearman_sign_test_bootstrap():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert spearman([1, 2, 2, 3], [1, 2, 2, 3]) == pytest.approx(1.0)  # ties
    assert math.isnan(spearman([1, 2], [1, 2]))
    assert sign_test_p(5, 0) == pytest.approx(0.0625)
    assert sign_test_p(3, 3) == pytest.approx(1.0)
    assert math.isnan(sign_test_p(0, 0))
    vals = [(f"c{i % 10}", float(i % 4)) for i in range(200)]
    lo, hi = cluster_bootstrap_ci(vals, n_boot=500)
    m = sum(v for _, v in vals) / len(vals)
    assert lo <= m <= hi
    assert all(math.isnan(x) for x in cluster_bootstrap_ci([("one", 1.0), ("one", 2.0)]))
