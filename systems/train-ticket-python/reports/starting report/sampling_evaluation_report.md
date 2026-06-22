# Adaptive Sampling RL Evaluation Report

## Overview

This report summarizes the adaptive sampling experiments performed on the Train-Ticket Python testbed. The goal was to compare multiple reinforcement learning methods under the same reward design and the same workload pattern.

The three RL methods evaluated were `q_learning`, `sarsa`, and `bandit`. All runs used the `balanced` reward mode and collected metrics from the sampling agent status and summary endpoints.

## Method

The evaluation used the same sampling-agent implementation, the same action space of candidate sampling rates, and the same runtime metrics (error rate, average latency, and QPS). Two operating scenarios were tested:

- `Healthy Condition`: Baseline operating condition with low injected faults (ORDER_DELAY_MS=50, ORDER_ERROR_RATE=0.01, TRAVEL_DELAY_MS=30, TRAVEL_ERROR_RATE=0.0).
- `Faulted Condition`: Stress condition with higher injected latency and error pressure (ORDER_DELAY_MS=200, ORDER_ERROR_RATE=0.08, TRAVEL_DELAY_MS=120, TRAVEL_ERROR_RATE=0.03).

## Results

### Healthy Condition

In the healthy batch, `sarsa` achieved the highest average reward (0.0905). All methods pushed sampling toward low levels, which is consistent with a stable system where extra traces are mostly overhead.

| Method | Avg Reward | Avg Rate | Min Rate | Max Rate | Final Latency (ms) | Final QPS | Final Error Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| sarsa | 0.0905 | 0.0682 | 0.05 | 0.20 | 99.77 | 58.70 | 0.0000 |
| bandit | 0.0687 | 0.0636 | 0.05 | 0.20 | 77.38 | 66.14 | 0.0000 |
| q_learning | 0.0562 | 0.0500 | 0.05 | 0.05 | 73.47 | 65.86 | 0.0000 |

### Faulted Condition

In the faulted batch, `q_learning` achieved the highest average reward (0.0828). The injected delays lowered throughput and increased latency, so the comparison reflects how each method behaves under degraded performance.

| Method | Avg Reward | Avg Rate | Min Rate | Max Rate | Final Latency (ms) | Final QPS | Final Error Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| q_learning | 0.0828 | 0.0682 | 0.05 | 0.20 | 124.26 | 27.67 | 0.0000 |
| bandit | 0.0569 | 0.0909 | 0.05 | 0.50 | 102.03 | 38.73 | 0.0000 |
| sarsa | 0.0168 | 0.1045 | 0.05 | 0.50 | 74.15 | 34.31 | 0.0000 |

## Interpretation

Under healthy conditions, all three methods reduced sampling to low levels, which is the expected behavior when the system is stable and extra traces provide limited benefit.

Under the faulted condition, the methods responded differently as latency increased and throughput dropped. This creates a useful basis for comparing how each method balances observability value against tracing cost.

At this stage, the strongest comparison signal is average reward together with average sampling rate. A method with higher reward and a controlled sampling rate is preferable because it suggests better adaptation without unnecessary overhead.

## Limitations

Across these batches, the final measured order-service error rate remained 0.0. The faulted scenario therefore mainly reflects latency and throughput degradation rather than persistent request failures. A later batch with stronger error-inducing conditions would help evaluate how the policies respond to explicit failures.

## Conclusion

The implementation and experiment pipeline are now complete enough for comparative evaluation. These results provide the first side-by-side view of RL-based adaptive sampling behavior and can be extended with additional fault scenarios or longer runs in the next phase.
