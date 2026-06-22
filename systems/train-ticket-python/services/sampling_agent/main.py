import asyncio
import os
import httpx
import json
import time
from collections import deque
import numpy as np
from sklearn.cluster import KMeans
import random
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from services.common.tracing import init_tracing
from services.common.sampling import start_sampling_poller

ORDER_STATS_URL = os.getenv("ORDER_STATS_URL", "http://order:8000/stats")
SAMPLING_CONFIG_URL = os.getenv("SAMPLING_CONFIG_URL", "http://sampling-config:8000/sampling")
POLL_INTERVAL = float(os.getenv("AGENT_POLL_INTERVAL", "10"))
MIN_RATE = float(os.getenv("MIN_SAMPLING_RATE", "0.05"))
MAX_RATE = float(os.getenv("MAX_SAMPLING_RATE", "0.8"))
POLICY_MODE = os.getenv("POLICY_MODE", "rule").lower()
KMEANS_WINDOW = int(os.getenv("KMEANS_WINDOW", "200"))
KMEANS_K = int(os.getenv("KMEANS_K", "3"))
RL_ACTIONS = os.getenv("RL_ACTIONS", "0.05,0.1,0.2,0.5,0.8")
RL_EPSILON = float(os.getenv("RL_EPSILON", "0.1"))
RL_ALPHA = float(os.getenv("RL_ALPHA", "0.2"))
RL_GAMMA = float(os.getenv("RL_GAMMA", "0.9"))
RL_REWARD_MODE = os.getenv("RL_REWARD_MODE", "balanced").lower()
RL_REWARD_ERROR_WEIGHT = float(os.getenv("RL_REWARD_ERROR_WEIGHT", "2.0"))
RL_REWARD_LATENCY_WEIGHT = float(os.getenv("RL_REWARD_LATENCY_WEIGHT", "0.5"))
RL_REWARD_COST_WEIGHT = float(os.getenv("RL_REWARD_COST_WEIGHT", "1.0"))
RL_REWARD_STABILITY_WEIGHT = float(os.getenv("RL_REWARD_STABILITY_WEIGHT", "0.2"))
RL_REWARD_DRIFT_WEIGHT = float(os.getenv("RL_REWARD_DRIFT_WEIGHT", "0.5"))
RL_ERROR_BINS = os.getenv("RL_ERROR_BINS", "0.05,0.2,0.5")
RL_LATENCY_BINS = os.getenv("RL_LATENCY_BINS", "50,150,300")
RL_QPS_BINS = os.getenv("RL_QPS_BINS", "20,50,100")
DECISION_LOG_PATH = os.getenv("AGENT_DECISION_LOG", "/tmp/agent_decisions.jsonl")
STATUS_PATH = os.getenv("AGENT_STATUS_PATH", "/tmp/agent_status.json")
SUMMARY_PATH = os.getenv("AGENT_SUMMARY_PATH", "/tmp/agent_summary.json")

_last_status = {
    "timestamp": None,
    "error_rate": None,
    "avg_latency_ms": None,
    "qps": None,
    "total": None,
    "chosen_rate": None,
}
_feature_window = deque(maxlen=KMEANS_WINDOW)
_kmeans_model = None
_q_learning_q = {}
_sarsa_q = {}
_bandit_values = {}
_q_pending = None
_sarsa_pending = None
_recent_rewards = deque(maxlen=200)
_recent_rates = deque(maxlen=200)
_last_features = None
_last_rate = None


async def compute_rate(error_rate: float, total: int) -> float:
    if total < 20:
        return 0.1
    if error_rate >= 0.4:
        return min(MAX_RATE, 0.8)
    if error_rate >= 0.2:
        return min(MAX_RATE, 0.5)
    if error_rate <= 0.05:
        return max(MIN_RATE, 0.05)
    return 0.1


