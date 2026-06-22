#!/usr/bin/env python3
import argparse
import json
import random
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
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
ACTION_VALUES = [0.05, 0.1, 0.2, 0.5, 0.8]
ERROR_THRESHOLDS = [0.01, 0.05, 0.2]
LATENCY_THRESHOLDS = [100.0, 200.0, 400.0]
QPS_THRESHOLDS = [2.0, 5.0, 10.0]
KMEANS_K = 3
KMEANS_WINDOW = 200
EPSILON = 0.1
ALPHA = 0.2
GAMMA = 0.9
METRIC_SETTLE_SECONDS = 16

feature_window = deque(maxlen=KMEANS_WINDOW)
kmeans_model = None
q_learning_q = {}
sarsa_q = {}
bandit_values = {}
q_pending = None
sarsa_pending = None
last_features = None
last_rate = None


SCENARIO_PROFILES = {
    "healthy": {"workers": 3, "pause": 0.2, "headers": {}},
    "faulted": {
        "workers": 3,
        "pause": 0.2,
        "headers": {
            "x-delay-record-recommendation": "400ms",
            "x-delay-record-recommendation-percentage": "100",
        },
    },
    "latency_spike": {
        "workers": 3,
        "pause": 0.2,
        "headers": {
            "x-delay-record-recommendation": "400ms",
            "x-delay-record-recommendation-percentage": "100",
        },
    },
    "error_burst": {
        "workers": 3,
        "pause": 0.2,
        "headers": {
            "x-error-get-ingredients": "internal-error",
            "x-error-get-ingredients-percentage": "100",
        },
    },
    "throughput_drop": {"workers": 1, "pause": 1.0, "headers": {}},
}


def reset_policy_state() -> None:
    global feature_window, kmeans_model, q_learning_q, sarsa_q, bandit_values
    global q_pending, sarsa_pending, last_features, last_rate
    feature_window = deque(maxlen=KMEANS_WINDOW)
    kmeans_model = None
    q_learning_q = {}
    sarsa_q = {}
    bandit_values = {}
    q_pending = None
    sarsa_pending = None
    last_features = None
    last_rate = None


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, check=True, text=True, capture_output=True)


def set_sampling_rate(rate: float, restart: bool = True) -> None:
    cmd = [sys.executable, "scripts/set_adaptive_sampling.py", "--rate", str(rate)]
    if restart:
        cmd.append("--restart")
    run(cmd)
    if restart:
        time.sleep(8)


def request_once(extra_headers: dict[str, str]) -> None:
    req = urllib.request.Request(BASE_URL, data=REQUEST_BODY, method="POST")
    for key, value in {**BASE_HEADERS, **extra_headers}.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            response.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        pass


def warm_up_traffic(seconds: int = 8) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        request_once({})
        time.sleep(0.2)


def generate_traffic(duration_seconds: int, scenario: str) -> None:
    profile = SCENARIO_PROFILES[scenario]
    deadline = time.time() + duration_seconds

    def worker() -> None:
        while time.time() < deadline:
            request_once(profile["headers"])
            time.sleep(profile["pause"])

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(profile["workers"])]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def fetch_metrics(lookback_seconds: int = 600) -> dict:
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


def measure_interval(scenario: str, interval_seconds: int) -> dict:
    generate_traffic(interval_seconds, scenario)
    time.sleep(METRIC_SETTLE_SECONDS)
    metrics = fetch_window_metrics(interval_seconds, offset_seconds=METRIC_SETTLE_SECONDS)

    if float(metrics.get("total", 0.0)) <= 0:
        for _ in range(10):
            request_once(SCENARIO_PROFILES[scenario]["headers"])
        time.sleep(METRIC_SETTLE_SECONDS)
        metrics = fetch_window_metrics(
            interval_seconds + METRIC_SETTLE_SECONDS,
            offset_seconds=METRIC_SETTLE_SECONDS,
        )

    return {
        "total": float(metrics.get("total", 0.0)),
        "avg_latency_ms": float(metrics.get("avg_latency_ms", 0.0)),
        "error_rate": float(metrics.get("error_rate", 0.0)),
        "qps": float(metrics.get("qps", 0.0)),
        "error_total": float(metrics.get("error_total", 0.0)),
        "duration_total_ms": float(metrics.get("duration_total_ms", 0.0)),
        "selector_used": metrics.get("selector_used", "none"),
        "current_total": float(metrics.get("current_total", 0.0)),
        "current_error_total": float(metrics.get("current_error_total", 0.0)),
        "current_duration_total_ms": float(metrics.get("current_duration_total_ms", 0.0)),
    }


def bin_value(value: float, thresholds: list[float]) -> int:
    for idx, cutoff in enumerate(thresholds):
        if value <= cutoff:
            return idx
    return len(thresholds)


def state_from_features(error_rate: float, avg_latency_ms: float, qps: float) -> tuple[int, int, int]:
    return (
        bin_value(error_rate, ERROR_THRESHOLDS),
        bin_value(avg_latency_ms, LATENCY_THRESHOLDS),
        bin_value(qps, QPS_THRESHOLDS),
    )


