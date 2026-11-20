"""Command-line entry point for ERDOS-GREEDY-AGENT."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import GreedyAgent
from .domain import scan


def main(argv=None):
    p = argparse.ArgumentParser(prog="es-agent",
                                description="Autonomous agent for greedy Erdős–Straus obstructions")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="run the full research campaign")
    run.add_argument("--n-max", type=int, default=20_000_000)
    run.add_argument("--out", type=Path, default=Path("runs/main"))
    run.add_argument("--seed", type=int, default=20261120)

    sc = sub.add_parser("scan", help="only compute the greedy-index table")
    sc.add_argument("--n-max", type=int, default=1_000_000)
    sc.add_argument("--out", type=Path, default=Path("data/scan.json"))

    args = p.parse_args(argv)
    if args.cmd == "scan":
        res = scan(args.n_max)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(res.to_dict(), indent=2), encoding="utf-8")
        print(json.dumps(res.to_dict(), indent=2))
        return 0
    if args.cmd == "run":
        agent = GreedyAgent(args.n_max, args.out, seed=args.seed)
        summary = agent.run()
        print(f"run complete: {args.out}")
        print(f"steps={summary['trace_steps']} elapsed={summary['elapsed_seconds']}s")
        print(f"summary: {args.out / 'summary.json'}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
