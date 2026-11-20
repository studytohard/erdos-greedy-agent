"""Analysis routines used by the agent's research tasks."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from fractions import Fraction
from math import gcd
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .domain import (ScanResult, factorize, greedy_index, greedy_witness,
                     smallest_prime_factors, step_certificate)


# ---------------------------------------------------------------------------
# Rule validation
# ---------------------------------------------------------------------------

def rule_holds(n: int, spf: Optional[Sequence[int]] = None) -> bool:
    """The discovered two-literal rule.

    True iff every prime factor of ``n`` and of ``(n+3)//4`` is 1 mod 3.
    """
    x0 = (n + 3) // 4
    if x0 < 1:
        return False
    for m in (n, x0):
        if m < 2:
            return False
        for p in factorize(m, spf):
            if p % 3 != 1:
                return False
    return True


def validate_rule(n_max: int, spf: Sequence[int], ks: bytearray) -> dict:
    """Compare the rule with the computed greedy index on 2..n_max."""
    tp = fp = fn = tn = 0
    first_fp = None
    first_fn = None
    for n in range(2, n_max + 1):
        pred = rule_holds(n, spf)
        actual = ks[n] > 1
        if pred and actual:
            tp += 1
        elif pred and not actual:
            fp += 1
            first_fp = first_fp or n
        elif not pred and actual:
            fn += 1
            first_fn = first_fn or n
        else:
            tn += 1
    return {"n_max": n_max, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": tp / (tp + fp) if tp + fp else 1.0,
            "recall": tp / (tp + fn) if tp + fn else 1.0,
            "first_fp": first_fp, "first_fn": first_fn}


# ---------------------------------------------------------------------------
# Record certificates
# ---------------------------------------------------------------------------

def record_certificates(records: Sequence[Tuple[int, int]],
                        spf: Optional[Sequence[int]] = None,
                        max_records: int = 12) -> List[dict]:
    out = []
    for n, k in records[-max_records:]:
        steps = []
        for j in range(1, k + 1):
            c = step_certificate(n, j, spf)
            steps.append({
                "j": j, "a": c.a, "p": c.p, "x": c.x,
                "reachable": len(c.divisor_residues),
                "target": c.target, "success": c.success,
                "reason": c.reason,
            })
        j, x, y, z, d, p = greedy_witness(n, spf)
        fn = factorize(n, spf)
        out.append({
            "n": n, "k": k, "is_prime": len(fn) == 1 and next(iter(fn.values())) == 1,
            "factorization": {str(q): e for q, e in fn.items()},
            "x": x, "y": y, "z": z, "d": d, "p": p,
            "z_over_n2": z / n**2, "z_over_n3": z / n**3,
            "steps": steps,
        })
    return out


# ---------------------------------------------------------------------------
# Heights
# ---------------------------------------------------------------------------

def _witness_fast(n: int, spf: Sequence[int]) -> Tuple[int, int, int, int, int, int]:
    if n % 4 != 1:
        x = n // 4 + 1
        a = 4 * x - n
        b = n * x
        g = gcd(a, b)
        p = a // g
        q = b // g
        return 1, x, 2 * q, 2 * q, q, p
    j = greedy_index(n, spf)
    cert = step_certificate(n, j, spf)
    if cert.p == 1:
        return j, cert.x, 2 * cert.q, 2 * cert.q, cert.q, 1
    p, q = cert.p, cert.q
    divisors = [1]
    for ell, e in cert.factors.items():
        divisors = [d * ell ** k for d in divisors for k in range(2 * e + 1)]
    best = None
    for d in divisors:
        if d > q or (d + q) % p:
            continue
        y = (q + d) // p
        z = (q + q * q // d) // p
        if y < cert.x or z < y:
            continue
        if best is None or z < best[0]:
            best = (z, y, d)
    if best is None:
        raise RuntimeError((n, j))
    z, y, d = best
    assert Fraction(1, cert.x) + Fraction(1, y) + Fraction(1, z) == Fraction(4, n)
    return j, cert.x, y, z, d, p


def height_scan(n_max: int, spf: Sequence[int], sample_every: int = 50) -> dict:
    """Compute the greedy-witness height for every n <= n_max.

    Returns the largest heights, the largest ratios z/n^2 and z/n^3, counts
    above n^3 and n^4, and a sparse sample for plotting.
    """
    t0 = time.time()
    top_z: List[Tuple[int, int, int, int, int]] = []
    top_z2: List[Tuple[float, int, int, int]] = []
    top_z3: List[Tuple[float, int, int, int]] = []
    sample: List[Tuple[int, int, int]] = []
    count3 = count4 = 0
    for n in range(2, n_max + 1):
        j, x, y, z, d, p = _witness_fast(n, spf)
        if z > n**3:
            count3 += 1
        if z > n**4:
            count4 += 1
        top_z.append((z, n, j, d, p))
        top_z2.append((z / n**2, n, j, z))
        top_z3.append((z / n**3, n, j, z))
        if len(top_z) > 300:
            top_z = sorted(top_z, reverse=True)[:150]
            top_z2 = sorted(top_z2, reverse=True)[:150]
            top_z3 = sorted(top_z3, reverse=True)[:150]
        if n % sample_every == 0:
            sample.append((n, j, z))
    return {
        "n_max": n_max,
        "seconds": round(time.time() - t0, 2),
        "count_z_gt_n3": count3,
        "count_z_gt_n4": count4,
        "top_z": sorted(top_z, reverse=True)[:20],
        "top_z2": sorted(top_z2, reverse=True)[:20],
        "top_z3": sorted(top_z3, reverse=True)[:20],
        "sample": sample,
    }


# ---------------------------------------------------------------------------
# Growth fits
# ---------------------------------------------------------------------------

def fit_log_growth(points: Sequence[Tuple[int, int]]) -> dict:
    """Fit k_max(N) = a * ln(N) + b and report R^2."""
    xs = [math.log(n) for n, _ in points]
    ys = [float(k) for _, k in points]
    m = len(xs)
    mx = sum(xs) / m
    my = sum(ys) / m
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    a = sxy / sxx if sxx else 0.0
    b = my - a * mx
    ss_res = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot else 1.0
    return {"a": a, "b": b, "r2": r2,
            "points": [{"N": n, "k_max": k} for n, k in points]}