def _kmeans_rate(error_rate: float, avg_latency_ms: float, qps: float) -> float:
    global _kmeans_model
    _feature_window.append([error_rate, avg_latency_ms, qps])
    if len(_feature_window) < max(10, KMEANS_K * 5):
        return 0.1

    X = np.array(_feature_window, dtype=float)
    if _kmeans_model is None or len(_feature_window) % 20 == 0:
        _kmeans_model = KMeans(n_clusters=KMEANS_K, n_init=10, random_state=42)
        _kmeans_model.fit(X)

    label = _kmeans_model.predict(np.array([[error_rate, avg_latency_ms, qps]]))[0]
    centers = _kmeans_model.cluster_centers_
    # Map clusters to rates by ordering on error_rate then latency then qps
    order = sorted(
        range(len(centers)),
        key=lambda i: (centers[i][0], centers[i][1], centers[i][2]),
    )
    rank = order.index(label)
    if rank == len(order) - 1:
        return min(MAX_RATE, 0.8)
    if rank == 0:
        return max(MIN_RATE, 0.05)
    return 0.2


def _parse_floats(value: str) -> list[float]:
    return [float(v.strip()) for v in value.split(",") if v.strip()]


RL_ACTION_VALUES = _parse_floats(RL_ACTIONS)
RL_ERROR_THRESHOLDS = _parse_floats(RL_ERROR_BINS)
RL_LATENCY_THRESHOLDS = _parse_floats(RL_LATENCY_BINS)
RL_QPS_THRESHOLDS = _parse_floats(RL_QPS_BINS)


def _bin(value: float, thresholds: list[float]) -> int:
    for idx, cutoff in enumerate(thresholds):
        if value <= cutoff:
            return idx
    return len(thresholds)


def _state_from_features(error_rate: float, avg_latency_ms: float, qps: float) -> tuple[int, int, int]:
    return (
        _bin(error_rate, RL_ERROR_THRESHOLDS),
        _bin(avg_latency_ms, RL_LATENCY_THRESHOLDS),
        _bin(qps, RL_QPS_THRESHOLDS),
    )


def _compute_drift(error_rate: float, avg_latency_ms: float, qps: float) -> float:
    global _last_features
    if _last_features is None:
        _last_features = (error_rate, avg_latency_ms, qps)
        return 0.0

    prev_error_rate, prev_latency_ms, prev_qps = _last_features
    drift = (
        abs(error_rate - prev_error_rate)
        + abs(avg_latency_ms - prev_latency_ms) / 1000.0
        + abs(qps - prev_qps) / 100.0
    )
    _last_features = (error_rate, avg_latency_ms, qps)
    return drift


def _reward_weights_for_mode() -> tuple[float, float, float, float, float]:
    if RL_REWARD_MODE == "error_focus":
        return (RL_REWARD_ERROR_WEIGHT * 1.5, RL_REWARD_LATENCY_WEIGHT, RL_REWARD_COST_WEIGHT, RL_REWARD_STABILITY_WEIGHT, RL_REWARD_DRIFT_WEIGHT)
    if RL_REWARD_MODE == "latency_focus":
        return (RL_REWARD_ERROR_WEIGHT, RL_REWARD_LATENCY_WEIGHT * 1.5, RL_REWARD_COST_WEIGHT, RL_REWARD_STABILITY_WEIGHT, RL_REWARD_DRIFT_WEIGHT)
    if RL_REWARD_MODE == "cost_focus":
        return (RL_REWARD_ERROR_WEIGHT, RL_REWARD_LATENCY_WEIGHT, RL_REWARD_COST_WEIGHT * 1.5, RL_REWARD_STABILITY_WEIGHT, RL_REWARD_DRIFT_WEIGHT)
    if RL_REWARD_MODE == "stream_adaptive":
        return (RL_REWARD_ERROR_WEIGHT, RL_REWARD_LATENCY_WEIGHT, RL_REWARD_COST_WEIGHT, RL_REWARD_STABILITY_WEIGHT * 0.5, RL_REWARD_DRIFT_WEIGHT * 1.5)
    return (
        RL_REWARD_ERROR_WEIGHT,
        RL_REWARD_LATENCY_WEIGHT,
        RL_REWARD_COST_WEIGHT,
        RL_REWARD_STABILITY_WEIGHT,
        RL_REWARD_DRIFT_WEIGHT,
    )


