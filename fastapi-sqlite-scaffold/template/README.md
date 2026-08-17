# __PROJECT_TITLE__

<!-- TODO: one or two sentences on what this app actually does -->

## Run it

```bash
cd __PROJECT_DIR__
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.main
```

Then open http://__HOST__:__PORT__ (host/port are set in `app/config.py`).

The SQLite database (`__DB_NAME__`) is not created by the app itself -
`alembic upgrade head` creates it. This only needs to be run once for a
fresh install; see below for how schema changes are handled from here on.

## API-first design

The backend (`app/`) is a plain JSON REST API (`/docs` for the interactive
Swagger UI) with no knowledge of the frontend. The frontend (`static/`) is a
thin vanilla-JS client with no build step, talking to the API over `fetch`.
That separation means the backend can be tested and used entirely on its
own, and the frontend can later be swapped for something richer without
touching the API.

<!-- TODO: list the actual endpoints once routers exist -->

## Schema changes (Alembic)

Schema is owned by migrations under `migrations/versions/`, not by wiping
`__DB_NAME__`. To change the schema:

```bash
# 1. Edit app/models.py as usual
# 2. Generate a migration from the diff
alembic revision --autogenerate -m "short description"
# 3. Look over the generated file in migrations/versions/ - autogenerate
#    is good but not infallible (e.g. it won't detect a plain column rename
#    on its own)
# 4. Apply it
alembic upgrade head
```

This preserves existing data. Useful commands: `alembic current` (what
revision the db is at), `alembic check` (does the db match `models.py`
right now), `alembic downgrade -1` (undo the last migration).

SQLite can't `ALTER TABLE` to add a constraint directly, so
`migrations/env.py` has `render_as_batch=True` set, which makes autogenerate
wrap those changes in `op.batch_alter_table(...)` (SQLite rebuilds the table
under the hood). If autogenerate produces a `batch_op.create_foreign_key(None,
...)` / `drop_constraint(None, ...)` call, give it an explicit name in both
`upgrade()` and `downgrade()` - SQLite's batch mode needs a name to
reference, and will fail with `ValueError: Constraint must have a name`
otherwise.

## Upgrading to Postgres later

Everything goes through SQLAlchemy + Alembic, so moving off SQLite is mostly
a matter of swapping `DATABASE_URL` in `app/database.py` (and
`sqlalchemy.url` in `alembic.ini`) for a Postgres connection string,
installing a driver (`psycopg`), and running `alembic upgrade head` against
the new database - no application code depends on SQLite specifics.

## Deploying

Runs as a systemd service on the Digital Ocean droplet, reached through a
Cloudflare Tunnel (no inbound ports opened on the droplet) and gated by
Cloudflare Access - see `deploy/__PROJECT_DIR__.service`.

One-time setup on the droplet:

```bash
sudo mkdir -p /opt/apps/__PROJECT_DIR__ && sudo chown deploy:deploy /opt/apps/__PROJECT_DIR__
# as the deploy user:
git clone <this repo's SSH URL> /opt/apps/__PROJECT_DIR__
cd /opt/apps/__PROJECT_DIR__
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo cp deploy/__PROJECT_DIR__.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now __PROJECT_DIR__
```

Then add an ingress entry for `__HOST__:__PORT__` to `/etc/cloudflared/config.yml`,
route DNS for its hostname (`cloudflared tunnel route dns <tunnel-name>
<hostname>`), and add a Cloudflare Access policy for that hostname.

Ongoing deploys are automatic: `.github/workflows/deploy.yml` runs on every
push to `main` - it SSHes in, pulls, reinstalls dependencies, runs `alembic
upgrade head`, and restarts the service. Needs these repo secrets set once
(Settings -> Secrets and variables -> Actions): `DO_HOST`, `DO_USER` (the
`deploy` user), `DO_SSH_KEY` (that user's private key).

## Notes

<!-- TODO: project-specific notes go here -->
