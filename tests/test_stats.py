"""Reference checks for McNemar and kappa."""

from audit.stats import cohens_kappa, mcnemar_exact
from scipy.stats import binomtest
from sklearn.metrics import cohen_kappa_score


def test_mcnemar_matches_scipy_binomtest():
    for b, c in ((0, 0), (1, 0), (4, 26), (5, 14), (3, 3), (0, 8)):
        expected = 1.0 if b + c == 0 else float(binomtest(min(b, c), b + c, 0.5, alternative="two-sided").pvalue)
        assert mcnemar_exact(b, c) == expected


def test_published_flash_p_value():
    # 26 discordant pairs one way, 4 the other. Published approximation 0.0000594761.
    p_value = mcnemar_exact(26, 4)
    assert abs(p_value - 0.0000594761) < 5e-10
    assert p_value == float(binomtest(4, 30, 0.5, alternative="two-sided").pvalue)


def test_published_flash_lite_p_value():
    p_value = mcnemar_exact(14, 5)
    assert abs(p_value - 0.0635681) < 5e-8


def test_kappa_matches_sklearn_on_a_hand_checkable_table():
    pairs = [("holds", "holds"), ("holds", "abandons"), ("abandons", "abandons"), ("abandons", "holds")]
    raw, kappa = cohens_kappa(pairs)
    assert raw == 0.5
    assert kappa == float(cohen_kappa_score([a for a, _ in pairs], [b for _, b in pairs]))
    # po = 0.5, pe = 0.5, kappa = 0
    assert kappa == 0.0
