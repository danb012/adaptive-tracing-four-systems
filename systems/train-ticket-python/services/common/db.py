import os
from typing import Iterable, Callable, Awaitable
import asyncpg

_pool = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        database_url = os.getenv(
            "DATABASE_URL", "postgresql://tt:tt@postgres:5432/trainticket"
        )
        _pool = await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=5)
    return _pool


async def init_schema(
    schema: str,
    ddl_statements: Iterable[str],
    seed_fn: Callable[[asyncpg.Connection], Awaitable[None]] | None = None,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        await conn.execute(f'SET search_path TO "{schema}"')
        for stmt in ddl_statements:
            await conn.execute(stmt)
        if seed_fn:
            await seed_fn(conn)
