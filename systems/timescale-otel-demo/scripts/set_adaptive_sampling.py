#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "instrumented" / "collector" / "config.yaml"

BASE_CONFIG = """receivers:
  otlp:
    protocols:
      grpc:
      http:

processors:
  batch:
{sampling_block}
exporters:
  otlp:
    endpoint: promscale:9202
    tls:
      insecure: true

service:
  telemetry:
    logs:
      level: "debug"
  pipelines:
    traces:
      receivers: [otlp]
      processors: [{processor_chain}]
      exporters: [otlp]
"""


def write_config(rate: float) -> None:
    if rate >= 1.0:
        sampling_block = ""
        processor_chain = "batch"
    else:
        sampling_block = (
            "  probabilistic_sampler:\n"
            f"    sampling_percentage: {round(rate * 100, 2)}\n"
        )
        processor_chain = "batch, probabilistic_sampler"

    CONFIG_PATH.write_text(
        BASE_CONFIG.format(
            sampling_block=sampling_block,
            processor_chain=processor_chain,
        ),
        encoding="utf-8",
    )


def restart_collector() -> None:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yaml",
            "ps",
            "-q",
            "collector",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    container_id = (result.stdout or "").strip()

    if not container_id:
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.yaml",
                "up",
                "-d",
                "--no-deps",
                "collector",
            ],
            cwd=ROOT,
            check=True,
            text=True,
        )
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.yaml",
                "ps",
                "-q",
                "collector",
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        container_id = (result.stdout or "").strip()

    if not container_id:
        raise RuntimeError("could not resolve collector container id")

    subprocess.run(
        ["docker", "cp", str(CONFIG_PATH), f"{container_id}:/etc/otelcol/config.yaml"],
        cwd=ROOT,
        check=True,
        text=True,
    )
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yaml",
            "restart",
            "collector",
        ],
        cwd=ROOT,
        check=True,
        text=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Set collector-side adaptive trace sampling rate.")
    parser.add_argument("--rate", type=float, required=True, help="trace sampling rate in [0.0, 1.0]")
    parser.add_argument("--rebuild", action="store_true", help="refresh the running collector after writing config")
    args = parser.parse_args()

    if not 0.0 <= args.rate <= 1.0:
        raise SystemExit("--rate must be between 0.0 and 1.0")

    write_config(args.rate)
    if args.rebuild:
        restart_collector()

    print(CONFIG_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
