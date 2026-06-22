#!/usr/bin/env python3
import argparse
import json
import random
import subprocess
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "experiment_results"
BASE_URL = "http://localhost:8080"
TRAFFIC_PATHS = [
    "/",
    "/api/customer/owners",
    "/api/vet/vets",
    "/api/gateway/owners/1",
]
ACTION_VALUES = [0.05, 0.1, 0.2, 0.5, 0.8]
ERROR_THRESHOLDS = [0.01, 0.05, 0.2]
LATENCY_THRESHOLDS = [20.0, 80.0, 200.0]
QPS_THRESHOLDS = [2.0, 5.0, 10.0]
KMEANS_K = 3
KMEANS_WINDOW = 200
EPSILON = 0.1
ALPHA = 0.2
GAMMA = 0.9

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


def fetch_metrics() -> dict:
    result = run(["python3", "scripts/query_trace_metrics.py", "--lookback-seconds", "60"])
    return json.loads(result.stdout)


def fetch_window_metrics(start_ms: int, end_ms: int) -> dict:
    lookback = max(45, int((end_ms - start_ms) / 1000) + 30)
    result = run(["python3", "scripts/query_trace_metrics.py", "--lookback-seconds", str(lookback)])
    return json.loads(result.stdout)


def set_sampling_rate(rate: float) -> None:
    run(["python3", "scripts/set_adaptive_sampling.py", "--rate", str(rate), "--restart"])
    time.sleep(8)


def disable_faults() -> None:
    for service in ("customers", "visits", "vets"):
        try:
            run(["bash", "scripts/chaos/call_chaos.sh", service, "watcher_disable"])
        except subprocess.CalledProcessError:
            pass


def apply_scenario(scenario: str) -> None:
    disable_faults()
    if scenario in {"faulted", "latency_spike"}:
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
            return
        except subprocess.CalledProcessError:
            pass
    if scenario == "error_burst":
        try:
            run(
                [
                    "bash",
                    "scripts/chaos/call_chaos.sh",
                    "visits",
                    "attacks_enable_exception",
                    "watcher_enable_restcontroller",
                ]
            )
            return
        except subprocess.CalledProcessError:
            pass


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
    if error_rate >= 0.2:
        return 0.8
    if error_rate >= 0.05:
        return 0.5
    return 0.05


def kmeans_rate(error_rate: float, avg_latency_ms: float, qps: float):
    global kmeans_model
    try:
        from sklearn.cluster import KMeans
    except ImportError as e:
        raise SystemExit(
            "K-Means policy requires scikit-learn. Install it in your Python environment (for example: `pip install scikit-learn`)."
        ) from e

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


def traffic_profile(scenario: str) -> tuple[int, float]:
    if scenario == "healthy":
        return 2, 0.2
    if scenario == "throughput_drop":
        return 1, 0.45
    if scenario == "error_burst":
        return 3, 0.15
    if scenario == "latency_spike":
        return 3, 0.12
    return 4, 0.1


def reset_policy_state() -> None:
    global kmeans_model, q_pending, sarsa_pending, last_features, last_rate
    feature_window.clear()
    q_learning_q.clear()
    sarsa_q.clear()
    bandit_values.clear()
    kmeans_model = None
    q_pending = None
    sarsa_pending = None
    last_features = None
    last_rate = None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Petclinic policy experiment.")
    parser.add_argument("--policy", choices=["q_learning", "sarsa", "bandit", "rule", "kmeans"], required=True)
    parser.add_argument("--scenario", choices=["healthy", "faulted", "latency_spike", "error_burst", "throughput_drop"], default="healthy")
    parser.add_argument("--duration", type=int, default=20)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--results-subdir", default="", help="optional subdirectory under experiment_results")
    args = parser.parse_args()

    results_dir = RESULTS_DIR / args.results_subdir if args.results_subdir else RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    reset_policy_state()
    apply_scenario(args.scenario)
    time.sleep(5)
    warm_up_traffic()

    decisions = []
    start_ts = time.time()
    current_rate = 0.05
    set_sampling_rate(current_rate)

    while time.time() - start_ts < args.duration:
        interval_start_ms = int(time.time() * 1000)
        burst, pause = traffic_profile(args.scenario)
        generate_traffic(args.interval, burst=burst, pause=pause)
        time.sleep(18)
        interval_end_ms = int(time.time() * 1000)
        metrics = fetch_window_metrics(interval_start_ms, interval_end_ms)

        error_rate = metrics["error_rate"]
        avg_latency_ms = metrics["avg_latency_ms"]
        qps = metrics["qps"]
        total = metrics["total"]

        if args.policy == "q_learning":
            rate, reward, state, action_idx, components = q_learning_rate(error_rate, avg_latency_ms, qps)
        elif args.policy == "sarsa":
            rate, reward, state, action_idx, components = sarsa_rate(error_rate, avg_latency_ms, qps)
        elif args.policy == "bandit":
            rate, reward, state, action_idx, components = bandit_rate(error_rate, avg_latency_ms, qps)
        elif args.policy == "rule":
            rate = rule_rate(error_rate, total)
            reward, components = compute_reward(error_rate, avg_latency_ms, qps, rate)
            state = state_from_features(error_rate, avg_latency_ms, qps)
            action_idx = ACTION_VALUES.index(rate)
        else:
            rate = kmeans_rate(error_rate, avg_latency_ms, qps)
            reward, components = compute_reward(error_rate, avg_latency_ms, qps, rate)
            state = state_from_features(error_rate, avg_latency_ms, qps)
            action_idx = ACTION_VALUES.index(rate)

        if rate != current_rate:
            current_rate = rate
            set_sampling_rate(current_rate)
            warm_up_traffic(4)

        snapshot = {
            "timestamp": time.time(),
            "error_rate": error_rate,
            "avg_latency_ms": avg_latency_ms,
            "qps": qps,
            "total": total,
            "chosen_rate": current_rate,
            "policy_mode": args.policy,
            "reward": reward,
            "state": list(state),
            "action_idx": action_idx,
            "reward_components": components,
        }
        decisions.append(snapshot)

    status = decisions[-1] if decisions else {
        "timestamp": time.time(),
        "error_rate": 0.0,
        "avg_latency_ms": 0.0,
        "qps": 0.0,
        "total": 0,
        "chosen_rate": current_rate,
        "policy_mode": args.policy,
        "reward": 0.0,
        "state": [0, 0, 0],
        "action_idx": ACTION_VALUES.index(current_rate),
        "reward_components": {},
    }

    rewards = [item["reward"] for item in decisions] or [0.0]
    rates = [item["chosen_rate"] for item in decisions] or [current_rate]
    summary = {
        "policy_mode": args.policy,
        "reward_mode": "balanced",
        "decision_count": len(decisions),
        "avg_reward": sum(rewards) / len(rewards),
        "min_reward": min(rewards),
        "max_reward": max(rewards),
        "avg_rate": sum(rates) / len(rates),
        "min_rate": min(rates),
        "max_rate": max(rates),
        "last_state": status["state"],
        "last_action_idx": status["action_idx"],
    }

    payload = {
        "system": "spring-petclinic-microservices",
        "policy": args.policy,
        "reward_mode": "balanced",
        "scenario": args.scenario,
        "duration_seconds": args.duration,
        "decision_interval_seconds": args.interval,
        "captured_at": time.time(),
        "status": status,
        "summary": summary,
        "decisions": {"status": "ok", "items": decisions},
    }

    out_path = results_dir / f"{args.policy}__balanced__{args.scenario}.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="ascii")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
