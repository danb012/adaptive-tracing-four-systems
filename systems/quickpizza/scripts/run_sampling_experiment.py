#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "experiment_results"
BASE_URL = "http://localhost:3333/api/pizza"
REQUEST_BODY = json.dumps(
    {
        "maxCaloriesPerSlice": 500,
        "mustBeVegetarian": False,
        "excludedIngredients": ["pepperoni"],
        "excludedTools": ["knife"],
        "maxNumberOfToppings": 6,
        "minNumberOfToppings": 2,
    }
).encode("utf-8")
BASE_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "token abcdef0123456789",
}
METRIC_SETTLE_SECONDS = 16


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, check=True, text=True, capture_output=True)


def set_sampling_rate(rate: float) -> None:
    run([sys.executable, "scripts/set_adaptive_sampling.py", "--rate", str(rate), "--restart"])
    time.sleep(8)


def scenario_headers(scenario: str) -> dict[str, str]:
    if scenario == "latency_spike":
        return {
            "x-delay-record-recommendation": "400ms",
            "x-delay-record-recommendation-percentage": "100",
        }
    if scenario == "error_burst":
        return {
            "x-error-get-ingredients": "internal-error",
            "x-error-get-ingredients-percentage": "100",
        }
    return {}


def request_once(extra_headers: dict[str, str]) -> None:
    req = urllib.request.Request(BASE_URL, data=REQUEST_BODY, method="POST")
    for key, value in {**BASE_HEADERS, **extra_headers}.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            response.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        pass


def generate_traffic(duration_seconds: int, scenario: str) -> None:
    headers = scenario_headers(scenario)
    if scenario == "throughput_drop":
        workers = 1
        pause = 1.0
    elif scenario == "healthy":
        workers = 3
        pause = 0.2
    else:
        workers = 3
        pause = 0.2

    deadline = time.time() + duration_seconds

    def worker() -> None:
        while time.time() < deadline:
            request_once(headers)
            time.sleep(pause)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def fetch_metrics(lookback_seconds: int) -> dict:
    result = run([sys.executable, "scripts/query_trace_metrics.py", "--lookback-seconds", str(lookback_seconds)])
    return json.loads(result.stdout)


def fetch_window_metrics(lookback_seconds: int, offset_seconds: int = 0) -> dict:
    cmd = [
        sys.executable,
        "scripts/query_trace_metrics.py",
        "--lookback-seconds",
        str(lookback_seconds),
    ]
    if offset_seconds > 0:
        cmd.extend(["--offset-seconds", str(offset_seconds)])
    result = run(cmd)
    return json.loads(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, required=True)
    parser.add_argument(
        "--scenario",
        default="healthy",
        choices=["healthy", "latency_spike", "error_burst", "throughput_drop"],
    )
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--results-subdir", default="")
    args = parser.parse_args()

    set_sampling_rate(args.rate)

    for _ in range(10):
        request_once({})
    time.sleep(2)

    generate_traffic(args.duration, args.scenario)
    time.sleep(METRIC_SETTLE_SECONDS)

    metrics = fetch_window_metrics(args.duration, offset_seconds=METRIC_SETTLE_SECONDS)
    if float(metrics.get("total", 0.0)) <= 0:
        metrics = fetch_window_metrics(
            args.duration + METRIC_SETTLE_SECONDS,
            offset_seconds=METRIC_SETTLE_SECONDS,
        )

    out_dir = RESULTS_DIR / args.results_subdir if args.results_subdir else RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"rate_{str(args.rate).replace('.', '_')}__{args.scenario}.json"
    payload = {
        "system": "quickpizza",
        "sampling_rate": args.rate,
        "scenario": args.scenario,
        "duration_seconds": args.duration,
        "captured_at": time.time(),
        "metrics": metrics,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