def _compute_reward(error_rate: float, avg_latency_ms: float, qps: float, rate: float) -> tuple[float, dict]:
    global _last_rate

    error_w, latency_w, cost_w, stability_w, drift_w = _reward_weights_for_mode()
    drift_score = _compute_drift(error_rate, avg_latency_ms, qps)
    previous_rate = _last_rate
    change_penalty = abs(rate - previous_rate) if previous_rate is not None else 0.0

    error_component = error_w * error_rate
    latency_component = latency_w * (avg_latency_ms / 1000.0)
    cost_component = cost_w * rate
    stability_component = stability_w * change_penalty
    drift_component = drift_w * drift_score

    reward = error_component + latency_component + drift_component - cost_component - stability_component
    _last_rate = rate

    components = {
        "mode": RL_REWARD_MODE,
        "error_component": error_component,
        "latency_component": latency_component,
        "drift_component": drift_component,
        "cost_component": cost_component,
        "stability_component": stability_component,
        "drift_score": drift_score,
        "previous_rate": previous_rate,
    }
    return reward, components


def _select_action(values: list[float]) -> int:
    if random.random() < RL_EPSILON:
        return random.randrange(len(RL_ACTION_VALUES))
    return int(np.argmax(values))


def _q_learning_rate(
    error_rate: float, avg_latency_ms: float, qps: float
) -> tuple[float, float, tuple[int, int, int], int, dict]:
    global _q_pending
    state = _state_from_features(error_rate, avg_latency_ms, qps)
    q_values = _q_learning_q.setdefault(state, [0.0 for _ in RL_ACTION_VALUES])

    if _q_pending is not None:
        prev_state, prev_action_idx, prev_reward = _q_pending
        prev_values = _q_learning_q.setdefault(prev_state, [0.0 for _ in RL_ACTION_VALUES])
        td_target = prev_reward + RL_GAMMA * max(q_values)
        prev_values[prev_action_idx] = prev_values[prev_action_idx] + RL_ALPHA * (
            td_target - prev_values[prev_action_idx]
        )

    action_idx = _select_action(q_values)
    rate = RL_ACTION_VALUES[action_idx]
    reward, reward_components = _compute_reward(error_rate, avg_latency_ms, qps, rate)
    _q_pending = (state, action_idx, reward)
    return rate, reward, state, action_idx, reward_components


def _sarsa_rate(
    error_rate: float, avg_latency_ms: float, qps: float
) -> tuple[float, float, tuple[int, int, int], int, dict]:
    global _sarsa_pending
    state = _state_from_features(error_rate, avg_latency_ms, qps)
    q_values = _sarsa_q.setdefault(state, [0.0 for _ in RL_ACTION_VALUES])
    action_idx = _select_action(q_values)

    if _sarsa_pending is not None:
        prev_state, prev_action_idx, prev_reward = _sarsa_pending
        prev_values = _sarsa_q.setdefault(prev_state, [0.0 for _ in RL_ACTION_VALUES])
        td_target = prev_reward + RL_GAMMA * q_values[action_idx]
        prev_values[prev_action_idx] = prev_values[prev_action_idx] + RL_ALPHA * (
            td_target - prev_values[prev_action_idx]
        )

    rate = RL_ACTION_VALUES[action_idx]
    reward, reward_components = _compute_reward(error_rate, avg_latency_ms, qps, rate)
    _sarsa_pending = (state, action_idx, reward)
    return rate, reward, state, action_idx, reward_components


def _bandit_rate(
    error_rate: float, avg_latency_ms: float, qps: float
) -> tuple[float, float, tuple[int, int, int], int, dict]:
    state = _state_from_features(error_rate, avg_latency_ms, qps)
    values = _bandit_values.setdefault(state, [0.0 for _ in RL_ACTION_VALUES])
    action_idx = _select_action(values)
    rate = RL_ACTION_VALUES[action_idx]
    reward, reward_components = _compute_reward(error_rate, avg_latency_ms, qps, rate)
    values[action_idx] = values[action_idx] + RL_ALPHA * (reward - values[action_idx])
    return rate, reward, state, action_idx, reward_components


def _write_status(status: dict) -> None:
    try:
        with open(STATUS_PATH, "w", encoding="utf-8") as handle:
            json.dump(status, handle)
    except OSError:
        pass


