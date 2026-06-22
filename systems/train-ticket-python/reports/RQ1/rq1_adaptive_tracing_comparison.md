# Adaptive Tracing Method Comparison Report

## Overview

This report summarizes the adaptive tracing experiments performed on the Train-Ticket Python testbed. The goal was to compare RL-based and non-RL adaptive tracing methods under the same workload pattern.

The methods can include RL-based strategies such as `q_learning`, `sarsa`, and `bandit`, as well as non-RL baselines such as `rule` and `kmeans`. Runs collect metrics from the sampling agent status and summary endpoints.

## Method

The evaluation used the same adaptive tracing testbed, the same workload generation process, and the same runtime metrics (error rate, average latency, QPS, and sampling behavior). Two operating scenarios were tested:

- `Healthy Condition`: Baseline operating condition with low injected faults (ORDER_DELAY_MS=50, ORDER_ERROR_RATE=0.01, TRAVEL_DELAY_MS=30, TRAVEL_ERROR_RATE=0.0).
- `Faulted Condition`: Stress condition with higher injected latency and error pressure (ORDER_DELAY_MS=200, ORDER_ERROR_RATE=0.08, TRAVEL_DELAY_MS=120, TRAVEL_ERROR_RATE=0.03).

## Results

### Healthy Condition

In the healthy batch, `q_learning` achieved the highest average reward (0.1031). Across the methods, sampling stayed relatively low, which is consistent with a stable system where extra traces are mostly overhead.

| Method | Avg Reward | Avg Rate | Min Rate | Max Rate | Final Latency (ms) | Final QPS | Final Error Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| q_learning | 0.1031 | 0.0500 | 0.05 | 0.05 | 119.23 | 51.79 | 0.0000 |
| bandit | 0.0937 | 0.0500 | 0.05 | 0.05 | 118.58 | 39.46 | 0.0000 |
| sarsa | 0.0760 | 0.0772 | 0.05 | 0.80 | 120.68 | 62.55 | 0.0000 |
| kmeans | n/a | 0.1000 | 0.10 | 0.10 | 120.31 | 43.27 | 0.0000 |
| rule | n/a | 0.0500 | 0.05 | 0.05 | 121.34 | 45.34 | 0.0000 |

### Faulted Condition

In the faulted batch, `q_learning` achieved the highest average reward (0.0767). The injected delays lowered throughput and increased latency, so the comparison reflects how each method behaves under degraded performance.

| Method | Avg Reward | Avg Rate | Min Rate | Max Rate | Final Latency (ms) | Final QPS | Final Error Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| q_learning | 0.0767 | 0.0545 | 0.05 | 0.10 | 96.29 | 35.36 | 0.0000 |
| bandit | 0.0637 | 0.0500 | 0.05 | 0.05 | 116.55 | 33.23 | 0.0000 |
| sarsa | 0.0034 | 0.1182 | 0.05 | 0.80 | 99.05 | 32.53 | 0.0000 |
| kmeans | n/a | 0.1000 | 0.10 | 0.10 | 134.88 | 29.22 | 0.0000 |
| rule | n/a | 0.0500 | 0.05 | 0.05 | 118.45 | 15.12 | 0.0000 |

## Interpretation

Under healthy conditions, the methods generally reduced tracing activity, which is the expected behavior when the system is stable and extra traces provide limited benefit.

Under the faulted condition, the methods responded differently as latency increased and throughput dropped. This creates a useful basis for comparing how each method balances observability value against tracing cost.

At this stage, the strongest comparison signal is average reward together with average sampling rate. A method with higher reward and a controlled sampling rate is preferable because it suggests better adaptation without unnecessary overhead.

## Limitations

Across these batches, the final measured order-service error rate remained 0.0. The faulted scenario therefore mainly reflects latency and throughput degradation rather than persistent request failures. A later batch with stronger error-inducing conditions would help evaluate how the policies respond to explicit failures.

## Conclusion

The implementation and experiment pipeline are now complete enough for comparative evaluation. These results provide a side-by-side view of adaptive tracing behavior and can be extended with additional fault scenarios, more baselines, or longer runs in the next phase.
