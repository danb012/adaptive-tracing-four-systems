import os
import random
import asyncio


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_delay_ms(prefix: str) -> int:
    return _env_int(f"{prefix}_DELAY_MS", 0)


def get_error_rate(prefix: str) -> float:
    return _env_float(f"{prefix}_ERROR_RATE", 0.0)


async def maybe_delay(prefix: str) -> None:
    delay_ms = get_delay_ms(prefix)
    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000.0)


def should_error(prefix: str) -> bool:
    rate = get_error_rate(prefix)
    if rate <= 0.0:
        return False
    if rate >= 1.0:
        return True
    return random.random() < rate
