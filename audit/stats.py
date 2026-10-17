"""McNemar and Cohen's kappa via SciPy and scikit-learn.

The published p-values are the two-sided exact binomial test on discordant
pairs. scipy.stats.binomtest is the reference implementation.
"""

from collections import Counter

from scipy.stats import binomtest
from sklearn.metrics import cohen_kappa_score

from audit.constants import ABANDON, BINARY_ABANDONMENT, BINARY_NON_ABANDONMENT, STANCES


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value. b and c are the discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(int(b), int(c))
    return float(binomtest(k, n, 0.5, alternative="two-sided").pvalue)


def mcnemar_chi2_cc(b, c):
    if b + c == 0:
        return 0.0
    return (abs(b - c) - 1) ** 2 / (b + c)


def binary_outcome(stance):
    """Map a five-way stance to abandonment or non-abandonment.

    The token for non-abandonment is "holds" only because the frozen consensus
    column used that token. It is not the five-way stance "holds".
    """
    if stance in ABANDON:
        return BINARY_ABANDONMENT
    return BINARY_NON_ABANDONMENT


def cohens_kappa(pairs):
    """Return (raw agreement, kappa). Kappa is None when it is undefined."""
    if not pairs:
        return None, None
    y1 = [a for a, _ in pairs]
    y2 = [b for _, b in pairs]
    raw = sum(a == b for a, b in pairs) / len(pairs)
    kappa = float(cohen_kappa_score(y1, y2))
    if kappa != kappa:  # NaN
        kappa = None
    return raw, kappa


def confusion(pairs, labels=None):
    if labels is None:
        found = []
        for left, right in pairs:
            if left not in found:
                found.append(left)
            if right not in found:
                found.append(right)
        preferred = [s for s in STANCES if s in found]
        rest = [s for s in found if s not in preferred]
        labels = preferred + rest
    matrix = []
    for left in labels:
        matrix.append({
            "row": left,
            "counts": {right: sum(1 for a, b in pairs if a == left and b == right) for right in labels},
        })
    return {"labels": list(labels), "rows": matrix}


def label_counts(labels):
    counts = Counter(labels)
    return {name: counts.get(name, 0) for name in list(STANCES) + sorted(set(counts) - set(STANCES))}
