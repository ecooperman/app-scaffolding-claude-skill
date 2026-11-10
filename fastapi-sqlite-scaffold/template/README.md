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

## Accounts

There is no sign-in form. Cloudflare Access authenticates everyone before a
request reaches the app and attaches a signed token saying who it was;
`app/auth.py` verifies it and creates that person's `users` row the first time
it sees them. `GET /api/me` says who you are.

- **Use `current_user` on every route that touches a person's data**
  (`user: models.User = Depends(current_user)`), and `require_admin` on anything
  only you should reach (admins are the emails in `ADMIN_EMAILS`).
- **Anything a person creates carries `owner_id`** (a non-null foreign key to
  `users.id`) and **every query filters on it** - including the lookup by id in
  `get`, `update` and `delete`, so someone else's id is a 404, never a 403 and
  never their data. Test it: add a test that signs in as two people (see the
  `alice`/`bob` fixtures in `tests/conftest.py`) and checks that neither can
  see, change or delete the other's rows on every endpoint. A missed filter is
  the one bug here that leaks data between people.
- **Production** needs `CF_TEAM_DOMAIN` and `CF_ACCESS_AUD` (plus optionally
  `ADMIN_EMAILS`) in `/etc/personal-apps/shared.env`, see `DEPLOYMENT.md`. The
  app answers 503 to everything without them and never trusts the plain email
  header, which a hostname that bypasses Access would let anyone forge.
- **Who can reach the app is a Cloudflare Access setting, not this code.** A
  new app starts behind the wildcard Access application, which allows only you.
  Add its hostname to the "Shared apps" Access application only once every
  table is scoped by `owner_id` - until then anyone let in would see everything.
- **Locally** every request is `DEV_USER_EMAIL` (default `dev@localhost.test`).
  To be someone else, send a `Cf-Access-Authenticated-User-Email` header or run
  `document.cookie = "dev_user=bob@example.com; path=/"` in the browser console
  (delete the cookie to go back). Neither works in production.
- **Frontend:** call `Global.mountUserBadge()` (shared-assets) from the page
  script to show who's signed in with a Log out link.

Tests (`pytest`, after `pip install -r requirements-dev.txt`) run the real
migrations on a throwaway database. `tests/test_auth.py` covers the sign-in
rules; add your own access tests beside it.

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
