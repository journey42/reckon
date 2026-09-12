#!/usr/bin/env python
"""Live Q&A load rehearsal — the plan's pre-deploy gate (checklist item 13).

Answers one question: can the backend hold a room of ~300 phones sitting on the
waiting screen, each reloading every 20 seconds, and then absorb the burst when
the question closes?

Run against a scratch database restored from a production snapshot:

    DB_URL=postgresql://user:pw@localhost:5432/scratch \\
        python scripts/load_test.py connections 300
    DB_URL=... python scripts/load_test.py reloads <open-slug> <closed-slug>

`connections` opens N websockets and samples the server's RSS and file
descriptors while they are held. `reloads` drives the real RoomState.on_load
code path concurrently for a waiting tab and for the closed artifact, reporting
work per load and the share of one worker a 300-tab room consumes.

The HTTP page fetch is deliberately not measured here: in production the static
frontend is served by Azure Static Web App, not by this container.
"""
from __future__ import annotations

import asyncio
import os
import statistics
import subprocess
import sys
import time
import uuid

# Reflex resolves its config by importing rxconfig; that only works if the repo
# root is importable and reflex is imported before anything touches the engine.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
# Python puts this script's own directory first on sys.path, where `pgvector/`
# would shadow the real package. Drop it, then make the repo root importable.
sys.path[:] = [
    p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE
]
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
os.environ.setdefault("DB_URL", "postgresql://lucy:lucy@localhost:5432/reckon_test")

from sqlalchemy import create_engine  # noqa: E402
from sqlmodel import Session  # noqa: E402

from rhiz.state.base import RoomParticipant  # noqa: E402
from rhiz.utils.rooms import (  # noqa: E402
    device_hash_for,
    enforce_deadline,
    get_room,
    my_answer,
    room_results,
    room_status,
)

WS_URL = os.environ.get(
    "WS_URL", "ws://localhost:8000/_event/?EIO=4&transport=websocket&token={token}"
)


# ---------------------------------------------------------------- server stats

def server_pid() -> str | None:
    """The reflex process holding the most fds (the worker, not the launcher)."""
    pids = subprocess.run(
        ["pgrep", "-f", "reflex run"], capture_output=True, text=True
    ).stdout.split()
    best, best_fds = None, -1
    for pid in pids:
        try:
            n = len(os.listdir(f"/proc/{pid}/fd"))
        except OSError:
            continue
        if n > best_fds:
            best, best_fds = pid, n
    return best


def proc_stats(pid: str | None) -> tuple[float, int]:
    """(RSS MB, open fd count)."""
    if not pid:
        return 0.0, 0
    try:
        rss_kb = 0
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss_kb = int(line.split()[1])
                    break
        return rss_kb / 1024, len(os.listdir(f"/proc/{pid}/fd"))
    except OSError:
        return 0.0, 0


# ---------------------------------------------------------------- connections