def compute_drift(error_rate: float, avg_latency_ms: float, qps: float) -> float:
    global last_features
    if last_features is None:
        last_features = (error_rate, avg_latency_ms, qps)
        return 0.0
    prev_error, prev_latency, prev_qps = last_features
    drift = abs(error_rate - prev_error) + abs(avg_latency_ms - prev_latency) / 1000.0 + abs(qps - prev_qps)
    last_features = (error_rate, avg_latency_ms, qps)
    return drift


def compute_reward(error_rate: float, avg_latency_ms: float, qps: float, rate: float) -> tuple[float, dict]:
    global last_rate
    drift_score = compute_drift(error_rate, avg_latency_ms, qps)
    previous_rate = last_rate
    change_penalty = abs(rate - previous_rate) if previous_rate is not None else 0.0

    error_component = 2.0 * error_rate
    latency_component = 0.5 * (avg_latency_ms / 1000.0)
    drift_component = 0.5 * drift_score
    cost_component = 1.0 * rate
    stability_component = 0.2 * change_penalty

    reward = error_component + latency_component + drift_component - cost_component - stability_component
    last_rate = rate

    return reward, {
        "error_component": error_component,
        "latency_component": latency_component,
        "drift_component": drift_component,
        "cost_component": cost_component,
        "stability_component": stability_component,
        "drift_score": drift_score,
        "previous_rate": previous_rate,
    }


def select_action(values: list[float]) -> int:
    if random.random() < EPSILON:
        return random.randrange(len(ACTION_VALUES))
    return max(range(len(values)), key=lambda i: values[i])


def rule_rate(error_rate: float, total: float) -> float:
    if total < 5:
        return 0.1
    if error_rate >= 0.2:
        return 0.8
    if error_rate >= 0.05:
        return 0.5
    return 0.05


def kmeans_rate(error_rate: float, avg_latency_ms: float, qps: float) -> float:
    global kmeans_model
    try:
        from sklearn.cluster import KMeans
    except ImportError as exc:
        raise SystemExit(
            "K-Means policy requires scikit-learn. Install it in your Python environment (for example: `pip install scikit-learn`)."
        ) from exc

    feature_window.append([error_rate, avg_latency_ms, qps])
    if len(feature_window) < max(10, KMEANS_K * 5):
        return 0.1
    X = [list(row) for row in feature_window]
    if kmeans_model is None or len(feature_window) % 20 == 0:
        kmeans_model = KMeans(n_clusters=KMEANS_K, n_init=10, random_state=42)
        kmeans_model.fit(X)
    label = kmeans_model.predict([[error_rate, avg_latency_ms, qps]])[0]
    centers = kmeans_model.cluster_centers_
    order = sorted(range(len(centers)), key=lambda i: (centers[i][0], centers[i][1], centers[i][2]))
    rank = order.index(label)
    if rank == len(order) - 1:
        return 0.8
    if rank == 0:
        return 0.05
    return 0.2


def q_learning_rate(error_rate: float, avg_latency_ms: float, qps: float):
    global q_pending
    state = state_from_features(error_rate, avg_latency_ms, qps)
    q_values = q_learning_q.setdefault(state, [0.0 for _ in ACTION_VALUES])

    if q_pending is not None:
        prev_state, prev_action_idx, prev_reward = q_pending
        prev_values = q_learning_q.setdefault(prev_state, [0.0 for _ in ACTION_VALUES])
        td_target = prev_reward + GAMMA * max(q_values)
        prev_values[prev_action_idx] = prev_values[prev_action_idx] + ALPHA * (
            td_target - prev_values[prev_action_idx]
        )

    action_idx = select_action(q_values)
    rate = ACTION_VALUES[action_idx]
    reward, components = compute_reward(error_rate, avg_latency_ms, qps, rate)
    q_pending = (state, action_idx, reward)
    return rate, reward, state, action_idx, components


def sarsa_rate(error_rate: float, avg_latency_ms: float, qps: float):
    global sarsa_pending
    state = state_from_features(error_rate, avg_latency_ms, qps)
    q_values = sarsa_q.setdefault(state, [0.0 for _ in ACTION_VALUES])
    action_idx = select_action(q_values)

    if sarsa_pending is not None:
        prev_state, prev_action_idx, prev_reward = sarsa_pending
        prev_values = sarsa_q.setdefault(prev_state, [0.0 for _ in ACTION_VALUES])
        td_target = prev_reward + GAMMA * q_values[action_idx]
        prev_values[prev_action_idx] = prev_values[prev_action_idx] + ALPHA * (
            td_target - prev_values[prev_action_idx]
        )

    rate = ACTION_VALUES[action_idx]
    reward, components = compute_reward(error_rate, avg_latency_ms, qps, rate)
    sarsa_pending = (state, action_idx, reward)
    return rate, reward, state, action_idx, components


