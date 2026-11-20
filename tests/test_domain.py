import unittest
from fractions import Fraction

from es_agent.domain import (greedy_index, greedy_witness, scan,
                             smallest_prime_factors, step_certificate)


class TestDomain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spf = smallest_prime_factors(20000)

    def test_known_records(self):
        self.assertEqual(greedy_index(49, self.spf), 2)
        self.assertEqual(greedy_index(1129, self.spf), 3)
        self.assertEqual(greedy_index(1201, self.spf), 6)
        self.assertEqual(greedy_index(21169, self.spf), 8)
        self.assertEqual(greedy_index(118801, self.spf), 15)

    def test_witness_is_exact(self):
        for n in range(2, 500):
            j, x, y, z, d, p = greedy_witness(n, self.spf)
            self.assertEqual(Fraction(1, x) + Fraction(1, y) + Fraction(1, z),
                             Fraction(4, n), msg=f"n={n}")

    def test_step_certificate_first_step(self):
        c = step_certificate(49, 1, self.spf)
        self.assertFalse(c.success)
        self.assertEqual(c.p, 3)
        self.assertEqual(c.divisor_residues, [1])
        c = step_certificate(1129, 1, self.spf)
        self.assertFalse(c.success)
        self.assertEqual(c.p, 3)

    def test_scan_small(self):
        res = scan(5000, self.spf)
        self.assertEqual(res.ks[49], 2)
        self.assertEqual(res.distribution[1] + sum(v for k, v in res.distribution.items() if k > 1),
                         4999)

    def test_theorem_counterexample_shape(self):
        # k > 1 forces n == 1 mod 12
        res = scan(20000, self.spf)
        for n in range(2, 20001):
            if res.ks[n] > 1:
                self.assertEqual(n % 12, 1, msg=f"n={n}")


if __name__ == "__main__":
    unittest.main()
