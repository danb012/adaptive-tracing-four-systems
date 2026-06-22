  Timescale OpenTelemetry Demo - Complete Progress Summary

  Project Purpose
  The Timescale OpenTelemetry Demo was used as another microservice system for
  the adaptive tracing project so the research would not rely only on Train-
  Ticket. The goal for this system was to reproduce RQ1 in a second environment
  and compare RL-based adaptive tracing methods with non-RL baselines under the
  same workflow.

  What the System Is
  This system is a lightweight password-generator microservice application. It
  includes:

  - generator
  - upper
  - lower
  - digit
  - special

  The generator service calls the other four services to build a password. A
  background load generator continuously sends requests so the system produces
  distributed traces.

  The tracing stack is:

  - application services
  - OpenTelemetry Collector
  - Promscale
  - TimescaleDB
  - Jaeger
  - Grafana

  This made it a good second research system because:

  - it is smaller than Train-Ticket
  - it is easier to run locally
  - it already supports observability and tracing
  - it still produces real multi-service traces

  Initial Setup Work
  The repository was cloned into a separate folder:

  - timescale-otel-demo

  This was kept separate from:

  - train-ticket-python

  This isolation was important so each system could be configured independently
  without breaking the other.

  Adaptive Tracing Integration
  A collector-side sampling control path was added so trace volume could be
  controlled centrally, similar to what was done in Train-Ticket.

  Created:

  - timescale-otel-demo/scripts/set_adaptive_sampling.py
  - timescale-otel-demo/ADAPTIVE_TRACING_NOTES.md

  This script updates the OpenTelemetry Collector configuration and lets the
  tracing rate be changed dynamically. This was the first step in making the
  system support adaptive tracing experiments.

  Later, the script was improved so it only rebuilt and restarted the collector
  instead of unnecessarily touching the database and the rest of the stack.

  Repository and Runtime Fixes
  A number of technical issues had to be fixed before the system could be used
  reliably.

  1. Promscale version mismatch
     The repository was using:

  - timescale/promscale:0.11.0

  That version was incompatible with the extension version in the current
  TimescaleDB image, causing:

  - promscale restart loops
  - jaeger restart loops
  - zero stored traces

  This was fixed by updating:

  - docker-compose.yaml

  from:

  - timescale/promscale:0.11.0

  to:

  - timescale/promscale:0.17.0

  That stabilized the tracing backend.

  2. Python image incompatibility
     Several services used:

  - python:latest

  That pulled a much newer Python version and broke older pinned dependencies
  such as:

  - grpcio==1.43.0

  This was fixed by changing these Dockerfiles to:

  - python:3.10-slim

  Files updated:

  - instrumented/digit/Dockerfile
  - instrumented/generator/Dockerfile
  - instrumented/load/Dockerfile
  - instrumented/special/Dockerfile
  - instrumented/upper/Dockerfile

  This made the services build correctly.

  Fault Injection and Scenario Support
  To reproduce healthy and faulted experiments like Train-Ticket, service-level
  runtime controls were added.

  Two environment-based controls were introduced:

  - APP_EXTRA_DELAY_MS
  - APP_ERROR_RATE

  These were wired into:

  - upper
  - lower
  - special
  - digit
  - generator

  This allowed the system to switch between:

  - healthy
  - faulted

  conditions without changing the whole deployment manually.

  The generator service was also explicitly instrumented with Flask tracing
  support so it would participate properly in distributed traces.

  Metrics Collection
  A query path was added so experiment results could be measured directly from
  TimescaleDB.

  Created:

  - timescale-otel-demo/scripts/query_trace_metrics.py

  This script queries root spans and returns:

  - total
  - avg_latency_ms
  - error_rate
  - qps

  This was important because it gave the same kind of experiment metrics used in
  Train-Ticket, but adapted to this system’s storage backend.

  A successful manual test confirmed this was working and producing nonzero
  metrics.

  Fixed-Rate Experiment Runner
  A basic experiment runner was built before the adaptive policy layer.

  Created:

  - timescale-otel-demo/scripts/run_sampling_experiment.py

  This script could:

  - apply a sampling rate
  - apply a healthy or faulted scenario
  - wait for live traffic
  - collect metrics
  - write JSON output into experiment_results/

  This validated that the system could support experimental runs before adding
  RL and non-RL policies.

  Policy Controller Layer for RQ1
  To make this system comparable to Train-Ticket for RQ1, a policy-based
  experiment runner was built.

  Created:

  - timescale-otel-demo/scripts/run_policy_experiment.py

  Supported policies:

  - q_learning
  - sarsa
  - bandit
  - rule
  - kmeans

  This script used:

  - state from runtime metrics
  - action as the chosen sampling rate
  - reward for RL methods
  - fixed decision intervals
  - JSON experiment outputs

  This was the key step that turned the system from a tracing demo into a second
  adaptive tracing experiment platform.

  Additional Fixes for Policy Runner
  Several issues were fixed during policy-runner development.

  1. Removed unnecessary numpy dependency
     The policy runner was updated so:

  - numpy was no longer required for normal RL policies

  2. kmeans dependency handled via virtual environment
     kmeans still required:

  - scikit-learn

  A local Python virtual environment was created and used so the package could
  be installed safely without modifying the system Python.

  3. Metrics logic made more robust
     At first, policy runs produced invalid JSON files with zero metrics because
     the runner was checking too narrow a time window or trying to clear traces
     too aggressively.

  The logic was improved so it:

  - used cumulative metrics over the experiment window
  - waited for live traces
  - generated direct traffic during warm-up
  - avoided fragile trace resets

  This made the policy experiments stable enough to complete correctly.

  RQ1 Experiment Set
  The full RQ1 matrix was run for this system.

  Methods:

  - q_learning
  - sarsa
  - bandit
  - rule
  - kmeans

  Scenarios:

  - healthy
  - faulted

  This produced the full 10 experiment files in:

  - timescale-otel-demo/experiment_results/

  Results Interpretation
  The Timescale OpenTelemetry Demo produced a different pattern from Train-
  Ticket.

  Main findings:

  - rule achieved the lowest final latency in both healthy and faulted
    conditions
  - bandit was the most stable RL method on runtime behavior
  - q_learning had the highest RL average reward in the faulted scenario
  - however, q_learning also had the worst final latency in the faulted case
  - sarsa was the only policy that noticeably explored higher sampling rates in
    the healthy run
  - kmeans kept a fixed 0.10 rate and had the highest final QPS in the faulted
    case

  This meant the second system did not reproduce the exact same winner pattern
  as Train-Ticket.

  Important Limitation Found
  A major limitation was identified in the reward function used for this system.

  The current reward design gave positive contribution to:

  - higher latency
  - higher error rate

  That means:

  - higher RL reward does not necessarily mean better runtime performance

  Because of that:

  - reward values were included in the report
  - but they were interpreted carefully
  - final latency, QPS, and error rate were treated as the stronger evidence

  This limitation was clearly documented in the report.

  RQ1 Conclusion for This System
  The conclusion for this system was:

  - the Timescale OpenTelemetry Demo successfully provided another direct RL vs
    non-RL adaptive tracing comparison
  - unlike Train-Ticket, the strongest overall result on runtime metrics came
    from the non-RL rule baseline
  - bandit looked like the most stable RL policy
  - q_learning achieved the highest RL reward in the faulted run, but that was
    weakened by the reward-design issue
  - overall, this system showed that adaptive tracing results are system-
    dependent and should not be generalized from one testbed alone

  This was valuable because it strengthened the research by showing variation
  across systems instead of repeating the same exact result.

  Report Output
  A full HTML report was created for this system:

  - timescale-otel-demo/reports/rq1_timescale_otel_demo_report.html

  The report includes:

  - the research question
  - description of the Timescale OpenTelemetry Demo
  - experiment setup
  - results tables
  - visual charts
  - interpretation
  - limitations
  - conclusion
  - appendix with experiment source files

  The report wording was later cleaned up so it refers to the application by
  name and does not call it “system 2.”

  Current Status
  For the Timescale OpenTelemetry Demo, the core RQ1 work is complete.

  What is done:

  - system setup
  - tracing backend fixes
  - adaptive sampling control
  - fault scenario controls
  - metrics query path
  - policy runner
  - all 10 RQ1 runs
  - full HTML report

  What remains only as future improvement:

  - longer runs
  - repeated runs for stability
  - reward redesign
  - stronger fault scenarios