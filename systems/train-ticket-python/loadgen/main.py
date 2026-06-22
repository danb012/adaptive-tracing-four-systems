import asyncio
import os
import random
import httpx

BASE_URL = os.getenv("BASE_URL", "http://gateway:8080")
CONCURRENCY = int(os.getenv("CONCURRENCY", "25"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "0.2"))

ROUTES = [
    ("Shanghai", "Beijing"),
    ("Beijing", "Tianjin"),
    ("Guangzhou", "Shenzhen"),
    ("Nanjing", "Shanghai"),
]


async def worker(worker_id: int):
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            try:
                login = await client.post(
                    f"{BASE_URL}/login",
                    json={"username": "alice", "password": "password"},
                )
                if login.status_code != 200:
                    print(f"worker {worker_id} login failed: {login.text}")
                    await asyncio.sleep(REQUEST_DELAY)
                    continue
                user_id = login.json()["user_id"]

                from_station, to_station = random.choice(ROUTES)
                search = await client.get(
                    f"{BASE_URL}/travel/search",
                    params={"from_station": from_station, "to_station": to_station, "date": "2026-01-28"},
                )
                if search.status_code != 200:
                    await asyncio.sleep(REQUEST_DELAY)
                    continue

                trip = search.json()["trips"][0]
                await client.get(f"{BASE_URL}/users/{user_id}")
                await client.post(
                    f"{BASE_URL}/orders",
                    json={
                        "user_id": user_id,
                        "trip_id": trip["trip_id"],
                        "amount": trip["price"],
                    },
                )
            except httpx.HTTPError as exc:
                print(f"worker {worker_id} http error: {exc}")
            await asyncio.sleep(REQUEST_DELAY)


async def main():
    await asyncio.gather(*(worker(i) for i in range(CONCURRENCY)))


if __name__ == "__main__":
    asyncio.run(main())
