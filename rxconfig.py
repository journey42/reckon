import reflex as rx

config = rx.Config(
    app_name="reckon",
    #db_url="sqlite:///reflex.db",
    db_url="postgresql://postgres:password@localhost:5432/reckon",
    env=rx.Env.DEV,
)
