#!/usr/bin/env python3
import argparse
import json
import urllib.parse
import urllib.request

PROM_URL = "http://localhost:9090"
DEFAULT_JOB = "quickpizza/public-api"
DEFAULT_PATH = "/api/*"
DEFAULT_METHOD = "POST"


def prom_query(expr: str) -> float:
    url = f"{PROM_URL}/api/v1/query?query={urllib.parse.quote(expr, safe='')}"
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.load(response)
    results = payload.get("data", {}).get("result", [])
    if not results:
        return 0.0
    return float(results[0]["value"][1])


def range_selector(lookback_seconds: int, offset_seconds: int = 0) -> str:
    selector = f"[{lookback_seconds}s]"
    if offset_seconds > 0:
        selector += f" offset {offset_seconds}s"
    return selector


def metric_window(metric: str, selector: str, lookback_seconds: int) -> float:
    return prom_query(f"sum(increase({metric}{{{selector}}}{range_selector(lookback_seconds)}))")


def metric_window_offset(metric: str, selector: str, lookback_seconds: int, offset_seconds: int) -> float:
    return prom_query(
        f"sum(increase({metric}{{{selector}}}{range_selector(lookback_seconds, offset_seconds)}))"
    )


def metric_current(metric: str, selector: str) -> float:
    return prom_query(f"sum({metric}{{{selector}}})")


def candidate_selectors(job: str, path: str, method: str) -> list[tuple[str, str]]:
    return [
        ("exact", f'job="{job}",path="{path}",method="{method}"'),
        ("api_wildcard_method", f'path="/api/*",method="{method}"'),
        ("path_method", f'path="{path}",method="{method}"'),
        ("path_only", f'path="{path}"'),
        ("namespace_method", f'service_namespace="quickpizza",method="{method}"'),
        ("namespace_only", 'service_namespace="quickpizza"'),
        ("all", ""),
    ]


def add_label(selector: str, extra: str) -> str:
    return f"{selector},{extra}" if selector else extra


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-seconds", type=int, default=60)
    parser.add_argument("--offset-seconds", type=int, default=0)
    parser.add_argument("--job", default=DEFAULT_JOB)
    parser.add_argument("--path", default=DEFAULT_PATH)
    parser.add_argument("--method", default=DEFAULT_METHOD)
    args = parser.parse_args()

    total = 0.0
    error_total = 0.0
    duration_total = 0.0
    selector_used = "none"
    current_total = 0.0
    current_error_total = 0.0
    current_duration_total = 0.0

    for selector_name, selector in candidate_selectors(args.job, args.path, args.method):
        total = metric_window_offset(
            "quickpizza_server_http_requests_total",
            selector,
            args.lookback_seconds,
            args.offset_seconds,
        )
        current_total = metric_current("quickpizza_server_http_requests_total", selector)
        if total <= 0 and current_total <= 0:
            continue
        error_total = metric_window_offset(
            "quickpizza_server_http_requests_total",
            add_label(selector, 'status=~"5.."'),
            args.lookback_seconds,
            args.offset_seconds,
        )
        duration_total = metric_window_offset(
            "quickpizza_server_http_request_duration_seconds_sum",
            selector,
            args.lookback_seconds,
            args.offset_seconds,
        )
        current_duration_total = metric_current(
            "quickpizza_server_http_request_duration_seconds_sum",
            selector,
        )
        current_error_total = metric_current(
            "quickpizza_server_http_requests_total",
            add_label(selector, 'status=~"5.."'),
        )
        selector_used = selector_name
        break

    avg_latency_ms = (duration_total / total * 1000.0) if total > 0 else 0.0
    error_rate = (error_total / total) if total > 0 else 0.0
    qps = total / float(args.lookback_seconds) if args.lookback_seconds > 0 else 0.0

    print(
        json.dumps(
            {
                "total": total,
                "avg_latency_ms": avg_latency_ms,
                "error_rate": error_rate,
                "qps": qps,
                "error_total": error_total,
                "duration_total_ms": duration_total * 1000.0,
                "job": args.job,
                "path": args.path,
                "method": args.method,
                "selector_used": selector_used,
                "current_total": current_total,
                "current_error_total": current_error_total,
                "current_duration_total_ms": current_duration_total * 1000.0,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
