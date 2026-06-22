# Adaptive Sampling RL Comparison

This report summarizes the RL-based adaptive sampling experiments collected from the current testbed. The comparison uses the same reward mode and the same workload per scenario.

### Faulted condition

In the faulted condition, `q_learning` achieved the highest average reward (0.0828).
Under injected faults, the comparison shows how each method responds when latency and error pressure increase.

| Method | Avg Reward | Avg Rate | Min Rate | Max Rate | Final Latency (ms) | Final QPS | Final Error Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| q_learning | 0.0828 | 0.0682 | 0.05 | 0.20 | 124.26 | 27.67 | 0.0000 |
| bandit | 0.0569 | 0.0909 | 0.05 | 0.50 | 102.03 | 38.73 | 0.0000 |
| sarsa | 0.0168 | 0.1045 | 0.05 | 0.50 | 74.15 | 34.31 | 0.0000 |

### Healthy condition

In the healthy condition, `sarsa` achieved the highest average reward (0.0905).
All methods kept sampling low, which is expected when the system is stable and there are no errors to justify aggressive tracing.

| Method | Avg Reward | Avg Rate | Min Rate | Max Rate | Final Latency (ms) | Final QPS | Final Error Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| sarsa | 0.0905 | 0.0682 | 0.05 | 0.20 | 99.77 | 58.70 | 0.0000 |
| bandit | 0.0687 | 0.0636 | 0.05 | 0.20 | 77.38 | 66.14 | 0.0000 |
| q_learning | 0.0562 | 0.0500 | 0.05 | 0.05 | 73.47 | 65.86 | 0.0000 |
