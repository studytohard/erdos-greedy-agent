import json
import unittest
import uuid
from pathlib import Path

from es_agent.agent import GreedyAgent


def _workdir() -> Path:
    d = Path("runs") / f"unit_{uuid.uuid4().hex[:8]}"
    d.mkdir(parents=True, exist_ok=False)
    return d


class TestAgent(unittest.TestCase):
    def test_small_campaign(self):
        td = _workdir()
        agent = GreedyAgent(20000, td)
        summary = agent.run()
        self.assertGreater(summary["trace_steps"], 10)
        self.assertTrue((td / "summary.json").exists())
        self.assertTrue((td / "trace.jsonl").exists())
        self.assertTrue((td / "trace.md").exists())
        self.assertGreaterEqual(len(list((td / "figures").glob("*.png"))), 6)
        hyps = {h["id"]: h for h in summary["hypotheses"]}
        self.assertEqual(hyps["H0"]["status"], "refuted")
        self.assertEqual(hyps["H1"]["status"], "theorem")
        self.assertEqual(summary["rule_validation_1e6"]["fp"], 0)
        self.assertEqual(summary["rule_validation_1e6"]["fn"], 0)

    def test_trace_is_jsonl(self):
        td = _workdir()
        agent = GreedyAgent(5000, td)
        agent.calibrate()
        lines = (td / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        rec = json.loads(lines[0])
        self.assertIn("thought", rec)
        self.assertIn("observation", rec)


if __name__ == "__main__":
    unittest.main()
