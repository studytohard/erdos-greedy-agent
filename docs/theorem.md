# Mathematical notes

This note records the two proved statements used by the agent.  The full
discussion, figures and trace are in [`../report/report.pdf`](../report/report.pdf).

## 1. The greedy step

For `n ≥ 2`, set

```
x_j = (n + 4j − 1) / 4      (requires n ≡ 1 mod 4)
a_j = 4x_j − n = 4j − 1
```

and let `k(n)` be the first `j` for which `4/n = 1/x_j + 1/y + 1/z` has a
solution with `x_j ≤ y ≤ z`.  For `n ≠ 1 (mod 4)` the first step always
succeeds.

### Divisor certificate

With `x = x_j`, `a = 4x − n`, `b = nx`, `g = gcd(a,b)`, `p = a/g`, `q = b/g`,

```
1/y + 1/z = p/q
  ⇔ (p y − q)(p z − q) = q².
```

Thus a solution exists iff some divisor `d | q²` satisfies `d ≡ −q (mod p)`.
Writing `q = ∏ ℓ^{e_ℓ}` and `d = ∏ ℓ^{f_ℓ}` (`0 ≤ f_ℓ ≤ 2e_ℓ`), the condition
becomes

```
∏ ℓ^{f_ℓ − e_ℓ} ≡ −1 (mod p).
```

The agent computes the set `S_j` of reachable products and tests `−1 ∈ S_j`.
Since `p ≤ a_j`, this is a small finite-group computation.

## 2. Theorem (first step)

**Theorem.** For every `n ≥ 2`,

```
k(n) > 1  ⇔  every prime factor of n and of ⌊(n+3)/4⌋ is ≡ 1 (mod 3).
```

**Proof.** If `n` is even, `2` divides `n` and `2 ≢ 1 (mod 3)`, while the
first step succeeds because `p = 1`.  If `n ≡ 3 (mod 4)`, the first step also
has `p = 1`; if both `n` and `x_0 = (n+3)/4` had only prime factors
`≡ 1 (mod 3)`, then `n ≡ 1` and `x_0 ≡ 1 (mod 3)`, but `n = 4m+3 ≡ m` and
`x_0 = m+1`, giving `x_0 ≡ 0` or `2`, a contradiction.

The interesting case is `n ≡ 1 (mod 4)`.  If `3 | n`, then `g = 3`, `p = 1`
and the first step succeeds.  Otherwise `p = 3`, `q = n x_0 ≡ 1 (mod 3)`.
Modulo 3 the reachable set is `{1}` if all prime factors of `q` are
`≡ 1 (mod 3)`, and `{1,2}` otherwise; the target is `−1 ≡ 2`.  Hence the first
step fails exactly when every prime factor of `q = n x_0` is `1 mod 3`.  ∎

**Corollary.** Every first-step failure satisfies `n ≡ 1 (mod 12)`.

## 3. Proposition (CRT height mechanism)

If `n ≡ 9 (mod 19)` and `n ≡ 33 (mod 52)`, then at step `j = 5` (`p = 19`),

```
q = n x_5 ≡ n²/4 ≡ −13 (mod 19),      13 | x_5,
```

so `d = 13` is admissible.  If steps 1–4 fail and `d = 13` is maximal, then

```
z(n) = q(q+13)/247,
z(n)/n³ = (n+19)(n²+19n+52) / (3952 n²) → ∞.
```

For `n = 767,761` and `n = 418,009` this matches the computed values
`194.2811236` and `105.7811237` exactly.

## 4. Status

- The theorem and the proposition are proved.
- The range `n ≤ 2×10⁷` is audited with zero false positives / negatives.
- The unboundedness of `k(n)` and of `z(n)/n³`, and the record-prime
  conjecture, remain open.