def _append_decision(entry: dict) -> None:
    try:
        with open(DECISION_LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def _write_summary() -> None:
    if not _recent_rewards or not _recent_rates:
        return

    summary = {
        "policy_mode": _last_status.get("policy_mode"),
        "reward_mode": RL_REWARD_MODE,
        "decision_count": len(_recent_rewards),
        "avg_reward": sum(_recent_rewards) / len(_recent_rewards),
        "min_reward": min(_recent_rewards),
        "max_reward": max(_recent_rewards),
        "avg_rate": sum(_recent_rates) / len(_recent_rates),
        "min_rate": min(_recent_rates),
        "max_rate": max(_recent_rates),
        "last_state": _last_status.get("state"),
        "last_action_idx": _last_status.get("action_idx"),
    }
    try:
        with open(SUMMARY_PATH, "w", encoding="utf-8") as handle:
            json.dump(summary, handle)
    except OSError:
        pass


async def main():
    init_tracing("sampling-agent")
    HTTPXClientInstrumentor().instrument()
    start_sampling_poller()
    tracer = trace.get_tracer("sampling-agent")
    async with httpx.AsyncClient(timeout=2.0) as client:
        while True:
            try:
                with tracer.start_as_current_span("sampling-agent.tick") as span:
                    stats_resp = await client.get(ORDER_STATS_URL)
                    if stats_resp.status_code == 200:
                        stats = stats_resp.json()
                        error_rate = float(stats.get("error_rate", 0.0))
                        avg_latency_ms = float(stats.get("avg_latency_ms", 0.0))
                        qps = float(stats.get("qps", 0.0))
                        total = int(stats.get("total", 0))
                        reward = None
                        state = None
                        action_idx = None
                        reward_components = None
                        if POLICY_MODE == "kmeans":
                            new_rate = _kmeans_rate(error_rate, avg_latency_ms, qps)
                        elif POLICY_MODE == "q_learning":
                            new_rate, reward, state, action_idx, reward_components = _q_learning_rate(
                                error_rate, avg_latency_ms, qps
                            )
                        elif POLICY_MODE == "sarsa":
                            new_rate, reward, state, action_idx, reward_components = _sarsa_rate(
                                error_rate, avg_latency_ms, qps
                            )
                        elif POLICY_MODE == "bandit":
                            new_rate, reward, state, action_idx, reward_components = _bandit_rate(
                                error_rate, avg_latency_ms, qps
                            )
                        elif POLICY_MODE == "rl":
                            new_rate, reward, state, action_idx, reward_components = _q_learning_rate(
                                error_rate, avg_latency_ms, qps
                            )
                        else:
                            new_rate = await compute_rate(error_rate, total)
                        span.set_attribute("error_rate", error_rate)
                        span.set_attribute("avg_latency_ms", avg_latency_ms)
                        span.set_attribute("qps", qps)
                        span.set_attribute("total", total)
                        span.set_attribute("new_rate", new_rate)
                        span.set_attribute("policy_mode", POLICY_MODE)
                        if reward is not None:
                            span.set_attribute("reward", reward)
                        if state is not None:
                            span.set_attribute("state", str(state))
                            span.set_attribute("action_idx", int(action_idx))
                        if reward_components is not None:
                            span.set_attribute("reward_mode", reward_components["mode"])
                            span.set_attribute("reward_drift_score", reward_components["drift_score"])
                        await client.put(SAMPLING_CONFIG_URL, json={"rate": new_rate})
                        now = time.time()
                        _last_status.update(
                            {
                                "timestamp": now,
                                "error_rate": error_rate,
                                "avg_latency_ms": avg_latency_ms,
                                "qps": qps,
                                "total": total,
                                "chosen_rate": new_rate,
                                "policy_mode": POLICY_MODE,
                                "reward": reward,
                                "state": state,
                                "action_idx": action_idx,
                                "reward_components": reward_components,
                            }
                        )
                        if reward is not None:
                            _recent_rewards.append(reward)
                        _recent_rates.append(new_rate)
                        _write_status(_last_status)
                        _write_summary()
                        _append_decision(_last_status)
            except httpx.HTTPError:
                pass
            await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