def bandit_rate(error_rate: float, avg_latency_ms: float, qps: float):
    state = state_from_features(error_rate, avg_latency_ms, qps)
    values = bandit_values.setdefault(state, [0.0 for _ in ACTION_VALUES])
    action_idx = select_action(values)
    rate = ACTION_VALUES[action_idx]
    reward, components = compute_reward(error_rate, avg_latency_ms, qps, rate)
    values[action_idx] = values[action_idx] + ALPHA * (reward - values[action_idx])
    return rate, reward, state, action_idx, components


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one policy-based adaptive tracing experiment on QuickPizza.")
    parser.add_argument("--policy", required=True, choices=["q_learning", "sarsa", "bandit", "rule", "kmeans"])
    parser.add_argument("--scenario", default="healthy", choices=sorted(SCENARIO_PROFILES.keys()))
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--interval", type=int, default=20, help="decision interval in seconds")
    parser.add_argument("--results-subdir", default="", help="optional subdirectory under experiment_results")
    args = parser.parse_args()

    reset_policy_state()
    results_dir = RESULTS_DIR / args.results_subdir if args.results_subdir else RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)

    current_rate = 0.1
    set_sampling_rate(current_rate, restart=True)
    warm_up_traffic(8)

    decisions = []
    steps = max(1, args.duration // args.interval)
    last_window_metrics = None

    for _ in range(steps):
        window_metrics = measure_interval(args.scenario, args.interval)
        last_window_metrics = window_metrics

        error_rate = float(window_metrics.get("error_rate", 0.0))
        avg_latency_ms = float(window_metrics.get("avg_latency_ms", 0.0))
        qps = float(window_metrics.get("qps", 0.0))
        total = float(window_metrics.get("total", 0.0))
        reward = None
        state = None
        action_idx = None
        reward_components = None

        if args.policy == "rule":
            rate = rule_rate(error_rate, total)
        elif args.policy == "kmeans":
            rate = kmeans_rate(error_rate, avg_latency_ms, qps)
        elif args.policy == "q_learning":
            rate, reward, state, action_idx, reward_components = q_learning_rate(error_rate, avg_latency_ms, qps)
        elif args.policy == "sarsa":
            rate, reward, state, action_idx, reward_components = sarsa_rate(error_rate, avg_latency_ms, qps)
        else:
            rate, reward, state, action_idx, reward_components = bandit_rate(error_rate, avg_latency_ms, qps)

        if rate != current_rate:
            set_sampling_rate(rate, restart=True)
            current_rate = rate
            warm_up_traffic(4)

        decision = {
            "timestamp": time.time(),
            "error_rate": error_rate,
            "avg_latency_ms": avg_latency_ms,
            "qps": qps,
            "total": total,
            "chosen_rate": rate,
            "policy_mode": args.policy,
            "reward": reward,
            "state": state,
            "action_idx": action_idx,
            "reward_components": reward_components,
            "selector_used": window_metrics.get("selector_used", "none"),
        }
        decisions.append(decision)

    rewards = [d["reward"] for d in decisions if d["reward"] is not None]
    rates = [d["chosen_rate"] for d in decisions]
    status = {
        "timestamp": time.time(),
        "error_rate": last_window_metrics["error_rate"] if last_window_metrics else 0.0,
        "avg_latency_ms": last_window_metrics["avg_latency_ms"] if last_window_metrics else 0.0,
        "qps": last_window_metrics["qps"] if last_window_metrics else 0.0,
        "total": last_window_metrics["total"] if last_window_metrics else 0.0,
        "chosen_rate": rates[-1] if rates else None,
        "policy_mode": args.policy,
        "reward": rewards[-1] if rewards else None,
        "state": decisions[-1]["state"] if decisions else None,
        "action_idx": decisions[-1]["action_idx"] if decisions else None,
        "reward_components": decisions[-1]["reward_components"] if decisions else None,
        "selector_used": decisions[-1]["selector_used"] if decisions else "none",
    }
    summary = {"status": "no-data"}
    if decisions:
        summary = {
            "policy_mode": args.policy,
            "reward_mode": "balanced",
            "decision_count": len(decisions),
            "avg_reward": (sum(rewards) / len(rewards)) if rewards else None,
            "min_reward": min(rewards) if rewards else None,
            "max_reward": max(rewards) if rewards else None,
            "avg_rate": sum(rates) / len(rates),
            "min_rate": min(rates),
            "max_rate": max(rates),
            "last_state": decisions[-1]["state"],
            "last_action_idx": decisions[-1]["action_idx"],
        }

    result = {
        "system": "quickpizza",
        "policy": args.policy,
        "reward_mode": "balanced",
        "scenario": args.scenario,
        "duration_seconds": args.duration,
        "decision_interval_seconds": args.interval,
        "captured_at": time.time(),
        "status": status,
        "summary": summary,
        "decisions": {
            "status": "ok",
            "items": decisions,
        },
    }

    out_path = results_dir / f"{args.policy}__balanced__{args.scenario}.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
