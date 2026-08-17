import subprocess
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

# Schema is owned by Alembic migrations (see migrations/) - run
# `alembic upgrade head` before starting the app rather than relying on
# create_all, so schema changes never silently bypass migrations.


def _get_git_sha() -> str:
    """Short commit hash the running app was deployed from, read straight
    from the repo on disk (the deploy pulls a real git checkout) - no CI
    wiring needed, and it can never drift from what's actually running.
    """
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


GIT_SHA = _get_git_sha()

app = FastAPI(title="__PROJECT_TITLE__")


@app.get("/api/version")
def get_version():
    return {"version": GIT_SHA}


@app.middleware("http")
async def no_cache(request: Request, call_next):
    """Never let the browser (or iOS's aggressive standalone-PWA cache) serve
    a stale copy of the app - these are single-user local tools, not public
    sites, so there's no real cost to always fetching fresh. `no-store` (not
    `no-cache`) is deliberate: `no-cache` still permits caching as long as
    the cache revalidates first, which a CDN or PWA cache layer isn't
    obligated to actually do - `no-store` is the only unambiguous "never
    cache this, anywhere" signal. See static/version.js, which surfaces
    GIT_SHA in a corner of every page so a deploy landing (vs. a stale
    cached copy) is something you can actually verify by eye.
    """
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


# TODO: once you've added a router under app/routers/, wire it in here, e.g.
# from .routers import things
# app.include_router(things.router)

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    from .config import HOST, PORT

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
