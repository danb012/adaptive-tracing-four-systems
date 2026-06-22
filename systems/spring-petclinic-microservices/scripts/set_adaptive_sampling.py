#!/usr/bin/env python3
import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.rq1"
COMPOSE_FILES = ["-f", "docker-compose.yml", "-f", "docker-compose.rq1.override.yaml"]
SAMPLING_SERVICES = [
    "api-gateway",
    "customers-service",
    "visits-service",
    "vets-service",
]


def write_env(rate: float) -> None:
    ENV_FILE.write_text(f"PETCLINIC_SAMPLING_PROBABILITY={rate:.4f}\n", encoding="ascii")


def compose_cmd(*args: str) -> list[str]:
    return ["docker", "compose", "--env-file", str(ENV_FILE), *COMPOSE_FILES, *args]


def restart_services() -> None:
    cmd = compose_cmd("up", "-d", "--no-deps", "--force-recreate", *SAMPLING_SERVICES)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update Petclinic tracing sampling probability.")
    parser.add_argument("--rate", type=float, required=True, help="Sampling probability between 0 and 1.")
    parser.add_argument("--restart", action="store_true", help="Recreate tracing services after updating the rate.")
    args = parser.parse_args()

    if not 0.0 < args.rate <= 1.0:
        raise SystemExit("--rate must be in the range (0, 1].")

    write_env(args.rate)

    if args.restart:
        restart_services()

    print(ENV_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
