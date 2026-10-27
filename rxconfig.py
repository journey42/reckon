import reflex as rx
import os

from client_render_plugin import ClientRenderPlugin

config = rx.Config(
    app_name="rhiz",
    #db_url="sqlite:///reflex.db",
    db_url=os.environ.get('DB_URL', 'postgresql://postgres:password@localhost:5432/reckon'),
    api_url=os.environ.get('API_URL', 'http://localhost:8000'),
    show_built_with_reflex=False,
    env=rx.Env.DEV,
    plugins=[
        # Owns .web/app/entry.client.js so the app mounts client-side instead of
        # hydrating a document whose <head> can never match (#418).
        ClientRenderPlugin(),
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                appearance="light",
                has_background=True,
                radius="full",
                accent_color="gray",
            ),
        ),
    ],
    disable_plugins=[rx.plugins.SitemapPlugin],
    tailwind={
        "theme": {
            "extend": {},
        },
        "plugins": ["@tailwindcss/typography"],
    },
)
