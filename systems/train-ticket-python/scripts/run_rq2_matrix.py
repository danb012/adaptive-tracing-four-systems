
#!/usr/bin/env python3
import argparse
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ["q_learning", "sarsa", "bandit"]
SCENARIOS = ["healthy", "latency_spike", "error_burst", "throughput_drop"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full RQ2 matrix for Train-Ticket.")
    parser.add_argument("--reward-mode", default="balanced")
    parser.add_argument("--duration", type=int, default=45)
    # no interval argument for the train-ticket runner
    parser.add_argument("--results-subdir", default="rq2")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for scenario in SCENARIOS:
        for policy in POLICIES:
            cmd = [
                "python3",
                "scripts/run_sampling_experiment.py",
                "--policy",
                policy,
                "--scenario",
                scenario,
                "--duration",
                str(args.duration),
                "--results-subdir",
                args.results_subdir,
            ] + ["--reward-mode", args.reward_mode]
            if args.dry_run:
                print(" ".join(shlex.quote(part) for part in cmd))
                continue
            subprocess.run(cmd, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
