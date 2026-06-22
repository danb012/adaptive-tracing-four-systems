#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_CONTAINER = "timescale-otel-demo-timescaledb-1"

SQL_TEMPLATE = r"""
WITH roots AS (
  SELECT start_time, duration_ms, status_code
  FROM ps_trace.span
  WHERE parent_span_id IS NULL
  {where_clause}
)
SELECT json_build_object(
  'total', COUNT(*),
  'avg_latency_ms', COALESCE(AVG(duration_ms), 0),
  'error_rate', COALESCE(AVG(CASE WHEN status_code = 'error' THEN 1.0 ELSE 0.0 END), 0),
  'qps', COALESCE(
    COUNT(*) / GREATEST(EXTRACT(EPOCH FROM (MAX(start_time) - MIN(start_time))), 1),
    0
  )
)::text
FROM roots;
"""


def resolve_db_container() -> str:
    # Prefer `docker compose ps -q timescaledb` so scripts work regardless of the project name.
    # Fallback to the historical hardcoded container name for compatibility.
    override = os.environ.get("TIMESCALE_OTEL_DB_CONTAINER")
    if override:
        return override
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", "docker-compose.yaml", "ps", "-q", "timescaledb"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        cid = (result.stdout or "").strip()
        if cid:
            return cid
    except Exception:
        pass
    return DEFAULT_DB_CONTAINER


def main() -> int:
    parser = argparse.ArgumentParser(description="Query aggregate root-span metrics from TimescaleDB.")
    parser.add_argument("--seconds", type=int, default=0, help="limit query to the last N seconds")
    parser.add_argument("--since-epoch", type=float, default=0.0, help="limit query to spans starting at or after this Unix epoch timestamp")
    args = parser.parse_args()

    where_clause = ""
    if args.since_epoch > 0:
        where_clause = f"AND start_time >= to_timestamp({args.since_epoch})"
    elif args.seconds > 0:
        where_clause = f"AND start_time >= now() - interval '{args.seconds} seconds'"

    sql = SQL_TEMPLATE.format(where_clause=where_clause)
    db_container = resolve_db_container()
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            db_container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "otel_demo",
            "-t",
            "-A",
            "-c",
            sql,
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = result.stdout.strip() or "{}"
    print(json.dumps(json.loads(payload), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
