from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Schema is owned by Alembic migrations (see migrations/) - run
# `alembic upgrade head` before starting the app rather than relying on
# create_all, so schema changes never silently bypass migrations.

app = FastAPI(title="__PROJECT_TITLE__")

# TODO: once you've added a router under app/routers/, wire it in here, e.g.
# from .routers import things
# app.include_router(things.router)

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    from .config import HOST, PORT

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
