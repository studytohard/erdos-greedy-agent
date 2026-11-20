import unittest

from es_agent.domain import scan, smallest_prime_factors
from es_agent.rules import feature_vector, learn_conjunction


class TestRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n_max = 20000
        cls.spf = smallest_prime_factors(cls.n_max)
        cls.res = scan(cls.n_max, cls.spf)
        cls.names = None
        cls.cols = {}
        cls.labels = []
        for n in range(2, cls.n_max + 1):
            f = feature_vector(n, cls.spf)
            if cls.names is None:
                cls.names = list(f)
                cls.cols = {k: [] for k in cls.names}
            for k, v in f.items():
                cls.cols[k].append(v)
            cls.labels.append(cls.res.ks[n] > 1)
        cls.rule = learn_conjunction(cls.cols, cls.labels, max_literals=4)

    def test_rule_is_exact_on_training(self):
        self.assertEqual(self.rule.fp, 0)
        self.assertEqual(self.rule.fn, 0)
        self.assertGreater(self.rule.tp, 0)

    def test_rule_uses_three_adic_predicates(self):
        joined = " ".join(self.rule.literals)
        self.assertIn("%3", joined)


if __name__ == "__main__":
    unittest.main()
