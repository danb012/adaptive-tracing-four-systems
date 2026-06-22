#!/usr/bin/env python3
import argparse
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ["q_learning", "sarsa", "bandit", "rule", "kmeans"]
SCENARIOS = ["healthy", "faulted"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full RQ1 comparison matrix for Grafana QuickPizza.")
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--interval", type=int, default=20)
    parser.add_argument("--results-subdir", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for scenario in SCENARIOS:
        for policy in POLICIES:
            cmd = [
                sys.executable,
                "scripts/run_policy_experiment.py",
                "--policy",
                policy,
                "--scenario",
                scenario,
                "--duration",
                str(args.duration),
                "--interval",
                str(args.interval),
            ]
            if args.results_subdir:
                cmd.extend(["--results-subdir", args.results_subdir])
            if args.dry_run:
                print(" ".join(shlex.quote(part) for part in cmd))
                continue
            subprocess.run(cmd, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
