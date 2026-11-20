"""Generic feature construction and conjunction-rule discovery.

The learner is intentionally small and auditable: features are unary predicates
on ``n`` (residue classes and factor-residue conditions), and the hypothesis
space is conjunctions of at most four literals.  A beam search over bitmasks
finds the simplest conjunction with zero false positives and maximal recall.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from .domain import all_prime_factors_congruent, factorize


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

RESIDUE_MODULI = (3, 4, 5, 7, 8, 12)
FACTOR_MODULI = (3, 7)
FACTOR_RESIDUES = {
    3: (1, 2),
    7: (1, 2, 3, 4, 5, 6),
}


def feature_vector(n: int, spf: Sequence[int] | None = None) -> Dict[str, bool]:
    """A generic library of unary features for the integer ``n``.

    No feature mentions the greedy index or a particular failure set; the
    library only contains residue classes and "all prime factors lie in a
    residue class" predicates, applied both to ``n`` and to the first greedy
    denominator ``x0 = (n+3)//4``.
    """
    x0 = (n + 3) // 4
    feats: Dict[str, bool] = {}
    for m in RESIDUE_MODULI:
        for r in range(m):
            feats[f"n%{m}=={r}"] = (n % m == r)
    feats["3|n"] = (n % 3 == 0)
    feats["n is prime"] = (n >= 2 and len(factorize(n, spf)) == 1
                           and next(iter(factorize(n, spf).values())) == 1)
    for m in FACTOR_MODULI:
        for r in FACTOR_RESIDUES[m]:
            feats[f"all pf(n)%{m}=={r}"] = all_prime_factors_congruent(n, r, m, spf)
            if x0 >= 2:
                feats[f"all pf(x0)%{m}=={r}"] = all_prime_factors_congruent(x0, r, m, spf)
            else:
                feats[f"all pf(x0)%{m}=={r}"] = False
    return feats


# ---------------------------------------------------------------------------
# Bitmask utilities
# ---------------------------------------------------------------------------

def _mask(indices: Sequence[int], size: int) -> int:
    m = 0
    for i in indices:
        m |= 1 << i
    return m


def _popcount(x: int) -> int:
    return x.bit_count()


@dataclass
class ConjunctionRule:
    literals: List[str]
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 0.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def to_dict(self) -> dict:
        return {"literals": self.literals, "tp": self.tp, "fp": self.fp,
                "fn": self.fn, "precision": round(self.precision, 6),
                "recall": round(self.recall, 6), "f1": round(self.f1, 6)}


def learn_conjunction(features: Dict[str, List[bool]], labels: List[bool],
                      max_literals: int = 4, beam_width: int = 40) -> ConjunctionRule:
    """Beam-search a conjunction of unary literals.

    ``features`` maps a human-readable literal to a boolean column; ``labels``
    is the target column.  The search prefers zero-false-positive rules, then
    larger true-positive counts, then fewer literals.
    """
    n = len(labels)
    label_mask = _mask([i for i, y in enumerate(labels) if y], n)
    neg_label = ((1 << n) - 1) ^ label_mask
    masks = {name: _mask([i for i, v in enumerate(vals) if v], n)
             for name, vals in features.items()}
    all_mask = (1 << n) - 1

    beam: List[Tuple[int, Tuple[str, ...]]] = [(all_mask, ())]
    best: ConjunctionRule | None = None
    for depth in range(1, max_literals + 1):
        cand: List[Tuple[int, int, int, Tuple[str, ...]]] = []
        seen = set()
        for mask, lits in beam:
            for name, fm in masks.items():
                if name in lits:
                    continue
                new = mask & fm
                if new in seen:
                    continue
                seen.add(new)
                tp = _popcount(new & label_mask)
                if tp == 0:
                    continue
                fp = _popcount(new & neg_label)
                cand.append((fp, -tp, new, lits + (name,)))
        if not cand:
            break
        cand.sort(key=lambda t: (t[0], t[1], len(t[3])))
        # keep a mixture of low-FP and high-recall rules
        beam = [(m, l) for _, _, m, l in cand[:beam_width]]
        for fp, negtp, _, lits in cand:
            if fp == 0:
                rule = ConjunctionRule(list(lits), -negtp, 0,
                                       _popcount(label_mask) + negtp)
                if best is None or (rule.recall, -len(rule.literals)) > (best.recall, -len(best.literals)):
                    best = rule
        if best is not None and best.recall >= 1.0:
            break
    if best is None:
        raise RuntimeError("no conjunction with positive coverage found")
    return best


def evaluate_rule(literals: Sequence[str], features: Dict[str, List[bool]],
                  labels: List[bool]) -> ConjunctionRule:
    n = len(labels)
    mask = (1 << n) - 1
    for name in literals:
        mask &= _mask([i for i, v in enumerate(features[name]) if v], n)
    label_mask = _mask([i for i, y in enumerate(labels) if y], n)
    tp = _popcount(mask & label_mask)
    fp = _popcount(mask & ~label_mask)
    fn = _popcount(~mask & label_mask)
    return ConjunctionRule(list(literals), tp, fp, fn)
