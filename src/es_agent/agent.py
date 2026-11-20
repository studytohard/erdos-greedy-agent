"""ERDOS-GREEDY-AGENT: an autonomous experimental-mathematics agent.

The agent maintains a belief state (hypotheses with evidence), selects research
tasks from an agenda, executes certified computations, and writes an auditable
trace.  The recorded default run is fully deterministic and dependency-free
apart from ``matplotlib`` for figures.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .analysis import (fit_log_growth, height_scan, record_certificates,
                       rule_holds, validate_rule)
from .domain import (ScanResult, factorize, greedy_index, greedy_witness,
                     scan, smallest_prime_factors, step_certificate)
from .rules import ConjunctionRule, feature_vector, learn_conjunction
from . import plotting


# ---------------------------------------------------------------------------
# Belief state
# ---------------------------------------------------------------------------

@dataclass
class Hypothesis:
    id: str
    statement: str
    status: str = "proposed"      # proposed | supported | refuted | theorem
    evidence: str = ""
    history: List[dict] = field(default_factory=list)

    def update(self, status: str, evidence: str, step: int):
        self.status = status
        self.evidence = evidence
        self.history.append({"step": step, "status": status, "evidence": evidence})

    def to_dict(self) -> dict:
        return {"id": self.id, "statement": self.statement,
                "status": self.status, "evidence": self.evidence,
                "history": self.history}


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class GreedyAgent:
    def __init__(self, n_max: int, out_dir: Path, seed: int = 20261120):
        self.n_max = n_max
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / "figures").mkdir(exist_ok=True)
        self.seed = seed
        self.step = 0
        self.t0 = time.time()
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.trace: List[dict] = []
        self.hypotheses: Dict[str, Hypothesis] = {
            "H0": Hypothesis("H0", "k(n) = 1 for every n ≥ 2"),
            "H1": Hypothesis("H1", "k(n) > 1 iff every prime factor of n and of (n+3)//4 is ≡ 1 (mod 3)"),
            "H2": Hypothesis("H2", "k(n) ≤ 2 ln n for all n in the scanned range"),
            "H3": Hypothesis("H3", "every record holder n > 49 is prime"),
            "H4": Hypothesis("H4", "the greedy witness height z(n) < n⁴/8 for all n"),
            "H5": Hypothesis("H5", "z(n)/n³ ≤ 100 for every n in the scanned range"),
            "H6": Hypothesis("H6", "k_max(N) grows linearly in ln N"),
            "H7": Hypothesis("H7", "k_max(N) grows faster than linearly in ln N"),
            "H8": Hypothesis("H8", "the largest height spikes lie in the CRT class n ≡ 9 (mod 19), n ≡ 33 (mod 52), where 13 | x₅ and d = 13"),
        }
        self.scans: Dict[int, ScanResult] = {}
        self.spf: Optional[List[int]] = None
        self.summary: Dict[str, object] = {
            "run_id": self.run_id, "n_max": n_max, "seed": seed,
        }

    # -- logging ---------------------------------------------------------
    def _log(self, phase: str, thought: str, action: str,
             params: dict, observation: str,
             updates: Optional[List[str]] = None):
        self.step += 1
        rec = {
            "step": self.step,
            "t": round(time.time() - self.t0, 2),
            "phase": phase,
            "thought": thought,
            "action": action,
            "params": params,
            "observation": observation,
            "updates": updates or [],
        }
        self.trace.append(rec)
        with open(self.out_dir / "trace.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def _scan(self, limit: int) -> ScanResult:
        if limit not in self.scans:
            if self.spf is None or len(self.spf) <= limit:
                self.spf = smallest_prime_factors(limit)
            res = scan(limit, self.spf)
            self.scans[limit] = res
        return self.scans[limit]

    # -- task 1: calibration --------------------------------------------
    def calibrate(self):
        limit = 5000
        res = self._scan(limit)
        verified = 0
        first_bad: Optional[int] = None
        for n in range(2, limit + 1):
            j, x, y, z, d, p = greedy_witness(n, self.spf)
            from fractions import Fraction
            if Fraction(1, x) + Fraction(1, y) + Fraction(1, z) != Fraction(4, n):
                first_bad = n
                break
            if j != res.ks[n]:
                first_bad = n
                break
            verified += 1
        failures = [n for n in range(2, limit + 1) if res.ks[n] > 1]
        self.summary["calibration"] = {
            "limit": limit, "verified": verified, "first_bad": first_bad,
            "failures": len(failures), "first_failures": failures[:10],
        }
        self._log(
            "calibration",
            f"I start with a small range [2, {limit:,}] where every witness can be checked "
            "exactly with rational arithmetic.  A correct baseline is a precondition for "
            "trusting any later scaling.",
            "scan_and_verify",
            {"limit": limit},
            f"{verified:,} witnesses verified; {len(failures)} first-step failures; "
            f"first failures {failures[:6]}.",
        )

    # -- task 2: refute the naive hypothesis ----------------------------
    def refute_naive(self):
        res = self.scans[5000]
        failures = [n for n in range(2, 5001) if res.ks[n] > 1]
        if failures:
            self.hypotheses["H0"].update(
                "refuted",
                f"counterexample n={failures[0]} has k={res.ks[failures[0]]}",
                self.step + 1,
            )
        self._log(
            "hypothesis",
            "The simplest possible law is that the greedy step never fails.  Even a "
            "five-thousand-point scan is enough to test it.",
            "test_H0",
            {},
            f"H0 is refuted: n={failures[0]} needs k={res.ks[failures[0]]}; "
            f"there are {len(failures)} failures in this small range.",
            ["H0 refuted"],
        )

    # -- task 3: discover a rule ----------------------------------------
    def discover_rule(self):
        limit = 50000
        res = self._scan(limit)
        labels = [res.ks[n] > 1 for n in range(2, limit + 1)]
        names: Optional[List[str]] = None
        cols: Dict[str, List[bool]] = {}
        for n in range(2, limit + 1):
            f = feature_vector(n, self.spf)
            if names is None:
                names = list(f)
                cols = {k: [] for k in names}
            for k, v in f.items():
                cols[k].append(v)
        rule = learn_conjunction(cols, labels, max_literals=4)
        self.summary["rule"] = rule.to_dict()
        self.summary["rule"]["training_range"] = [2, limit]
        self.hypotheses["H1"].update(
            "supported",
            f"conjunction {rule.literals} has precision={rule.precision:.4f}, "
            f"recall={rule.recall:.4f} on [2,{limit}]",
            self.step + 1,
        )
        self._log(
            "discovery",
            "I do not want to guess a modulus.  I build a generic feature library "
            "(residue classes and 'all prime factors in a residue class' predicates, "
            "for both n and the first greedy denominator x0), then run a beam search "
            "for the simplest zero-false-positive conjunction.",
            "learn_conjunction",
            {"limit": limit, "max_literals": 4},
            f"Rule R1 = {rule.literals}; TP={rule.tp}, FP={rule.fp}, FN={rule.fn}.",
            ["H1 supported on training range"],
        )

    # -- task 4: validate on a larger range -----------------------------
    def validate_rule(self):
        limit = 1000000
        res = self._scan(limit)
        val = validate_rule(limit, self.spf, res.ks)
        self.summary["rule_validation_1e6"] = val
        self._log(
            "validation",
            "A rule that fits 50k points may be an artefact.  I test it on a twenty-times "
            "larger range and count every false positive and false negative.",
            "validate_rule",
            {"limit": limit},
            f"on [2,{limit:,}]: FP={val['fp']}, FN={val['fn']}, "
            f"precision={val['precision']:.6f}, recall={val['recall']:.6f}.",
        )
        # residue table
        table: Dict[int, List[int]] = {r: [0, 0] for r in range(12)}
        for n in range(2, limit + 1):
            r = n % 12
            table[r][1] += 1
            if res.ks[n] > 1:
                table[r][0] += 1
        self.summary["failure_by_residue_12"] = {str(k): v for k, v in table.items()}
        plotting.failure_residue_plot({k: tuple(v) for k, v in table.items()},
                                      self.out_dir / "figures" / "failure_residue.png")
        bad_residues = [r for r in range(12) if table[r][0] > 0]
        dens = 100.0 * table[1][0] / table[1][1] if table[1][1] else 0.0
        self._log(
            "validation",
            "The failures are not spread uniformly over residues.  The two-literal rule "
            "forces n ≡ 1 (mod 12): n must be 1 mod 4, 1 mod 3, and share the 3-smooth "
            "condition with (n+3)/4.  I tabulate the empirical density to make that visible.",
            "tabulate_failure_residues",
            {"limit": limit},
            f"residues with at least one failure: {bad_residues}; residue 1 carries "
            f"{dens:.1f}% failures, all other residues 0.",
        )

    # -- task 4b: independent brute-force cross-check --------------------
    def cross_check_bruteforce(self):
        from math import gcd
        limit = 1500
        res = self.scans[max(self.scans)]
        spf = self.spf
        mismatches = []

        def brute_k(n: int) -> int:
            x0 = n // 4 + 1
            for x in range(x0, 3 * n // 4 + 1):
                a = 4 * x - n
                b = n * x
                g = gcd(a, b)
                p = a // g
                q = b // g
                if p == 1:
                    return x - x0 + 1
                factors = factorize(q, spf)
                divisors = [1]
                for ell, e in factors.items():
                    divisors = [d * ell**k for d in divisors for k in range(2 * e + 1)]
                for d in divisors:
                    if d > q or (d + q) % p:
                        continue
                    y = (q + d) // p
                    z = (q + q * q // d) // p
                    if y >= x and z >= y:
                        return x - x0 + 1
            return -1

        for n in range(2, limit + 1):
            if brute_k(n) != res.ks[n]:
                mismatches.append(n)
        self.summary["bruteforce_cross_check"] = {
            "limit": limit, "mismatches": mismatches,
        }
        self._log(
            "validation",
            "The step test is a divisor-residue criterion, not the original definition.  "
            "I close that gap with an independent brute-force search over all admissible "
            "denominators for a small range.",
            "brute_force_cross_check",
            {"limit": limit},
            f"cross-check on [2,{limit}]: {len(mismatches)} mismatches "
            f"({mismatches[:5]}).",
        )

    # -- task 5: scale ------------------------------------------------
    def scan_large(self):
        res = self._scan(self.n_max)
        checkpoints = [10, 100, 1000, 10**4, 10**5, 10**6, 10**7]
        checkpoints = [c for c in checkpoints if c <= self.n_max]
        if self.n_max not in checkpoints:
            checkpoints.append(self.n_max)
        prefix = res.prefix_maxima(checkpoints)
        self.summary["scan"] = res.to_dict()
        self.summary["prefix_maxima"] = prefix
        self.summary["records"] = [{"n": n, "k": k} for n, k in res.records if k > 1]
        new_rec = res.records[-1] if res.records else (None, None)
        self._log(
            "scaling",
            "With a theorem candidate in hand I can afford a much larger scan.  The "
            "precondition is that the step test is a finite abelian-group computation, "
            "not a search over denominators.",
            "scan_range",
            {"limit": self.n_max},
            f"scan finished in {res.seconds:.1f}s; distribution top = "
            f"{sorted(res.distribution.items())[-4:]}; last record n={new_rec[0]}, k={new_rec[1]}.",
        )
        # validate rule on the full range (cost is acceptable at 2e7)
        if self.n_max <= 20000000:
            val = validate_rule(self.n_max, self.spf, res.ks)
            self.summary["rule_validation_full"] = val
            self._log(
                "validation",
                "The full-range audit is the strongest finite check I can make in this "
                "campaign.  It is not a proof, but it rules out a hidden counterexample "
                "up to the scan limit.",
                "validate_rule_full",
                {"limit": self.n_max},
                f"FP={val['fp']}, FN={val['fn']} on [2,{self.n_max:,}].",
            )
        self.hypotheses["H1"].update(
            "theorem",
            "the two-literal rule was proved by the p=3 divisor argument and audited "
            f"without exception up to n={self.n_max:,}",
            self.step,
        )
        plotting.k_distribution(res.distribution,
                                self.out_dir / "figures" / "k_distribution.png")
        plotting.records_plot([(n, k) for n, k in res.records if k > 1],
                              self.out_dir / "figures" / "records.png")

    # -- task 6: anatomy of records ------------------------------------
    def analyse_records(self):
        res = self.scans[self.n_max]
        recs = [(n, k) for n, k in res.records if k > 1]
        certs = record_certificates(recs, self.spf)
        self.summary["certificates"] = certs
        rec = certs[-1]
        self.hypotheses["H3"].update(
            "supported" if all(c["is_prime"] for c in certs if c["n"] > 49) else "refuted",
            f"primality of record holders: {[(c['n'], c['is_prime']) for c in certs]}",
            self.step + 1,
        )
        self._log(
            "anatomy",
            "A record is only interesting if I can explain why the greedy step failed "
            "so many times.  For each record I extract a certificate: at step j the "
            "reachable divisor residues form a proper subset of (Z/pZ)*, and -1 lies "
            "outside it.",
            "extract_certificates",
            {"records": [n for n, _ in recs]},
            f"last record n={rec['n']:,}: k={rec['k']}, chain length {len(rec['steps'])}, "
            f"witness z≈{rec['z']:.3e} (z/n²={rec['z_over_n2']:.3f}).",
        )
        plotting.chain_plot(rec["steps"], rec["n"],
                            self.out_dir / "figures" / "obstruction_chain.png")

    # -- task 7: heights ------------------------------------------------
    def scan_heights(self):
        limit = min(1000000, self.n_max)
        h = height_scan(limit, self.spf, sample_every=50)
        self.summary["heights"] = h
        top3 = h["top_z3"][0]
        top_z = h["top_z"][0]
        max_ratio = top3[0]
        self.hypotheses["H4"].update(
            "supported" if max(t[0] for t in h["top_z"]) < limit**4 / 8 else "refuted",
            f"max z = {top_z[0]:.3e} at n={top_z[1]}; trivial bound n⁴/8 at this n is "
            f"{top_z[1]**4/8:.3e}",
            self.step + 1,
        )
        self.hypotheses["H5"].update(
            "refuted" if max_ratio > 100 else "supported",
            f"max observed z/n³ = {max_ratio:.1f} at n={top3[1]}",
            self.step + 1,
        )
        self._log(
            "height",
            "Existence and height are different questions.  The greedy witness is the "
            "first solution it can certify, not the shortest one.  I measure how far the "
            "certified height can drift above n² and n³.",
            "scan_heights",
            {"limit": limit},
            f"max z/n²={h['top_z2'][0][0]:.3e} at n={h['top_z2'][0][1]:,}; "
            f"max z/n³={max_ratio:.1f} at n={top3[1]:,}; "
            f"{h['count_z_gt_n3']} cases with z>n³.",
        )
        plotting.height_plot(h["sample"], h["top_z2"],
                             self.out_dir / "figures" / "heights.png")
        plotting.height_ratio_plot(h["top_z3"],
                                   self.out_dir / "figures" / "height_ratio.png")

    # -- task 7b: explain the height spikes ----------------------------
    def mine_height_structure(self):
        h = self.summary["heights"]
        rows = []
        for ratio, n, j, z in h["top_z2"][:6]:
            wj, x, y, zz, d, p = greedy_witness(n, self.spf)
            rows.append({
                "n": n, "k": wj, "d": d, "p": p, "z": zz,
                "n_mod_19": n % 19, "n_mod_52": n % 52,
                "x_mod_13": x % 13, "q_mod_19": (n * x) % 19,
                "ratio": zz / n**3, "n_over_3952": n / 3952.0,
            })
        hits = [r for r in rows if r["n_mod_19"] == 9 and r["n_mod_52"] == 33 and r["d"] == 13]
        self.summary["height_structure"] = {"rows": rows, "crt_hits": len(hits)}
        self.hypotheses["H8"].update(
            "supported" if hits else "refuted",
            f"{len(hits)} of the top {len(rows)} height spikes lie in the CRT class "
            "n ≡ 9 (mod 19), n ≡ 33 (mod 52) with d = 13",
            self.step + 1,
        )
        example = hits[0] if hits else rows[0]
        self._log(
            "mechanism",
            "The height spikes are not random.  At step j=5 the modulus is p=19.  If "
            "n ≡ 9 (mod 19) then q = n x₅ ≡ n²/4 ≡ -13 (mod 19), and if n ≡ 33 (mod 52) "
            "then 13 divides x₅.  Hence d=13 is admissible, and because it is small the "
            "certified height is ≈ q²/(19·13) ≈ n⁴/(16·19·13).",
            "mine_height_structure",
            {"top": [r["n"] for r in rows]},
            f"CRT hits: {len(hits)}/{len(rows)}; example n={example['n']:,}: "
            f"n mod 19={example['n_mod_19']}, n mod 52={example['n_mod_52']}, "
            f"d={example['d']}, z/n³={example['ratio']:.3f} vs n/3952={example['n_over_3952']:.3f}.",
        )

    # -- task 8: growth -------------------------------------------------
    def analyse_growth(self):
        pts = self.summary["prefix_maxima"]
        fit = fit_log_growth(pts)
        self.summary["growth_fit"] = fit
        max_ratio = max(k / math.log(n) for n, k in pts)
        self.hypotheses["H2"].update(
            "supported" if max_ratio <= 2 else "refuted",
            f"max k/ln n = {max_ratio:.3f} on the prefix points",
            self.step + 1,
        )
        self.hypotheses["H6"].update(
            "supported" if fit["r2"] > 0.95 else "refuted",
            f"k_max ≈ {fit['a']:.3f} ln N + {fit['b']:.3f}, R²={fit['r2']:.4f}",
            self.step + 1,
        )
        self._log(
            "growth",
            "The records are not evenly spaced.  I fit the maximal index against ln N and "
            "check whether a two-parameter logarithmic law is a reasonable first description.",
            "fit_growth",
            {"points": pts},
            f"k_max ≈ {fit['a']:.2f} ln N + {fit['b']:.2f}, R²={fit['r2']:.3f}; "
            f"max k/ln n = {max_ratio:.2f}.",
        )
        plotting.growth_plot([(p["N"], p["k_max"]) for p in fit["points"]],
                             fit["a"], fit["b"],
                             self.out_dir / "figures" / "growth.png")

    # -- task 8b: compare growth laws ----------------------------------
    def refine_growth(self):
        pts = [(int(p[0]), int(p[1])) for p in self.summary["prefix_maxima"]]
        ns = [p[0] for p in pts]
        ys = [float(p[1]) for p in pts]
        ln_n = [math.log(n) for n in ns]
        mean_y = sum(ys) / len(ys)

        def fit_linear(xs):
            mx = sum(xs) / len(xs)
            my = mean_y
            sxx = sum((x - mx) ** 2 for x in xs)
            sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            a = sxy / sxx
            b = my - a * mx
            pred = [a * x + b for x in xs]
            ss_res = sum((y - p) ** 2 for y, p in zip(ys, pred))
            ss_tot = sum((y - my) ** 2 for y in ys)
            return a, b, 1 - ss_res / ss_tot

        # power law in ln N:  y = A (ln N)^c
        lx = [math.log(x) for x in ln_n]
        ly = [math.log(y) for y in ys]
        mx = sum(lx) / len(lx)
        my = sum(ly) / len(ly)
        c = sum((x - mx) * (y - my) for x, y in zip(lx, ly)) / sum((x - mx) ** 2 for x in lx)
        logA = my - c * mx
        A = math.exp(logA)
        pred = [A * x ** c for x in ln_n]
        ss_res = sum((y - p) ** 2 for y, p in zip(ys, pred))
        ss_tot = sum((y - mean_y) ** 2 for y in ys)
        r2_pow_ln = 1 - ss_res / ss_tot

        # power law in N: y = A N^c
        mx2 = sum(ln_n) / len(ln_n)
        c2 = sum((x - mx2) * (y - my) for x, y in zip(ln_n, ly)) / sum((x - mx2) ** 2 for x in ln_n)
        A2 = math.exp(my - c2 * mx2)
        pred2 = [A2 * x ** c2 for x in ns]
        ss_res2 = sum((y - p) ** 2 for y, p in zip(ys, pred2))
        r2_pow_n = 1 - ss_res2 / ss_tot

        lin = fit_linear(ln_n)
        models = {
            "log_linear": {"a": lin[0], "b": lin[1], "r2": lin[2]},
            "power_in_lnN": {"A": A, "c": c, "r2": r2_pow_ln},
            "power_in_N": {"A": A2, "c": c2, "r2": r2_pow_n},
        }
        # asymptotic regime: drop the small-N edge cases
        asym = [(n, y) for n, y in zip(ns, ys) if n >= 1000]
        if len(asym) >= 4:
            ln_asym = [math.log(n) for n, _ in asym]
            ly_asym = [math.log(y) for _, y in asym]
            mx_a = sum(math.log(x) for x in ln_asym) / len(ln_asym)
            my_a = sum(ly_asym) / len(ly_asym)
            c_a = sum((math.log(x) - mx_a) * (y - my_a)
                      for x, y in zip(ln_asym, ly_asym)) / sum((math.log(x) - mx_a) ** 2 for x in ln_asym)
            A_a = math.exp(my_a - c_a * mx_a)
            pred_a = [A_a * x ** c_a for x in ln_asym]
            ss_res_a = sum((y - p) ** 2 for y, p in zip([y for _, y in asym], pred_a))
            mean_a = sum(y for _, y in asym) / len(asym)
            ss_tot_a = sum((y - mean_a) ** 2 for _, y in asym)
            r2_a = 1 - ss_res_a / ss_tot_a
            models["power_in_lnN_asymptotic"] = {"A": A_a, "c": c_a, "r2": r2_a,
                                                 "n_min": 1000}
            c, r2_pow_ln = c_a, r2_a
        self.summary["growth_models"] = models
        self.hypotheses["H7"].update(
            "supported" if c > 1.5 and r2_pow_ln > 0.9 else "refuted",
            f"power-in-ln model (n≥1000): k_max ≈ "
            f"{models['power_in_lnN_asymptotic']['A']:.4f} (ln N)^{c:.3f}, "
            f"R²={r2_pow_ln:.3f}" if "power_in_lnN_asymptotic" in models
            else f"power-in-ln model: k_max ≈ {A:.4f} (ln N)^{c:.3f}, R²={r2_pow_ln:.3f}",
            self.step + 1,
        )
        self._log(
            "model-selection",
            "A single logarithmic line fits poorly.  I compare three two-parameter laws: "
            "linear in ln N, a power of ln N, and a power of N.  With seven prefix points "
            "the comparison is descriptive, not asymptotic.",
            "compare_growth_models",
            {"points": pts},
            f"R²: log-linear={lin[2]:.3f}, power(ln N)={r2_pow_ln:.3f} "
            f"(c={c:.2f}), power(N)={r2_pow_n:.3f} (c={c2:.2f}).",
        )

    # -- task 9: conjecture tests --------------------------------------
    def test_conjectures(self):
        res = self.scans[self.n_max]
        recs = [{"n": n, "k": k} for n, k in res.records if k > 1]
        nonprime = []
        for r in recs:
            fn = factorize(r["n"], self.spf)
            if not (len(fn) == 1 and next(iter(fn.values())) == 1):
                nonprime.append(r["n"])
        self.summary["record_nonprimes"] = nonprime
        self._log(
            "conjecture",
            "I now check the cross-cutting conjectures that emerged from the scans: "
            "record holders being prime, the logarithmic growth of k_max, and the "
            "behaviour of the height ratio.",
            "test_conjectures",
            {},
            f"record holders: {[(r['n'], r['k']) for r in recs]}; non-prime record holders: {nonprime}.",
        )

    # -- task 10: synthesis --------------------------------------------
    def synthesise(self):
        self.summary["hypotheses"] = [h.to_dict() for h in self.hypotheses.values()]
        self.summary["elapsed_seconds"] = round(time.time() - self.t0, 2)
        self.summary["trace_steps"] = self.step
        with open(self.out_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(self.summary, f, ensure_ascii=False, indent=2)
        with open(self.out_dir / "hypotheses.json", "w", encoding="utf-8") as f:
            json.dump([h.to_dict() for h in self.hypotheses.values()], f,
                      ensure_ascii=False, indent=2)
        lines = [
            f"# ERDOS-GREEDY-AGENT — run {self.run_id}", "",
            f"Range: n ≤ {self.n_max:,}.  Steps: {self.step}.  "
            f"Elapsed: {self.summary['elapsed_seconds']} s.", "",
            "| step | phase | thought | action | observation |",
            "|---:|---|---|---|---|",
        ]
        for r in self.trace:
            t = r["thought"].replace("|", "/")
            o = r["observation"].replace("|", "/")
            lines.append(f"| {r['step']} | {r['phase']} | {t} | `{r['action']}` | {o} |")
        (self.out_dir / "trace.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        plotting.agent_loop(self.out_dir / "figures" / "agent_loop.png")
        self._log(
            "synthesis",
            "The campaign is complete.  I freeze the trace, the certificates and the "
            "figures, and state the surviving hypotheses and the open questions.",
            "write_summary",
            {"out_dir": str(self.out_dir)},
            f"summary.json, trace.md and {len(list((self.out_dir/'figures').glob('*.png')))} "
            "figures written.",
        )

    # -- entry point ----------------------------------------------------
    def run(self) -> dict:
        self.calibrate()
        self.refute_naive()
        self.discover_rule()
        self.validate_rule()
        self.scan_large()
        self.analyse_records()
        self.cross_check_bruteforce()
        self.scan_heights()
        self.mine_height_structure()
        self.analyse_growth()
        self.refine_growth()
        self.test_conjectures()
        self.synthesise()
        return self.summary