async def connections_test(n: int, hold: int, batch: int) -> None:
    import aiohttp

    pid = server_pid()
    r0, f0 = proc_stats(pid)
    print(f"server pid={pid} baseline rss={r0:.0f}MB fds={f0}")

    conns: list = []
    lat: list[float] = []
    errs = 0

    # limit=0: aiohttp's default connector caps a client at 100 sockets, which
    # otherwise looks exactly like a server-side ceiling.
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=0)
    ) as session:

        async def one() -> None:
            nonlocal errs
            token = str(uuid.uuid4())
            t0 = time.perf_counter()
            try:
                ws = await session.ws_connect(
                    WS_URL.format(token=token),
                    timeout=aiohttp.ClientWSTimeout(ws_close=10),
                )
                await ws.receive_str(timeout=10)  # engine.io open
                await ws.send_str('40{"token":"%s"}' % token)  # namespace connect
                for _ in range(8):
                    m = await ws.receive_str(timeout=10)
                    if m.startswith("40"):
                        break
                lat.append((time.perf_counter() - t0) * 1000)
                conns.append(ws)
            except Exception:
                errs += 1

        t0 = time.perf_counter()
        for start in range(0, n, batch):
            await asyncio.gather(
                *[one() for _ in range(min(batch, n - start))]
            )
        ramp = time.perf_counter() - t0

    lat.sort()
    print(f"\n{n} concurrent websockets: ok={len(conns)} errors={errs} ramp={ramp:.1f}s")
    if lat:
        print(
            f"  handshake p50={lat[len(lat)//2]:.0f}ms "
            f"p95={lat[int(len(lat)*0.95)]:.0f}ms max={lat[-1]:.0f}ms"
        )
    r1, f1 = proc_stats(pid)
    print(f"  while held: rss {r0:.0f}->{r1:.0f}MB (+{r1-r0:.0f}), fds +{f1-f0}")
    if conns:
        print(
            f"  {(f1-f0)/len(conns):.2f} fds/connection, "
            f"{(r1-r0)*1024/len(conns):.0f} KB/connection"
        )

    for _ in range(hold // 5):
        await asyncio.sleep(5)
        r, f = proc_stats(pid)
        print(f"  held: rss={r:.0f}MB fds={f} (drift check)")

    for ws in conns:
        await ws.close()
    await asyncio.sleep(3)
    r2, f2 = proc_stats(pid)
    print(f"  after close: rss={r2:.0f}MB fds={f2} (baseline {r0:.0f}MB/{f0})")


# ---------------------------------------------------------------- reload work

def reloads_test(open_slug: str, closed_slug: str, tabs: int, cycles: int, workers: int = 16) -> None:
    """Drive the real on_load code path concurrently.

    RoomState.on_load is synchronous DB work; a thread pool reproduces the
    contention the DB connection pool (Reflex default: 5 + 10 overflow) sees
    when a whole room reloads at once.
    """
    import concurrent.futures as cf
    from sqlmodel import select

    engine = create_engine(os.environ["DB_URL"])

    def session():
        # Plain SQLModel session: the read paths take one, so the measurement
        # does not depend on Reflex's config/engine discovery.
        return Session(bind=engine, autoflush=False)

    def waiting_load(i: int) -> str:
        with session() as s:
            room = get_room(s, open_slug)
            if room is None:
                return "missing"
            room = enforce_deadline(s, room)
            room_status(s, room)
            h = device_hash_for(f"load-token-open-{i % 40}", open_slug)
            p = s.exec(
                select(RoomParticipant).where(RoomParticipant.device_hash == h)
            ).first()
            if p is not None and p.current_answer_id is not None:
                my_answer(s, p)
        return "ok"

    def artifact_load(i: int) -> str:
        with session() as s:
            room = get_room(s, closed_slug)
            if room is None:
                return "missing"
            room = enforce_deadline(s, room)
            room_status(s, room)
            room_results(s, room)
        return "ok"

    for label, fn in (("waiting tab", waiting_load), ("artifact tab", artifact_load)):
        per_load: list[float] = []
        bad = 0
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            for _ in range(cycles):
                t0 = time.perf_counter()
                results = list(ex.map(fn, range(tabs)))
                dt = time.perf_counter() - t0
                bad += results.count("missing")
                per_load.append(dt / tabs * 1000)
        mean = statistics.mean(per_load)
        need = tabs / 20.0  # every tab reloads once per 20s
        print(f"\n{label}: {tabs} concurrent loads -> {mean:.2f}ms per load "
              f"(worst {max(per_load):.2f}ms), missing={bad}")
        print(f"  a {tabs}-phone room needs {need:.0f} loads/s "
              f"= {need * mean / 10:.1f}% of one worker's DB time")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "connections"
    if mode == "connections":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 300
        hold = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        batch = int(sys.argv[4]) if len(sys.argv) > 4 else 50
        asyncio.run(connections_test(n, hold, batch))
    elif mode == "reloads":
        reloads_test(sys.argv[2], sys.argv[3],
                     int(sys.argv[4]) if len(sys.argv) > 4 else 300,
                     int(sys.argv[5]) if len(sys.argv) > 5 else 3,
                     int(sys.argv[6]) if len(sys.argv) > 6 else 16)
    else:
        print(__doc__)
        sys.exit(1)
