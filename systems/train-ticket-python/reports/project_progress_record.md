# Project Progress Record

## Project Direction
The overall project is about adaptive tracing in microservice systems, with reinforcement learning as one important angle. The goal is to study how tracing behavior can be adjusted automatically at runtime so that the system keeps useful observability information without creating unnecessary overhead.

## System and Testbed Setup
The main system used so far is the Train-Ticket Python microservice testbed. This is a distributed microservice application built with multiple FastAPI services and deployed with Docker Compose. The system was instrumented with:
- OpenTelemetry for tracing
- Jaeger for trace collection and visualization
- a configurable sampling layer so tracing rates can be changed at runtime

An adaptive sampling and tracing control setup was added, including:
- a `sampling-agent`
- a `sampling-config` service
- a `sampling-agent-status` service
- status and summary endpoints for monitoring decisions during experiments

This created a working environment for testing adaptive tracing policies under live traffic.

## Adaptive Tracing Methods Implemented
Several adaptive tracing decision methods were implemented and made runnable in the system.

RL-based methods:
- `q_learning`
- `sarsa`
- `bandit`

Non-RL methods:
- `rule`
- `kmeans`

The system was also extended with:
- configurable reward modes
- state, action, and reward logging
- decision history collection
- summary and status endpoints

This allowed experiments to compare how different methods choose tracing rates over time.

## Experiment Infrastructure
An experiment runner script was created and improved so that experiments could be repeated in a controlled way. The script:
- restarts the required services
- clears old agent logs
- waits for live traffic
- runs the chosen policy for a fixed duration
- collects `status`, `summary`, and `decisions`
- writes results into JSON files

During this process, several practical fixes were made:
- connection reset handling was improved
- old agent outputs were cleared before runs
- the runner was changed so seat reset failures do not stop the experiment
- forced Docker rebuilds were removed from each run to speed up execution
- the report generator was updated to handle both RL and non-RL methods correctly

This made the experiment workflow stable enough for repeated research runs.

## Healthy and Faulted Scenarios
Two runtime scenarios were defined for the experiments.

Healthy condition:
- low injected delay
- low fault pressure
- mostly stable service behavior

Faulted condition:
- higher injected latency
- stronger performance degradation
- lower throughput and more stressful runtime conditions

These scenarios were used to study how adaptive tracing methods behave under normal and degraded system states.

## Initial RL Experiments
The first experiments were run with the RL methods:
- `q_learning`
- `sarsa`
- `bandit`

At first, some runs were invalid because the system had no live traffic, so metrics like `qps`, `total`, and `avg_latency_ms` stayed at zero. That problem was diagnosed and fixed by ensuring the full stack and load generator were running before experiments.

After that, valid healthy and faulted runs were produced and a first comparison report was created. These runs showed that:
- RL methods behaved differently under stable and degraded conditions
- `q_learning` generally gave the strongest overall RL result
- `sarsa` explored more aggressively
- `bandit` stayed more conservative

This formed the first experimental basis for the project.

## Shift to Literature-Driven Research Questions
After meeting with the professor, the project direction was clarified further. The next phase was not just more implementation, but a proper research workflow:
- do a literature review
- identify gaps in the adaptive tracing literature
- turn those gaps into research questions
- study each question as a separate small research unit with its own experiments and report

The focus was narrowed to adaptive tracing, not broad autoscaling or general monitoring.

## Literature Review Work
A reading list was started around adaptive tracing and closely related work. The review focused on:
- distributed tracing systems
- adaptive tracing
- selective tracing
- anomaly-aware tracing
- trace sampling as one part of adaptive tracing
- RL-based adaptive observability where relevant

From the literature review, the following main gaps were identified:
- RL has not been studied enough directly for adaptive tracing
- there is limited direct comparison between RL-based and non-RL adaptive tracing methods
- different types of adaptive tracing are not clearly organized or compared
- behavior under changing runtime conditions is not explored enough
- reward design for RL-based adaptive tracing is still open
- trace usefulness is hard to define directly
- practical systems focus mostly on sampling, not broader adaptive tracing

Three research questions were then defined from those gaps:

1. How does RL-based adaptive tracing compare to non-RL adaptive tracing baselines, such as rule-based and optimization or sampling-based methods?
2. How do RL-based adaptive tracing methods behave under different runtime changes, such as latency spikes, throughput drops, and error bursts?
3. What are the main types of adaptive tracing, and how do they differ in goals, decision signals, and tracing behavior?

It was also decided that the first earlier RL comparison question does not count as one of these three new literature-driven questions.

## RQ1 Work: RL vs Non-RL Adaptive Tracing
The first new research question completed was:

How does RL-based adaptive tracing compare to non-RL adaptive tracing baselines, such as rule-based and optimization or sampling-based methods?

To answer this, a complete comparison experiment was designed using:

RL methods:
- `q_learning`
- `sarsa`
- `bandit`

Non-RL baselines:
- `rule`
- `kmeans`

Each method was run under:
- healthy
- faulted

This produced a full 10-run experiment matrix.

The report generator was then updated to support non-RL methods, since `rule` and `kmeans` do not produce RL reward summaries. For those methods, comparison was based on:
- sampling rate
- latency
- QPS
- error rate
- decision history

The RQ1 results showed:
- `q_learning` performed best overall among the tested methods in this setup
- `bandit` remained conservative and performed reasonably well
- `sarsa` explored more aggressively but did not improve results
- `rule` and `kmeans` were stable baselines but did not outperform `q_learning`
- under degraded conditions, `q_learning` still maintained low tracing overhead while adapting better than the tested non-RL methods

A full report for RQ1 was created, including:
- motivation
- research question
- literature gap addressed
- methods
- experiment setup
- results tables
- interpretation
- limitations
- conclusion

The main literature gap directly addressed by RQ1 was:
- There is limited direct comparison between RL-based and non-RL adaptive tracing methods in the current literature.

The answer to RQ1 from the experiments was:
- RL-based adaptive tracing, especially `q_learning`, performed competitively and in this setup outperformed the tested non-RL baselines overall
- this provides initial evidence that RL can be more effective than simpler adaptive tracing methods in the tested environment

## Limitations Identified So Far
Several limitations were also documented:
- the experiments so far were done only on Train-Ticket
- stronger fault scenarios are still needed because the measured final error rate often remained `0.0`
- non-RL methods do not expose reward values, so comparison is not perfectly symmetric
- trace usefulness was not measured directly; the experiments mainly used runtime and tracing-control metrics
- only two non-RL baselines were used so far
- runs were relatively short

These are not blockers, but they define what should be improved later.

## Next Research Direction
At this point:
- RQ1 is complete as a research unit
- the next step is to move to RQ2 and later RQ3

Likely next work:
- study adaptive tracing under different runtime changes more carefully
- add stronger fault and error scenarios
- possibly expand beyond Train-Ticket

It was also recognized that the project should eventually use more than one microservice system so the results are not tied only to one application. The current recommended systems are:
- Train-Ticket
- Hotel Reservation from DeathStarBench
- Online Boutique

This would make the research stronger and more general.

## Current Status
So far, the project has:
- built a working adaptive tracing testbed
- implemented RL and non-RL tracing methods
- created a repeatable experiment pipeline
- completed a literature-guided first research question
- produced a full RQ1 report with experiments and conclusions
- identified the next research directions and broader systems to include later
