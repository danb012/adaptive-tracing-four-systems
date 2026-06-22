#!/usr/bin/env python3
import argparse
import json
import urllib.parse
import urllib.request

PROM_URL = "http://localhost:9091"
TIMEOUT = 10
JOB_FILTER = 'job=~"api-gateway|customers-service|visits-service|vets-service"'
# Keep the Prometheus selector broad. The earlier uri-based filter dropped valid series
# in this stack and caused false zeros even when the raw request counters were increasing.
REQUEST_COUNT_EXPR = f'http_server_requests_seconds_count{{{JOB_FILTER}}}'
ERROR_COUNT_EXPR = f'http_server_requests_seconds_count{{{JOB_FILTER},status=~"5.."}}'
DURATION_SUM_EXPR = f'http_server_requests_seconds_sum{{{JOB_FILTER}}}'


def instant_query(prom_url: str, query: str) -> float:
    encoded = urllib.parse.urlencode({"query": query})
    url = f"{prom_url}/api/v1/query?{encoded}"
    with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
        payload = json.load(response)
    result = payload.get("data", {}).get("result", [])
    if not result:
        return 0.0
    return float(result[0]["value"][1])


def main() -> int:
    parser = argparse.ArgumentParser(description="Query Petclinic runtime metrics from Prometheus.")
    parser.add_argument("--prom-url", default=PROM_URL)
    parser.add_argument("--lookback-seconds", type=int, default=60)
    args = parser.parse_args()

    window = f"[{args.lookback_seconds}s]"
    total = instant_query(args.prom_url, f"sum(increase({REQUEST_COUNT_EXPR}{window}))")
    error_total = instant_query(args.prom_url, f"sum(increase({ERROR_COUNT_EXPR}{window}))")
    duration_total_seconds = instant_query(args.prom_url, f"sum(increase({DURATION_SUM_EXPR}{window}))")

    avg_latency_ms = (duration_total_seconds / total * 1000.0) if total > 0 else 0.0
    error_rate = (error_total / total) if total > 0 else 0.0
    qps = (total / args.lookback_seconds) if args.lookback_seconds > 0 else 0.0

    print(
        json.dumps(
            {
                "total": int(round(total)),
                "avg_latency_ms": avg_latency_ms,
                "error_rate": error_rate,
                "qps": qps,
                "error_total": int(round(error_total)),
                "duration_total_ms": duration_total_seconds * 1000.0,
                "prom_url": args.prom_url,
                "lookback_seconds": args.lookback_seconds,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
