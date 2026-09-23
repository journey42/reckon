"""Link-unfurl routes: serve crawler-visible OG metadata for group links.

Group pages are a client-rendered SPA shell on the Static Web App, so a
shared link unfurls with generic (or no) metadata. Crawlers (Discord, X,
Slack, iMessage) do not run JavaScript — they read the initial HTML.

This module mounts a tiny Starlette app on the Reflex backend that serves
per-group OG HTML at ``/g/<slug>``:

- crawlers get the group name + founding question as og:title/description
  (a question summary — never member posts, which stay group-private),
- everyone else is 302-redirected to the real group page.

Use ``/g/<slug>`` in invite links; the frontend URL keeps working as-is.
"""

import html

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Route

from rhiz.utils.groups import get_group_by_slug
from rhiz.pages.group_common import public_base_url

# Which user agents are crawlers that read OG tags (case-insensitive match).
_CRAWLERS = (
    "discord",
    "twitterbot",
    "slack",
    "telegrambot",
    "facebookexternalhit",
    "linkedinbot",
    "whatsapp",
    "embedly",
    "curl",
    "python-requests",
    "googlebot",
    "bingbot",
    "applebot",
)


def _is_crawler(user_agent: str) -> bool:
    ua = (user_agent or "").lower()
    return any(marker in ua for marker in _CRAWLERS)


def _escape(value: str) -> str:
    return html.escape(value or "", quote=True)


def _og_html(name: str, question: str, group_url: str, logo_url: str) -> str:
    description = (
        question.strip()
        or "A group discussion space on Rhiz — propose concepts, support the best ones, build understanding together."
    )
    # Trim long questions to a share-friendly length on a word boundary.
    if len(description) > 200:
        description = description[:197].rsplit(" ", 1)[0] + "…"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{_escape(name)} — Rhiz</title>
  <meta property="og:site_name" content="Rhiz">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{_escape(name)} — Rhiz">
  <meta property="og:description" content="{_escape(description)}">
  <meta property="og:url" content="{_escape(group_url)}">
  <meta property="og:image" content="{_escape(logo_url)}">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{_escape(name)} — Rhiz">
  <meta name="twitter:description" content="{_escape(description)}">
  <meta http-equiv="refresh" content="0;url={_escape(group_url)}">
</head>
<body>
  <p>Opening {_escape(name)} on Rhiz… <a href="{_escape(group_url)}">Continue</a></p>
</body>
</html>"""


async def group_unfurl(request):
    """Serve OG HTML to crawlers; redirect humans to the group page."""
    slug = request.path_params.get("slug", "")
    user_agent = request.headers.get("user-agent", "")
    group_url = f"{public_base_url()}/group/{slug}"

    if not _is_crawler(user_agent):
        return RedirectResponse(group_url, status_code=302)

    import reflex as rx

    with rx.session() as session:
        group = get_group_by_slug(session, slug)

    if group is None:
        return HTMLResponse(
            "<html><head><meta property=\"og:title\" content=\"Rhiz — Speak Together\">"
            "</head><body>Group not found.</body></html>",
            status_code=404,
        )

    import os

    logo_url = f"{public_base_url()}/logo.png"
    return HTMLResponse(
        _og_html(group.name, group.founding_question, group_url, logo_url)
    )


def make_unfurl_app():
    """Starlette app to mount via rx.App(api_transformer=...)."""
    return Starlette(
        routes=[Route("/g/{slug}", group_unfurl, methods=["GET", "HEAD"])]
    )
