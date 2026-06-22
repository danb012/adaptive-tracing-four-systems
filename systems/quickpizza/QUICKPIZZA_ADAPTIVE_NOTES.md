# QuickPizza Adaptive Tracing Notes

This repository is the fourth candidate system for the adaptive tracing study.

## Current integration state

Implemented:
- local microservices deployment path
- local adaptive compose override: `compose.adaptive.microservices.yaml`
- trace sampling control via `QUICKPIZZA_TRACE_SAMPLING_RATE`
- sampling control script: `scripts/set_adaptive_sampling.py`
- metrics query script: `scripts/query_trace_metrics.py`
- fixed-rate experiment runner: `scripts/run_sampling_experiment.py`
- policy experiment runner: `scripts/run_policy_experiment.py`
- full RQ1 matrix runner: `scripts/run_rq1_matrix.py`
- full RQ2 matrix runner: `scripts/run_rq2_matrix.py`
- QuickPizza RQ2 report generator: `scripts/generate_rq2_report.py`

## Startup path for adaptive workflow

```bash
cd /Users/dan/quickpizza
docker compose --env-file .env.adaptive \
  -f compose.grafana-local-stack.microservices.yaml \
  -f compose.adaptive.microservices.yaml \
  up -d --build
```

## Validation

```bash
python3 scripts/query_trace_metrics.py --lookback-seconds 60
python3 scripts/run_sampling_experiment.py --rate 0.05 --scenario healthy --duration 30
python3 scripts/run_sampling_experiment.py --rate 0.05 --scenario error_burst --duration 30
python3 scripts/run_rq1_matrix.py
python3 scripts/run_rq2_matrix.py
python3 scripts/generate_rq2_report.py
```

## Current scenario model

- `healthy`: normal POST traffic to `/api/pizza`
- `latency_spike`: adds deterministic request-side delay headers
- `error_burst`: injects deterministic ingredient-fetch failures that surface as observable public API `5xx` responses
- `throughput_drop`: reduces request intensity

## Current status

QuickPizza now has the same core experiment structure as the other systems:
- controller-comparison policy runs for `healthy` and `faulted`
- runtime-change RQ2 runs for `healthy`, `latency_spike`, `error_burst`, and `throughput_drop`
- fixed-rate scenario checks
- generated QuickPizza RQ2 HTML reporting

## Remaining caveats

- Prometheus scrape health is still not fully clean across every QuickPizza target.
- Some policy/scenario combinations remain noisier than the other three systems, so interpretation should still favor the regenerated artifacts over the earliest exploratory runs.
