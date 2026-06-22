# Timescale OTel Demo Adaptive Tracing Notes

## Chosen System
This repo is the second microservice system for the adaptive tracing project.

It is a lightweight password generator microservice demo with five services:
- generator
- upper
- lower
- digit
- special

## Why this system
- much lighter than the large Online Boutique demo
- already instrumented with OpenTelemetry
- already includes a collector, Jaeger, Grafana, and load generator
- small enough to understand and modify quickly
- includes runtime variability and occasional slow behavior in service code

## Adaptive tracing integration
Unlike Train-Ticket, this system does not have a custom sampling controller.

The least invasive control point is the OpenTelemetry Collector in:
- `instrumented/collector/config.yaml`

This repo now includes:
- `scripts/set_adaptive_sampling.py`

That script rewrites the collector config to insert a `probabilistic_sampler`
processor into the traces pipeline and can rebuild just the collector service.

## Current workflow
1. Start the system with Docker Compose.
2. Set a collector-side sampling rate, for example:

```bash
python3 scripts/set_adaptive_sampling.py --rate 0.05 --rebuild
```

3. Verify:
- app on `http://localhost:5050/`
- Jaeger on `http://localhost:16686/search`
- Grafana on `http://localhost:3000/`

4. Build experiment automation on top of this sampling control path.

## What is done so far
- repo inspected
- service count confirmed
- collector identified as the adaptive tracing control point
- initial sampling control script added

## What remains
- run the stack locally
- verify collector-side sampling changes take effect
- define status metrics for experiments
- add experiment runner and reporting for this system
- reproduce RQ1 on this system
