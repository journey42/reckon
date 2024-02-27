import reflex as rx
import os

config = rx.Config(
    app_name="reckon",
    #db_url="sqlite:///reflex.db",
    db_url=os.environ.get('DB_URL', 'postgresql://postgres:password@localhost:5432/reckon'),
    #db_url="postgresql://reckon:+bX2NBT~;oa?@reckon-db.postgres.database.azure.com:5432/reckon",
    env=rx.Env.DEV,
    tailwind={},
)
