#!/usr/bin/env python3
import argparse
import json
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "experiment_results"
DB_CONTAINER = "timescale-otel-demo-timescaledb-1"
GENERATOR_URL = "http://localhost:5050/"
ACTION_VALUES = [0.05, 0.1, 0.2, 0.5, 0.8]
ERROR_THRESHOLDS = [0.05, 0.2, 0.5]
LATENCY_THRESHOLDS = [50.0, 150.0, 300.0]
QPS_THRESHOLDS = [0.2, 0.5, 1.0]
KMEANS_K = 3
KMEANS_WINDOW = 200
EPSILON = 0.1
ALPHA = 0.2
GAMMA = 0.9

SCENARIOS = {
    "healthy": {
        "APP_EXTRA_DELAY_MS": "0",
        "APP_ERROR_RATE": "0",
    },
    "faulted": {
        "APP_EXTRA_DELAY_MS": "40",
        "APP_ERROR_RATE": "0.05",
    },
    "latency_spike": {
        "APP_EXTRA_DELAY_MS": "120",
        "APP_ERROR_RATE": "0",
    },
    "error_burst": {
        "APP_EXTRA_DELAY_MS": "0",
        "APP_ERROR_RATE": "0.15",
    },
    "throughput_drop": {
        "APP_EXTRA_DELAY_MS": "90",
        "APP_ERROR_RATE": "0.02",
    },
}

feature_window = deque(maxlen=KMEANS_WINDOW)
kmeans_model = None
q_learning_q = {}
sarsa_q = {}
bandit_values = {}
q_pending = None
sarsa_pending = None
last_features = None
last_rate = None


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


def fetch_metrics(seconds: int | None = None, since_epoch: float | None = None) -> dict:
    cmd = ["python3", "scripts/query_trace_metrics.py"]
    if since_epoch is not None and since_epoch > 0:
        cmd.extend(["--since-epoch", str(since_epoch)])
    elif seconds is not None and seconds > 0:
        cmd.extend(["--seconds", str(seconds)])
    result = run(cmd)
    return json.loads(result.stdout)


def generate_traffic(requests_count: int = 5) -> None:
    for _ in range(requests_count):
        try:
            with urllib.request.urlopen(GENERATOR_URL, timeout=5) as response:
                response.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            pass


def wait_for_live_traces(since_epoch: float, timeout_seconds: int = 60, delay: float = 3.0) -> dict:
    deadline = time.time() + timeout_seconds
    last = {}
    while time.time() < deadline:
        generate_traffic(10)
        metrics = fetch_metrics(since_epoch=since_epoch)
        last = metrics
        if metrics.get("total", 0) > 0 and metrics.get("qps", 0.0) > 0.0:
            return metrics
        time.sleep(delay)
    raise RuntimeError(f"timed out waiting for trace traffic; last metrics={last}")


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


def rule_rate(error_rate: float, total: int) -> float:
    if total < 5:
        return 0.1
    if error_rate >= 0.4:
        return 0.8
    if error_rate >= 0.2:
        return 0.5
    if error_rate <= 0.05:
        return 0.05
    return 0.1


def kmeans_rate(error_rate: float, avg_latency_ms: float, qps: float) -> float:
    global kmeans_model
    from sklearn.cluster import KMeans

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
    parser = argparse.ArgumentParser(description="Run one policy-based adaptive tracing experiment on Timescale OTel demo.")
    parser.add_argument("--policy", required=True, choices=["q_learning", "sarsa", "bandit", "rule", "kmeans"])
    parser.add_argument("--scenario", default="healthy", choices=sorted(SCENARIOS.keys()))
    parser.add_argument("--duration", type=int, default=20)
    parser.add_argument("--interval", type=int, default=5, help="decision interval in seconds")
    parser.add_argument("--results-subdir", default="", help="optional subdirectory under experiment_results")
    args = parser.parse_args()

    results_dir = RESULTS_DIR / args.results_subdir if args.results_subdir else RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    apply_scenario(args.scenario)
    set_sampling_rate(0.1)
    time.sleep(max(args.interval, 5))
    experiment_start = time.time()
    generate_traffic(10)
    last_metrics = wait_for_live_traces(experiment_start)

    decisions = []
    steps = max(1, args.duration // args.interval)
    current_rate = 0.1

    for _ in range(steps):
        metrics = fetch_metrics(since_epoch=experiment_start)
        error_rate = float(metrics.get("error_rate", 0.0))
        avg_latency_ms = float(metrics.get("avg_latency_ms", 0.0))
        qps = float(metrics.get("qps", 0.0))
        total = int(metrics.get("total", 0))
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
            set_sampling_rate(rate)
            current_rate = rate
            time.sleep(3)
            generate_traffic(10)
            metrics = fetch_metrics(since_epoch=experiment_start)
            error_rate = float(metrics.get("error_rate", 0.0))
            avg_latency_ms = float(metrics.get("avg_latency_ms", 0.0))
            qps = float(metrics.get("qps", 0.0))
            total = int(metrics.get("total", 0))
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
        }
        decisions.append(decision)
        last_metrics = metrics
        time.sleep(args.interval)

    rewards = [d["reward"] for d in decisions if d["reward"] is not None]
    rates = [d["chosen_rate"] for d in decisions]
    status = {
        "timestamp": time.time(),
        "error_rate": last_metrics["error_rate"] if last_metrics else 0.0,
        "avg_latency_ms": last_metrics["avg_latency_ms"] if last_metrics else 0.0,
        "qps": last_metrics["qps"] if last_metrics else 0.0,
        "total": last_metrics["total"] if last_metrics else 0,
        "chosen_rate": rates[-1] if rates else None,
        "policy_mode": args.policy,
        "reward": rewards[-1] if rewards else None,
        "state": decisions[-1]["state"] if decisions else None,
        "action_idx": decisions[-1]["action_idx"] if decisions else None,
        "reward_components": decisions[-1]["reward_components"] if decisions else None,
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
        "system": "timescale-otel-demo",
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
    sys.exit(main())
