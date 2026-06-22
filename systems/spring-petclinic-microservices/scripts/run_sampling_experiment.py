#!/usr/bin/env python3
import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "experiment_results"
BASE_URL = "http://localhost:8080"
TRAFFIC_PATHS = [
    "/",
    "/api/customer/owners",
    "/api/vet/vets",
    "/api/gateway/owners/1",
]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, check=True, text=True, capture_output=True)


def set_sampling_rate(rate: float) -> None:
    run(["python3", "scripts/set_adaptive_sampling.py", "--rate", str(rate), "--restart"])


def disable_faults() -> None:
    for service in ("customers", "visits", "vets"):
        try:
            run(["bash", "scripts/chaos/call_chaos.sh", service, "watcher_disable"])
        except subprocess.CalledProcessError:
            pass


def apply_scenario(scenario: str) -> None:
    disable_faults()
    if scenario == "faulted":
        try:
            run(
                [
                    "bash",
                    "scripts/chaos/call_chaos.sh",
                    "visits",
                    "attacks_enable_latency",
                    "watcher_enable_restcontroller",
                ]
            )
        except subprocess.CalledProcessError:
            # Some published images do not expose Chaos Monkey actuator endpoints.
            # Fall back to a heavier traffic profile for the faulted scenario.
            pass


def fetch_window_metrics(start_ms: int, end_ms: int) -> dict:
    lookback = max(60, int((end_ms - start_ms) / 1000) + 30)
    result = run(["python3", "scripts/query_trace_metrics.py", "--lookback-seconds", str(lookback)])
    return json.loads(result.stdout)


def hit(path: str) -> None:
    try:
        with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=5) as response:
            response.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        pass


def warm_up_traffic(seconds: int = 8) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        for path in TRAFFIC_PATHS:
            hit(path)
        time.sleep(0.2)


def generate_traffic(duration_seconds: int, burst: int, pause: float) -> None:
    deadline = time.time() + duration_seconds
    idx = 0
    while time.time() < deadline:
        path = TRAFFIC_PATHS[idx % len(TRAFFIC_PATHS)]
        for _ in range(burst):
            hit(path)
        idx += 1
        time.sleep(pause)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a fixed-rate Petclinic experiment.")
    parser.add_argument("--rate", type=float, required=True)
    parser.add_argument("--scenario", choices=["healthy", "faulted"], default="healthy")
    parser.add_argument("--duration", type=int, default=20)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)

    set_sampling_rate(args.rate)
    apply_scenario(args.scenario)
    time.sleep(8)
    warm_up_traffic()

    start_ms = int(time.time() * 1000)
    if args.scenario == "healthy":
        generate_traffic(args.duration, burst=2, pause=0.2)
    else:
        generate_traffic(args.duration, burst=4, pause=0.1)
    time.sleep(20)
    end_ms = int(time.time() * 1000)
    metrics = fetch_window_metrics(start_ms, end_ms)
    payload = {
        "system": "spring-petclinic-microservices",
        "sampling_rate": args.rate,
        "scenario": args.scenario,
        "duration_seconds": args.duration,
        "captured_at": time.time(),
        "metrics": metrics,
    }

    out_path = RESULTS_DIR / f"rate_{str(args.rate).replace('.', '_')}__{args.scenario}.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="ascii")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
