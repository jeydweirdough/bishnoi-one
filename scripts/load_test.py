"""How many people Bishnoi One takes at once: a load test (2026-11-19).

Many people at once, each opening the pages people open all day (who am I, customers, deals, quotes, stock,
invoices, a report), with a pause between clicks like a person. Prints, per step of load, the requests a
second, how long answers took (median, 95th and 99th percentile) and the errors by kind, and the overall verdict.

NEVER against the live system: on a copy (a staging backend on the server, or this computer). It only
reads, but at load, and people working would feel it.

    cd backend
    uv run python ../scripts/load_test.py --base http://127.0.0.1:8300 --tokens tokens.txt --users 10,25,50 --seconds 30

--tokens: a file with one Bishnoi One sign-in token per line (each counts as one person for the per-person
limit; fewer tokens than users are shared). Each pretend person also gets an address of their own
(X-Forwarded-For, taken only from this network), so the per-address limit sees many people, as it would.
--think: seconds between a person's clicks (default 2; 0 = as fast as possible, a stress test).
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from collections import Counter
from pathlib import Path

import httpx

# What a page asks the backend for, as the one app does (BACKEND_URL + module path + route).
PAGES = [
    "/platform/identity/me",
    "/crm/companies?limit=25",
    "/crm/deals?limit=25",
    "/crm/quotes?limit=25",
    "/crm/attention",
    "/inventory/inventory/stock?limit=25",
    "/finance/finance/invoices?limit=25",
    "/crm/reports/pipeline",
]


async def person(n: int, client: httpx.AsyncClient, base: str, token: str, until: float, think: float, times: list, errors: Counter, by_page: dict) -> None:
    headers = {"Authorization": f"Bearer {token}", "X-Forwarded-For": f"10.{200 + n // 65000 % 50}.{n // 250 % 250}.{n % 250 + 1}"}
    while time.monotonic() < until:
        path = random.choice(PAGES)
        started = time.monotonic()
        try:
            r = await client.get(base + path, headers=headers)
            took = time.monotonic() - started
            if r.status_code >= 400:
                errors[f"{r.status_code} {path.split('?')[0]}"] += 1
            else:
                times.append(took)
                by_page.setdefault(path.split("?")[0], []).append(took)
        except httpx.HTTPError as e:
            errors[f"{type(e).__name__} {path.split('?')[0]}"] += 1
        if think:
            await asyncio.sleep(random.uniform(think * 0.5, think * 1.5))


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))]


async def step(base: str, tokens: list[str], users: int, seconds: int, think: float) -> dict:
    times: list[float] = []
    errors: Counter = Counter()
    by_page: dict[str, list[float]] = {}
    limits = httpx.Limits(max_connections=users + 10, max_keepalive_connections=users + 10)
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        until = time.monotonic() + seconds
        await asyncio.gather(*(person(i, client, base, tokens[i % len(tokens)], until, think, times, errors, by_page) for i in range(users)))
    done = len(times) + sum(errors.values())
    return {"users": users, "rps": done / seconds, "ok": len(times), "errors": errors,
            "p50": statistics.median(times) if times else 0, "p95": pct(times, 0.95), "p99": pct(times, 0.99), "by_page": by_page}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8300")
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--users", default="10,25,50")
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--think", type=float, default=2.0)
    a = ap.parse_args()
    tokens = [t.strip() for t in Path(a.tokens).read_text().splitlines() if t.strip()]
    if not tokens:
        raise SystemExit("No tokens in the file.")
    print(f"{'people':>7} {'req/s':>7} {'ok':>7} {'errors':>7} {'median':>8} {'p95':>8} {'p99':>8}")
    worst = None
    for users in [int(u) for u in a.users.split(",")]:
        r = asyncio.run(step(a.base.rstrip("/"), tokens, users, a.seconds, a.think))
        bad = sum(r["errors"].values())
        print(f"{users:>7} {r['rps']:>7.1f} {r['ok']:>7} {bad:>7} {r['p50']*1000:>6.0f}ms {r['p95']*1000:>6.0f}ms {r['p99']*1000:>6.0f}ms")
        slow = sorted(((pct(v, 0.95), k) for k, v in r["by_page"].items()), reverse=True)[:3]
        print(f"{'':>9}slowest (p95): " + ", ".join(f"{k} {t*1000:.0f}ms" for t, k in slow))
        for kind, count in r["errors"].most_common(5):
            print(f"{'':>9}{count} x {kind}")
        if worst is None and (r["p95"] > 2.0 or bad > 0.01 * max(1, r["ok"] + bad)):
            worst = users
    print()
    print(f"Holds up to the largest step tried ({users} people)." if worst is None else
          f"Strained at {worst} people: answers slower than 2 s for 1 in 20, or more than 1% errors.")


if __name__ == "__main__":
    main()
