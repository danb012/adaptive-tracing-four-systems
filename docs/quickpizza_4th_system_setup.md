# QuickPizza Fourth-System Setup

## Why QuickPizza

QuickPizza is the fourth system because it is:
- an official Grafana observability demo
- available in both monolithic and microservices modes
- already instrumented for metrics, traces, logs, and profiling
- lighter than large e-commerce benchmarks, while still useful for real operational observability work

For this project, the correct starting point is the **local microservices stack** so the fourth system remains comparable to the first three systems.

Official source used:
- GitHub: `https://github.com/grafana/quickpizza`
- The repository README describes:
  - `compose.grafana-local-stack.microservices.yaml`
  - `compose.grafana-local-stack.monolithic.yaml`
  - local Grafana OSS observability stack

## Chosen deployment path

Use:
- `compose.grafana-local-stack.microservices.yaml`

Reason:
- it keeps QuickPizza in microservice mode
- it runs against a local Grafana OSS stack
- it avoids the need for Grafana Cloud credentials

## Expected local endpoints

After startup, expect at least:
- QuickPizza app: `http://localhost:3333`
- Grafana: `http://localhost:3000`

Additional ports depend on the compose file, but Grafana is the main UI checkpoint.

## Setup commands

```bash
cd /Users/dan
git clone https://github.com/grafana/quickpizza.git
cd quickpizza
docker compose -f compose.grafana-local-stack.microservices.yaml up -d
```

## Validation commands

```bash
cd /Users/dan/quickpizza
docker compose -f compose.grafana-local-stack.microservices.yaml ps
open http://localhost:3333
open http://localhost:3000
```

## What to verify

1. the QuickPizza UI loads on `localhost:3333`
2. Grafana loads on `localhost:3000`
3. after clicking the app, traces and metrics appear in the local Grafana stack

## Planned integration work after base startup

Once the stack is confirmed healthy, the next work is:
- identify the service names in the microservices deployment
- identify the trace pipeline control point
  - likely Grafana Alloy / OpenTelemetry sampling configuration
- add a sampling-control script
- add a metrics/traces query script
- add the same experiment workflow used in the other systems:
  - fixed-rate runs
  - controller runs
  - comparative report generation

## Known blocker in this Codex session

This Codex session cannot reach GitHub directly because outbound DNS/network resolution is blocked, so the repository could not be cloned from inside the session. The setup commands above need to be run from the local terminal.
