#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "experiment_results"
DEFAULT_DB_CONTAINER = "timescale-otel-demo-timescaledb-1"
SCENARIOS = {
    "healthy": {
        "APP_EXTRA_DELAY_MS": "0",
        "APP_ERROR_RATE": "0",
    },
    "faulted": {
        "APP_EXTRA_DELAY_MS": "40",
        "APP_ERROR_RATE": "0.05",
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


def set_sampling_rate(rate: float) -> None:
    run(["python3", "scripts/set_adaptive_sampling.py", "--rate", str(rate), "--rebuild"])


def apply_scenario(scenario: str) -> None:
    env = SCENARIOS[scenario].copy()
    run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yaml",
            "up",
            "-d",
            "--no-deps",
            "--build",
            "upper",
            "lower",
            "special",
            "digit",
            "generator",
            "load",
        ],
        extra_env=env,
    )


def resolve_db_container() -> str:
    override = os.environ.get("TIMESCALE_OTEL_DB_CONTAINER")
    if override:
        return override
    try:
        result = run(["docker", "compose", "-f", "docker-compose.yaml", "ps", "-q", "timescaledb"])
        cid = (result.stdout or "").strip()
        if cid:
            return cid
    except Exception:
        pass
    return DEFAULT_DB_CONTAINER


def clear_traces() -> None:
    db_container = resolve_db_container()
    run(
        [
            "docker",
            "exec",
            "-i",
            db_container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "otel_demo",
            "-c",
            "TRUNCATE TABLE _ps_trace.event, _ps_trace.link, _ps_trace.span RESTART IDENTITY CASCADE;",
        ]
    )


def fetch_metrics() -> dict:
    result = run(["python3", "scripts/query_trace_metrics.py"])
    return json.loads(result.stdout)


def wait_for_live_traces(timeout_seconds: int = 30, delay: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    last = {}
    while time.time() < deadline:
        metrics = fetch_metrics()
        last = metrics
        if metrics.get("total", 0) > 0 and metrics.get("qps", 0.0) > 0.0:
            return metrics
        time.sleep(delay)
    raise RuntimeError(f"timed out waiting for trace traffic; last metrics={last}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one adaptive tracing experiment on the Timescale OTel demo.")
    parser.add_argument("--rate", type=float, required=True, help="sampling rate in [0.0, 1.0]")
    parser.add_argument("--scenario", default="healthy", choices=sorted(SCENARIOS.keys()))
    parser.add_argument("--duration", type=int, default=20)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)

    set_sampling_rate(args.rate)
    apply_scenario(args.scenario)
    time.sleep(5)
    clear_traces()
    wait_for_live_traces()
    time.sleep(args.duration)
    metrics = fetch_metrics()

    result = {
        "system": "timescale-otel-demo",
        "sampling_rate": args.rate,
        "scenario": args.scenario,
        "duration_seconds": args.duration,
        "captured_at": time.time(),
        "metrics": metrics,
    }

    rate_label = str(args.rate).replace(".", "_")
    out_path = RESULTS_DIR / f"rate_{rate_label}__{args.scenario}.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
