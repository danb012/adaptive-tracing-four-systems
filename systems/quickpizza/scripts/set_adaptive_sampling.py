#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.adaptive"
COMPOSE_FILES = [
    "compose.grafana-local-stack.microservices.yaml",
    "compose.adaptive.microservices.yaml",
]
APP_SERVICES = ["catalog", "config", "copy", "public-api", "recommendations", "ws", "grpc"]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def compose_cmd(*args: str) -> list[str]:
    cmd = ["docker", "compose", "--env-file", str(ENV_FILE)]
    for compose_file in COMPOSE_FILES:
        cmd.extend(["-f", compose_file])
    cmd.extend(args)
    return cmd


def write_rate(rate: float) -> None:
    ENV_FILE.write_text(f"QUICKPIZZA_TRACE_SAMPLING_RATE={rate}\n", encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, required=True)
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()

    if not 0.0 <= args.rate <= 1.0:
        raise SystemExit("--rate must be between 0.0 and 1.0")

    write_rate(args.rate)

    if args.restart or args.build:
        cmd = compose_cmd("up", "-d")
        if args.build:
            cmd.append("--build")
        cmd.extend(APP_SERVICES)
        run(cmd)

    print(ENV_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
