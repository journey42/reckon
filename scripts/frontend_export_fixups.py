#!/usr/bin/env python3
"""Make an exported frontend bundle safe for the host's navigation fallback.

`reflex export` writes `__spa-fallback.html` when it prerenders routes, and
copies it to `404.html`. In SPA mode (`--no-ssr`) it writes only `index.html`,
but `deploy/staticwebapp.config.json` — which is shared with production — keeps
rewriting every unknown path to `/__spa-fallback.html`. Without that file every
deep link 404s, which is a worse bug than the hydration warning this is all
about. Copy the file instead of retargeting the config, so a single config stays
correct for both build modes and a staging experiment cannot change what
production serves.

Usage:
    python scripts/frontend_export_fixups.py [--out .web/build/client] [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

FALLBACK = "__spa-fallback.html"
NOT_FOUND = "404.html"
INDEX = "index.html"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".web/build/client", help="exported client directory")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.out)
    if not root.is_dir():
        print(f"error: {root} is not a directory (run `reflex export` first)", file=sys.stderr)
        return 2

    index = root / INDEX
    if not index.is_file():
        print(f"error: {index} missing — the export produced nothing to serve", file=sys.stderr)
        return 2

    for name in (FALLBACK, NOT_FOUND):
        target = root / name
        if target.is_file():
            print(f"  {name}: already present ({target.stat().st_size} bytes)")
            continue
        if args.dry_run:
            print(f"  {name}: would copy from {INDEX}")
            continue
        shutil.copyfile(index, target)
        print(
            f"  {name}: created from {INDEX} ({target.stat().st_size} bytes) — "
            "the host rewrites unknown paths here"
        )

    prerendered = sorted(p.parent.relative_to(root).as_posix() for p in root.glob("*/index.html"))
    print(
        f"  prerendered routes: {len(prerendered)}"
        + (f" (e.g. {', '.join(prerendered[:4])})" if prerendered else " — SPA mode: one shell for all routes")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
