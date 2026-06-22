# Train-Ticket Python Subset (8 services)

Services:
- ts-gateway-service
- ts-auth-service
- ts-user-service
- ts-travel-service
- ts-route-service
- ts-seat-service
- ts-order-service
- ts-payment-service
- sampling-config-service

## Run

```bash
cd /Users/dan/train-ticket-python
docker compose up --build
```

- Gateway: http://localhost:8080
- Jaeger UI: http://localhost:16686

## Dynamic sampling

Get current sampling rate:

```bash
curl http://localhost:8001/sampling
```

Update sampling rate (0.0 - 1.0):

```bash
curl -X PUT http://localhost:8001/sampling \\
  -H 'content-type: application/json' \\
  -d '{\"rate\":0.2}'
```

## Adaptive sampling agent

The sampling agent adjusts the sampling rate based on order error rate.
Defaults:
- error_rate >= 0.4 -> rate 0.8
- error_rate >= 0.2 -> rate 0.5
- error_rate <= 0.05 -> rate 0.05
- otherwise -> rate 0.1

Tuning via env vars in `docker-compose.yml`:
- `AGENT_POLL_INTERVAL`
- `MIN_SAMPLING_RATE`
- `MAX_SAMPLING_RATE`
- `KMEANS_WINDOW`
- `KMEANS_K`
- `POLICY_MODE` (`rule`, `kmeans`, `q_learning`, `sarsa`, `bandit`; `rl` aliases `q_learning`)
- `RL_ACTIONS`
- `RL_EPSILON`
- `RL_ALPHA`
- `RL_GAMMA`
- `RL_REWARD_MODE` (`balanced`, `error_focus`, `latency_focus`, `cost_focus`, `stream_adaptive`)
- `RL_REWARD_ERROR_WEIGHT`
- `RL_REWARD_LATENCY_WEIGHT`
- `RL_REWARD_COST_WEIGHT`
- `RL_REWARD_STABILITY_WEIGHT`
- `RL_REWARD_DRIFT_WEIGHT`
- `RL_ERROR_BINS`
- `RL_LATENCY_BINS`
- `RL_QPS_BINS`

Agent status:

```bash
curl http://localhost:8002/status
```

Agent summary and recent decisions:

```bash
curl http://localhost:8002/summary
curl http://localhost:8002/decisions?limit=10
```

RL method testing:

```bash
# switch POLICY_MODE in docker-compose.yml, then rebuild the agent
docker compose up -d --build sampling-agent
```

Experiment runner:

```bash
python3 scripts/run_sampling_experiment.py --policy q_learning --reward-mode balanced --scenario healthy --duration 30
python3 scripts/run_sampling_experiment.py --policy sarsa --reward-mode balanced --scenario healthy --duration 30
python3 scripts/run_sampling_experiment.py --policy bandit --reward-mode balanced --scenario healthy --duration 30

python3 scripts/run_sampling_experiment.py --policy q_learning --reward-mode balanced --scenario faulted --duration 30
python3 scripts/run_sampling_experiment.py --policy sarsa --reward-mode balanced --scenario faulted --duration 30
python3 scripts/run_sampling_experiment.py --policy bandit --reward-mode balanced --scenario faulted --duration 30
```

Each run writes a JSON file under `experiment_results/`.

Report generation:

```bash
python3 scripts/generate_sampling_report.py experiment_results/*__healthy.json experiment_results/*__faulted.json
```

## Fault injection (Week 1)

Set latency or error injection via env vars in `docker-compose.yml`:
- `ORDER_DELAY_MS`, `ORDER_ERROR_RATE`
- `TRAVEL_DELAY_MS`, `TRAVEL_ERROR_RATE`

Example (set 200ms delay + 10% errors in order):
```bash
# edit docker-compose.yml, then:
docker compose up -d --build order
```

## Example

```bash
curl -X POST http://localhost:8080/login \
  -H 'content-type: application/json' \
  -d '{"username":"alice","password":"password"}'
```
