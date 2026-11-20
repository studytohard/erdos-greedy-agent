"""Mathematical core for the Erdős–Straus greedy-obstruction agent.

The module is deliberately dependency-free (standard library only) so that the
agent can be audited and re-run in a bare Python environment.  Optional
``sympy`` is used only for cross-checks in the test-suite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from math import gcd, isqrt
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Factorisation
# ---------------------------------------------------------------------------

def smallest_prime_factors(n: int) -> List[int]:
    """Return the SPF table for 0..n (inclusive)."""
    spf = list(range(n + 1))
    if n >= 1:
        spf[0] = 0
        spf[1] = 1
    for i in range(2, isqrt(n) + 1):
        if spf[i] == i:
            for j in range(i * i, n + 1, i):
                if spf[j] == j:
                    spf[j] = i
    return spf


def factorize(n: int, spf: Optional[Sequence[int]] = None) -> Dict[int, int]:
    """Prime factorisation as ``{prime: exponent}``.

    When ``spf`` is supplied it must cover every prime factor of ``n``; this is
    the fast path used by the range scanner.
    """
    if n < 1:
        raise ValueError("factorize expects a positive integer")
    out: Dict[int, int] = {}
    if spf is not None and n < len(spf):
        while n > 1:
            p = int(spf[n])
            if p == n:
                out[p] = out.get(p, 0) + 1
                break
            e = 0
            while n % p == 0:
                n //= p
                e += 1
            out[p] = out.get(p, 0) + e
        return out
    d = 2
    while d * d <= n:
        while n % d == 0:
            out[d] = out.get(d, 0) + 1
            n //= d
        d += 1 if d == 2 else 2
    if n > 1:
        out[n] = out.get(n, 0) + 1
    return out


def all_prime_factors_congruent(n: int, residue: int, modulus: int,
                                spf: Optional[Sequence[int]] = None) -> bool:
    """True iff every prime factor of ``n`` is ``residue`` modulo ``modulus``."""
    return all(p % modulus == residue for p in factorize(n, spf))


# ---------------------------------------------------------------------------
# The greedy step
# ---------------------------------------------------------------------------

@dataclass
class StepCertificate:
    """A verifiable explanation of one greedy step.

    For a fixed ``n`` and step index ``j`` (1-based) the greedy algorithm uses

        x_j = (n + 4j - 1) / 4          (requires n == 1 mod 4)

    and writes ``a_j = 4x_j - n = 4j - 1``.  With ``p = a_j / gcd(a_j, n x_j)``
    and ``q = n x_j / gcd(a_j, n x_j)``, a solution exists iff some divisor
    ``d`` of ``q^2`` satisfies ``d == -q (mod p)``.  The certificate below
    records the finite abelian group computation that decides this.
    """

    n: int
    j: int
    x: int
    a: int
    g: int
    p: int
    q: int
    factors: Dict[int, int]
    divisor_residues: List[int]
    target: int
    success: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "n": self.n, "j": self.j, "x": self.x, "a": self.a, "g": self.g,
            "p": self.p, "q": self.q,
            "factors": {str(k): v for k, v in self.factors.items()},
            "divisor_residues": self.divisor_residues,
            "target": self.target, "success": self.success, "reason": self.reason,
        }


def _divisor_residues(factors: Dict[int, int], p: int) -> List[int]:
    """Residues modulo ``p`` reachable as divisors of ``q^2``.

    If ``q = prod l^e`` then a divisor of ``q^2`` is ``prod l^f`` with
    ``0 <= f <= 2e``.  Dividing by ``q`` gives the equivalent condition
    ``prod l^(f-e) == -1 (mod p)`` with ``-e <= f-e <= e``.  The set below is
    the set of reachable residues of ``prod l^(f-e)``.
    """
    reachable = {1}
    for ell, e in factors.items():
        powers = [pow(ell, h, p) for h in range(-e, e + 1)]
        reachable = {(s * m) % p for s in reachable for m in powers}
        if len(reachable) == p:
            break
    return sorted(reachable)


def step_certificate(n: int, j: int,
                     spf: Optional[Sequence[int]] = None) -> StepCertificate:
    """Decide whether the ``j``-th greedy step succeeds, with a certificate."""
    if n % 4 != 1:
        raise ValueError("greedy step j is only defined for n == 1 (mod 4)")
    if j < 1:
        raise ValueError("j must be >= 1")
    x = (n + 4 * j - 1) // 4
    a = 4 * x - n
    b = n * x
    g = gcd(a, b)
    p = a // g
    q = b // g
    fn = factorize(n, spf)
    fx = factorize(x, spf)
    fg = factorize(g, spf)
    factors = dict(fn)
    for ell, e in fx.items():
        factors[ell] = factors.get(ell, 0) + e
    for ell, e in fg.items():
        factors[ell] -= e
        if factors[ell] == 0:
            del factors[ell]

    if p == 1:
        return StepCertificate(n, j, x, a, g, p, q, factors, [1], 0, True,
                               "p = 1: a_j divides n x_j, so d = q works")
    target = p - 1  # after dividing d by q, the condition is prod l^h == -1
    residues = _divisor_residues(factors, p)
    success = target in residues
    if success:
        reason = f"-1 lies in the reachable shifted divisor residues mod {p}"
    else:
        reason = f"-1 is outside the reachable shifted divisor residues mod {p}"
    return StepCertificate(n, j, x, a, g, p, q, factors, residues, target,
                           success, reason)


def _step_ok(n: int, j: int, fn: Dict[int, int],
             spf: Optional[Sequence[int]]) -> Tuple[bool, int, int, int, int]:
    """Fast existence test for one greedy step.

    Returns ``(ok, x, a, p, q)``.  ``fn`` is the factorisation of ``n``.
    """
    x = (n + 4 * j - 1) // 4
    a = 4 * j - 1
    b = n * x
    g = gcd(a, b)
    p = a // g
    if p == 1:
        return True, x, a, p, b
    q = b // g
    factors = dict(fn)
    for ell, e in factorize(x, spf).items():
        factors[ell] = factors.get(ell, 0) + e
    for ell, e in factorize(g, spf).items():
        factors[ell] -= e
        if factors[ell] == 0:
            del factors[ell]
    reachable = {1}
    for ell, e in factors.items():
        powers = [pow(ell, h, p) for h in range(-e, e + 1)]
        reachable = {(s * m) % p for s in reachable for m in powers}
        if len(reachable) == p:
            break
    return (p - 1) in reachable, x, a, p, q


def greedy_index(n: int, spf: Optional[Sequence[int]] = None,
                 max_steps: int = 4096) -> int:
    """First ``j`` for which the greedy step succeeds.

    For ``n != 1 (mod 4)`` the first step always succeeds (p = 1).  For
    ``n == 1 (mod 4)`` with ``3 | n`` it also succeeds immediately.  The
    remaining case is the interesting one.
    """
    if n < 2:
        raise ValueError("n must be >= 2")
    if n % 4 != 1:
        return 1
    if n % 3 == 0:
        return 1
    fn = factorize(n, spf)
    for j in range(1, max_steps + 1):
        if _step_ok(n, j, fn, spf)[0]:
            return j
    raise RuntimeError(f"no greedy solution found for n={n} up to {max_steps} steps")


def greedy_witness(n: int, spf: Optional[Sequence[int]] = None,
                   max_steps: int = 4096) -> Tuple[int, int, int, int, int, int]:
    """Return ``(j, x, y, z, d, p)`` for the first successful greedy step.

    The divisor ``d`` is chosen as the largest admissible divisor ``<= q``;
    this minimises the resulting ``z`` for the greedy step.
    """
    j = greedy_index(n, spf, max_steps)
    if n % 4 != 1:
        x = n // 4 + 1
        a = 4 * x - n
        b = n * x
        g = gcd(a, b)
        p = a // g
        q = b // g
        if p != 1:
            raise RuntimeError("unexpected p != 1 for n != 1 mod 4")
        return j, x, 2 * q, 2 * q, q, 1
    cert = step_certificate(n, j, spf)
    if cert.p == 1:
        d = cert.q
        y = z = 2 * cert.q
        return j, cert.x, y, z, d, cert.p
    p, q = cert.p, cert.q
    # enumerate divisors of q^2 and keep the best admissible one
    divisors = [1]
    for ell, e in cert.factors.items():
        divisors = [d * ell ** k for d in divisors for k in range(2 * e + 1)]
    best: Optional[Tuple[int, int]] = None
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
        raise RuntimeError(f"certificate claimed success but no ordered witness: n={n}, j={j}")
    z, y, d = best
    assert Fraction(1, cert.x) + Fraction(1, y) + Fraction(1, z) == Fraction(4, n)
    return j, cert.x, y, z, d, p


# ---------------------------------------------------------------------------
# Range scanning
# ---------------------------------------------------------------------------

@dataclass
class ScanResult:
    limit: int
    distribution: Dict[int, int]
    records: List[Tuple[int, int]]
    failures_j1: List[int] = field(default_factory=list)
    seconds: float = 0.0
    ks: Optional[bytearray] = None

    def to_dict(self) -> dict:
        return {
            "limit": self.limit,
            "distribution": {str(k): v for k, v in sorted(self.distribution.items())},
            "records": [{"n": n, "k": k} for n, k in self.records],
            "failures_j1": len(self.failures_j1),
            "seconds": round(self.seconds, 3),
        }

    def prefix_maxima(self, checkpoints: Iterable[int]) -> List[Tuple[int, int]]:
        """Return ``(checkpoint, max k(n) for n <= checkpoint)`` pairs."""
        if self.ks is None:
            raise ValueError("scan result has no k-array")
        out = []
        cur = 0
        cps = sorted(set(c for c in checkpoints if 2 <= c <= self.limit))
        idx = 0
        for n in range(2, self.limit + 1):
            if self.ks[n] > cur:
                cur = self.ks[n]
            while idx < len(cps) and cps[idx] == n:
                out.append((n, cur))
                idx += 1
        return out


def scan(n_max: int, spf: Optional[Sequence[int]] = None) -> ScanResult:
    """Compute ``k(n)`` for all ``2 <= n <= n_max``.

    The scan exploits the fact that only ``n == 1 (mod 4)`` with ``3 ∤ n`` can
    fail at the first step, which makes a ten-million range cheap.
    """
    import time

    t0 = time.time()
    if spf is None:
        spf = smallest_prime_factors(n_max)
    ks = bytearray(n_max + 1)
    dist: Dict[int, int] = {}
    records: List[Tuple[int, int]] = []
    failures: List[int] = []
    maxk = 0
    for n in range(2, n_max + 1):
        if n % 4 != 1 or n % 3 == 0:
            k = 1
        else:
            fn = factorize(n, spf)
            j = 1
            while not _step_ok(n, j, fn, spf)[0]:
                j += 1
                if j > 4096:
                    raise RuntimeError(f"no greedy solution for n={n}")
            k = j
        ks[n] = k
        dist[k] = dist.get(k, 0) + 1
        if k > 1:
            failures.append(n)
        if k > maxk:
            maxk = k
            if k > 1:
                records.append((n, k))
    return ScanResult(n_max, dist, records, failures, time.time() - t0, ks)
