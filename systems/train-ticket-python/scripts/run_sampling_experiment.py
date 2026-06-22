#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.yml"
RESULTS_DIR = ROOT / "experiment_results"
STATUS_URL = "http://localhost:8002/status"
SUMMARY_URL = "http://localhost:8002/summary"
DECISIONS_URL = "http://localhost:8002/decisions?limit={limit}"
AGENT_TMP_FILES = [
    "/tmp/agent_decisions.jsonl",
    "/tmp/agent_status.json",
    "/tmp/agent_summary.json",
]
SCENARIOS = {
    "healthy": {
        "ORDER_DELAY_MS": "50",
        "ORDER_ERROR_RATE": "0.01",
        "TRAVEL_DELAY_MS": "30",
        "TRAVEL_ERROR_RATE": "0.0",
    },
    "faulted": {
        "ORDER_DELAY_MS": "200",
        "ORDER_ERROR_RATE": "0.08",
        "TRAVEL_DELAY_MS": "120",
        "TRAVEL_ERROR_RATE": "0.03",
    },
    "latency_spike": {
        "ORDER_DELAY_MS": "320",
        "ORDER_ERROR_RATE": "0.0",
        "TRAVEL_DELAY_MS": "220",
        "TRAVEL_ERROR_RATE": "0.0",
    },
    "error_burst": {
        "ORDER_DELAY_MS": "60",
        "ORDER_ERROR_RATE": "0.18",
        "TRAVEL_DELAY_MS": "40",
        "TRAVEL_ERROR_RATE": "0.10",
    },
    "throughput_drop": {
        "ORDER_DELAY_MS": "420",
        "ORDER_ERROR_RATE": "0.02",
        "TRAVEL_DELAY_MS": "280",
        "TRAVEL_ERROR_RATE": "0.01",
    },
}


def run(cmd: list[str], extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )


def try_run(cmd: list[str], extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )


def fetch_json(url: str, retries: int = 10, delay: float = 2.0) -> dict:
    last_error = None
    for _ in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            ConnectionResetError,
            OSError,
        ) as exc:
            last_error = exc
            time.sleep(delay)
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def reset_seats() -> None:
    result = try_run(
        [
            "docker",
            "exec",
            "-i",
            "train-ticket-python-postgres-1",
            "psql",
            "-U",
            "tt",
            "-d",
            "trainticket",
            "-c",
            "UPDATE seat.seats SET available=5000;",
        ]
    )
    if result.returncode != 0:
        # Seat rows are lazily recreated by the seat service, so experiments can continue
        # even if this reset query is unavailable early in startup.
        return


def clear_agent_outputs() -> None:
    run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "exec",
            "-T",
            "sampling-agent",
            "sh",
            "-lc",
            "rm -f " + " ".join(AGENT_TMP_FILES),
        ]
    )


def restart_services(policy_mode: str, reward_mode: str, scenario: str) -> None:
    env = {
        "POLICY_MODE": policy_mode,
        "RL_REWARD_MODE": reward_mode,
    }
    env.update(SCENARIOS[scenario])
    run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "up",
            "-d",
            "order",
            "travel",
            "sampling-agent",
            "sampling-agent-status",
        ],
        extra_env=env,
    )


def wait_for_live_status(timeout_seconds: int = 60, delay: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    last_status = None
    while time.time() < deadline:
        try:
            status = fetch_json(STATUS_URL, retries=3, delay=delay)
            last_status = status
            if status.get("total", 0) > 0 and status.get("qps", 0.0) > 0.0:
                return status
        except RuntimeError:
            pass
        time.sleep(delay)
    raise RuntimeError(f"timed out waiting for live traffic; last status={last_status}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one adaptive sampling experiment.")
    parser.add_argument("--policy", required=True, help="policy mode, e.g. q_learning, sarsa, bandit")
    parser.add_argument("--reward-mode", default="balanced", help="reward mode")
    parser.add_argument("--scenario", default="healthy", choices=sorted(SCENARIOS.keys()), help="traffic/fault scenario")
    parser.add_argument("--duration", type=int, default=30, help="seconds to wait before sampling results")
    parser.add_argument("--decision-limit", type=int, default=20, help="recent decisions to capture")
    parser.add_argument("--results-subdir", default="", help="optional subdirectory under experiment_results")
    args = parser.parse_args()

    results_dir = RESULTS_DIR / args.results_subdir if args.results_subdir else RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)

    reset_seats()
    restart_services(args.policy, args.reward_mode, args.scenario)
    clear_agent_outputs()
    wait_for_live_status()
    time.sleep(args.duration)

    status = fetch_json(STATUS_URL)
    summary = fetch_json(SUMMARY_URL)
    decisions = fetch_json(DECISIONS_URL.format(limit=args.decision_limit))

    payload = {
        "policy": args.policy,
        "reward_mode": args.reward_mode,
        "scenario": args.scenario,
        "duration_seconds": args.duration,
        "captured_at": time.time(),
        "status": status,
        "summary": summary,
        "decisions": decisions,
    }

    out_path = results_dir / f"{args.policy}__{args.reward_mode}__{args.scenario}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
