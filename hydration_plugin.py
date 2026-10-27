"""Hydrate only when the served HTML is actually this route's prerender.

Why this exists
---------------
Reflex builds the frontend with React Router in ``ssr: false`` +
``prerender: true`` mode. That prerenders every *static* route to a real HTML
file, and leaves *parameterised* routes — ``/group/[slug]``, ``/room/[slug]``,
``/concept/[rid]`` and five others — with nothing but the root-only shell, which
the host serves for them as a fallback.

Reflex's stock entry is unconditional::

    hydrateRoot(document, createElement(HydratedRouter));

So for every dynamic route the browser is handed markup that cannot contain the
page it is about to render. React calls that a hydration failure
(`Minified React error #418 <https://react.dev/errors/418>`_), throws the tree
away and re-renders it from scratch — on the app's most-visited pages, during the
event, on phones.

Two host-side fixes were measured on the deployed site and neither works: export
in SPA mode (``--no-ssr``) makes *every* route mismatch instead of just the
dynamic ones, and emptying the shell's body does not help either — the mismatch
is unconditional once ``hydrateRoot`` is used against markup that was not
rendered for this URL. The entry itself has to decide.

This plugin uses Reflex's supported hook (``Plugin.provides_entry_client``, which
makes the framework skip its own ``entry.client.js``) and writes an entry that
hydrates when ``scripts/frontend_export_fixups.py`` stamped the document with the
route it was prerendered for, and mounts client-side otherwise. Prerendering
keeps working where it applies; the console stops lying about the rest.
"""

from __future__ import annotations

from reflex.plugins.base import Plugin
from reflex.utils.prerequisites import get_web_dir
from reflex_base.constants import Embed

#: Must match ``MARKER_NAME`` in scripts/frontend_export_fixups.py.
MARKER_NAME = "reflex:prerendered-route"

ENTRY_CLIENT_JS = """\
// Provided by hydration_plugin.ConditionalHydrationPlugin — registered in
// rxconfig.py. Reflex would otherwise write its own unconditional entry here.
//
// Hydrate only when this document was prerendered for *this* URL. Reflex
// prerenders the static routes and leaves parameterised ones to the host's SPA
// fallback; hydrating that fallback is React error #418 on every visit, which
// costs a discarded tree and a full re-render. A stamped marker means the bytes
// came from this route's prerender, so hydration is safe. Without it, mount
// client-side, which is exactly what a fallback is asking for.
import { createElement, startTransition } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";

const MARKER = "%(marker)s";

function normalize(path) {
  // /login and /login/ are the same route; the export writes files under the
  // directory form while the host may serve either spelling.
  return path.length > 1 && path.endsWith("/") ? path.slice(0, -1) : path;
}

function servedRoute() {
  const meta = document.querySelector(`meta[name="${MARKER}"]`);
  return meta ? meta.getAttribute("content") : null;
}

const served = servedRoute();
const canHydrate = served !== null && normalize(served) === normalize(window.location.pathname);

startTransition(() => {
  if (canHydrate) {
    hydrateRoot(document, createElement(HydratedRouter));
  } else {
    createRoot(document).render(createElement(HydratedRouter));
  }
});
""" % {"marker": MARKER_NAME}


class ConditionalHydrationPlugin(Plugin):
    """Own ``.web/app/entry.client.js`` so hydration becomes conditional."""

    def provides_entry_client(self) -> bool:
        """Tell the framework not to write its own entry for this build."""
        return True

    def pre_compile(self, **context) -> None:
        """Write the entry before the frontend is built.

        Runs on every compile, so an edit here cannot be masked by a stale
        ``.web`` directory left over from a previous Reflex version.
        """
        target = get_web_dir() / Embed.ENTRY_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text(encoding="utf-8") if target.is_file() else None
        if existing != ENTRY_CLIENT_JS:
            target.write_text(ENTRY_CLIENT_JS, encoding="utf-8")
