#!/usr/bin/env python3
"""Read production container logs.

`az containerapp logs show` does not work for this app: the CLI streams through
`properties.eventStreamEndpoint`, which the environment does not expose, so it
dies with `KeyError: 'eventStreamEndpoint'`. The console output is still there —
the environment forwards it to a Log Analytics workspace — so this queries that
workspace directly.

    python scripts/prod_logs.py                 # last 30 minutes
    python scripts/prod_logs.py --minutes 5
    python scripts/prod_logs.py --errors        # only lines that look like errors
    python scripts/prod_logs.py --grep rotate
    python scripts/prod_logs.py --app rhiz-backend-staging

Requires an authenticated Azure CLI session (`az login`) with read access to the
workspace. This is the fastest way to answer "what is the app doing right now"
during an event, so it deliberately depends on nothing but `az` and stdlib.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

WORKSPACE_NAME = "workspace-reckonrgzwFp"
RESOURCE_GROUP = "reckon-rg"
LOG_ANALYTICS_SCOPE = "https://api.loganalytics.io"

ERRORISH = (
    "error",
    "traceback",
    "exception",
    "failed",
    "critical",
    "refused",
    "timeout",
    "deadlock",
)


def az(*args: str) -> str:
    """Run the Azure CLI and return stdout, or exit with its stderr."""
    proc = subprocess.run(["az", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"az {' '.join(args)} failed:\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def workspace_id() -> str:
    """The workspace's customer (query) id — the id the query API wants."""
    cid = az(
        "monitor",
        "log-analytics",
        "workspace",
        "show",
        "-n",
        WORKSPACE_NAME,
        "-g",
        RESOURCE_GROUP,
        "--query",
        "customerId",
        "-o",
        "tsv",
    )
    if not cid:
        sys.exit(f"could not resolve customerId for {WORKSPACE_NAME}")
    return cid


def query(customer_id: str, kql: str) -> list[dict]:
    token = az("account", "get-access-token", "--resource", LOG_ANALYTICS_SCOPE, "--query", "accessToken", "-o", "tsv")
    if not token:
        sys.exit("no access token — run `az login` first")
    req = urllib.request.Request(
        f"{LOG_ANALYTICS_SCOPE}/v1/workspaces/{customer_id}/query",
        data=json.dumps({"query": kql}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        sys.exit(f"query failed: HTTP {exc.code} {exc.read()[:300].decode(errors='replace')}")
    except urllib.error.URLError as exc:
        sys.exit(f"could not reach Log Analytics: {exc.reason}")
    tables = payload.get("tables") or []
    if not tables:
        return []
    columns = [c["name"] for c in tables[0]["columns"]]
    return [dict(zip(columns, row)) for row in tables[0]["rows"]]


def main() -> int:
    ap = argparse.ArgumentParser(description="Query this app's container logs.")
    ap.add_argument("--minutes", type=int, default=30, help="how far back to look (default 30)")
    ap.add_argument("--app", default="rhiz-backend", help="container app name (default rhiz-backend)")
    ap.add_argument("--errors", action="store_true", help="only lines that look like errors")
    ap.add_argument("--grep", help="only lines containing this text (case-insensitive)")
    ap.add_argument("--limit", type=int, default=200, help="max lines (default 200)")
    args = ap.parse_args()

    since = datetime.now(timezone.utc) - timedelta(minutes=args.minutes)
    # tostring(TimeGenerated) so the API hands back ISO strings rather than
    # Azure's datetime objects, which keep their own formatting.
    kql = (
        "ContainerAppConsoleLogs_CL "
        f'| where ContainerAppName_s == "{args.app}" '
        f"| where TimeGenerated > datetime({since:%Y-%m-%dT%H:%M:%SZ}) "
        "| extend T = tostring(TimeGenerated) "
        "| project T, Log_s "
        f"| order by T desc | take {args.limit}"
    )
    rows = query(workspace_id(), kql)
    if not rows:
        print(f"no log lines for {args.app} in the last {args.minutes} minutes")
        return 0

    lines = [(r.get("T", ""), (r.get("Log_s") or "").rstrip()) for r in rows]
    if args.errors:
        lines = [(t, l) for t, l in lines if any(k in l.lower() for k in ERRORISH)]
    if args.grep:
        needle = args.grep.lower()
        lines = [(t, l) for t, l in lines if needle in l.lower()]

    for stamp, line in reversed(lines):
        print(f"{stamp[:19]}  {line}")
    print(f"\n{len(lines)} line(s) from the last {args.minutes} minutes", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
