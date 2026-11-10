---
name: fastapi-sqlite-scaffold
description: Scaffolds a new small local-first Python web app using the FastAPI + SQLAlchemy + Alembic + SQLite stack, matching the established house pattern (as seen in time-management and social-planning under ~/code/personal-projects) - API-first backend, no-build-step vanilla JS frontend, on-disk SQLite with Alembic migrations from day one, and an easy upgrade path to Postgres later. Use this skill whenever the user wants to start a new small personal app/tool, says things like "let's build a new app for X", "make a new project like social-planning/time-management", "scaffold a new FastAPI app", or is clearly about to hand-roll the same boilerplate (config.py, database.py, alembic.ini, migrations/env.py, requirements.txt, etc.) that this skill already generates - even if they don't ask for "scaffolding" by name. Do NOT use this for adding a feature to an *existing* app, for apps that don't want a local SQLite database, or for stacks other than FastAPI/SQLAlchemy (e.g. Flask, Django, Node).
---

# FastAPI + SQLite scaffold

## What this is for

Every new small local app in this house style starts with the same
boilerplate: a `config.py` with HOST/PORT, a `database.py` wiring up
SQLAlchemy, a `deps.py` with `get_db`, a `main.py` that mounts routers and
static files, an Alembic setup with `render_as_batch=True` so SQLite can
handle schema changes safely, and a vanilla-JS static frontend with no build
step. None of that boilerplate differs from project to project - only the
actual data model (`models.py`, `schemas.py`, `crud.py`, routers) and the
frontend content do.

This skill generates the boilerplate by copying real, working template files
(not by regenerating them from a prose description each time), so every
scaffolded project is byte-for-byte consistent with its siblings and doesn't
drift. It deliberately stops short of the domain-specific parts - those are
left as small stub files for you to fill in with the actual project, right
after scaffolding.

## How to use it

Run `scripts/scaffold.py` from the parent directory that holds (or should
hold) the sibling projects - e.g. `~/code/personal-projects`:

```bash
python3 <skill_dir>/scripts/scaffold.py <project-name> --title "Human Readable Title" --db-name <domain>.db
```

- `<project-name>` - the directory name to create, e.g. `recipe-box`. Use a
  short kebab-case name matching the project's purpose.
- `--title` - the FastAPI app title and README heading. Defaults to a
  title-cased version of `<project-name>` if omitted, but pick something
  better when you already know the project's purpose (e.g. "Recipe Box"
  rather than "Recipe-box").
- `--db-name` - the SQLite filename, e.g. `recipes.db`. Pick a name that
  reflects the actual domain noun (like `ideas.db` in social-planning or
  `tasks.db` in time-management), not a generic default - this only takes a
  moment and reads much better in `database.py`/`alembic.ini`/`.gitignore`.
- `--root` - parent directory to scaffold into (default: current directory).
  Point this at the directory containing sibling projects so port
  auto-detection can see them.
- `--port` - override the auto-picked port. Normally leave this out: the
  script scans sibling projects under `--root` for their `app/config.py`
  `PORT` value, picks the next free one above the highest in use, and
  double-checks nothing is already listening on it.
- `--with-api-keys` / `--with-invites` - add an optional module (see "Optional
  modules" below). Neither is on by default.
- `--no-venv` - skip creating a virtualenv and installing dependencies.
  By default the script does create `venv/` and `pip install -r
  requirements.txt -r requirements-dev.txt`, so the project is immediately
  ready to migrate and run. The venv is built with Python 3.10+ (the script
  picks one from PATH if the `python3` running it is older, as macOS's system
  3.9 is) and pip is upgraded first.

**Prerequisite:** the `shared-python` repo must sit next to the new project
(`<root>/shared-python`, on the droplet `/opt/apps/shared-python` owned by
`deploy`). The generated `requirements.txt` installs it with
`-e ../shared-python`, and the script stops early if it isn't there. See the
root `DEPLOYMENT.md` ("Shared Python code").

Run `python3 <skill_dir>/scripts/scaffold.py --help` for the full flag list.

## What gets generated vs. left as stubs

Generated in full (identical pattern across every project):
- `app/config.py`, `app/database.py`, `app/deps.py`, `app/main.py` - the
  latter already wires up `/api/version` (reports the deployed git SHA) and
  a `Cache-Control: no-store` middleware on every response, see "Design
  notes" below for why
- **Accounts** (every app gets them - see "Accounts" below): `app/auth.py`
  (`current_user`, `require_admin`; a thin wrapper over `shared_python.auth`,
  which does the Cloudflare token check), the `User` model in
  `app/models.py`, a baseline migration creating the `users` table, `GET
  /api/me` (`app/routers/me.py`, includes `is_admin`), `DEV_USER_EMAIL` and
  `ADMIN_EMAILS` in `app/config.py`, and a pytest setup
  (`tests/`, `pytest.ini`, `requirements-dev.txt`) whose `tests/test_auth.py`
  covers the sign-in rules
- `app/routers/__init__.py` (empty package, ready for route files)
- `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`,
  `migrations/README`, empty `migrations/versions/`
- `requirements.txt` (includes `-e ../shared-python`, the shared package that
  verifies sign-in tokens and holds the Cloudflare/notification helpers),
  `.gitignore` (ignores `__DB_NAME__` and
  `__DB_NAME__.bak` - the latter is what `scp`-based db-refresh scripts
  tend to produce, see e.g. trip-planning's `refresh_local_dbs`)
- `README.md` with the Alembic workflow, future-Postgres-upgrade, and
  deploying sections already written (same as time-management/social-planning)
- `templates/index.html` (Jinja2, rendered by the `GET /` route in
  `app/main.py` - not served via `StaticFiles`), plus `static/app.js`,
  `static/style.css` - a bare shell (title + empty mount point), not real
  UI, but already wired to `static/version.js` (renders `/api/version` in a
  fixed corner of the page, so a deploy landing is something you can verify
  by eye rather than hoping the cache headers did their job) and to
  `{{ shared_assets_base }}/theme.css`/`theme.js`/`icons.js` - the shared
  look-and-feel (accordion cards, add-toggle forms, message toasts, modals,
  `.app-nav`, buttons, forms) and shared DOM/fetch/date helpers
  (`Global.el`, `Global.fetchJSON`, `Global.showMessage`, ...) used across
  the fleet, maintained in the `shared-assets` repo, exposed as
  `window.Global`. Any section that waits on async data should be wrapped in
  `Global.withLoading(el, promise)` so it shows a spinner (the generated
  `static/app.js` stub documents this). `shared_assets_base` comes from `app/config.py`'s
  `SHARED_ASSETS_BASE` (`https://static.evancooperman.com` in production,
  `http://127.0.0.1:8070` otherwise - see "Design notes" below), so local
  dev and the real deploy point at the right one automatically, with no
  HTML/code edits ever needed to switch. Any *other* HTML page you add
  needs the same treatment: a template under `templates/`, not a static
  file, plus a `GET` route in `app/main.py` rendering it the same way as
  `index()` does. Build real UI with those shared classes/helpers rather
  than reinventing them in this app's own `style.css`/`app.js` - see
  `shared-assets/README.md`.
- `.github/workflows/deploy.yml` - SSHes into the Digital Ocean droplet on
  every push to `main` and restarts the service (needs `DO_HOST`, `DO_USER`,
  `DO_SSH_KEY` repo secrets set once, see README)
- `deploy/<project-dir>.service` - the systemd unit to install on the
  droplet, running `uvicorn` bound to the project's `HOST`/`PORT`, and
  loading the droplet's shared secrets file
  (`EnvironmentFile=-/etc/personal-apps/shared.env`) so shared API keys
  like `ANTHROPIC_API_KEY` are available with no per-app setup. Read them
  in `app/config.py` with `os.environ.get(...)`; never add a per-app
  `Environment=` line for a key that's already in the shared file

Left as near-empty stubs, because they're different for every project and
guessing at them would just create throwaway code to delete later:
- `app/models.py` - has the `Base` import ready, no tables
- `app/schemas.py` - has the Pydantic imports ready, no schemas
- `app/crud.py` - has the `models`/`schemas` imports ready, no functions
- No routers besides `/api/me`, no seed data. The only migration is the one
  creating `users`; your own tables come from the autogenerated migration
  in step 4 below

## Optional modules

Two features that several apps want but not every app does. Ask for them at
scaffold time; each is a folder under `modules/<name>/` (`files/` copied in,
`inject/` snippets spliced into the template's `# @@marker@@` lines, which are
removed when nothing uses them). Their migrations chain after the baseline
`users` one in a fixed order (api-keys, then invites), and both come with tests that
the generated project runs (`pytest`).

- **`--with-api-keys`**: people's own API keys for paid services, saved on
  `/profile.html`. Adds `app/apikeys.py` (the rule: own key, else the server's key
  for an administrator only, else the feature is off), `app/routers/profile.py`, a
  `UserApiKey` model + migration, the Profile page, and `can_use` on `GET /api/me`.
  Ships with an Anthropic provider; add more in `PROVIDERS` with a `_verify_...`
  function. The encryption itself is `shared_python.keystore`. Production needs
  `KEY_ENCRYPTION_SECRET` in the shared secrets file and house keys (e.g.
  `ANTHROPIC_API_KEY`) in the shared file too.
- **`--with-invites`**: ask for new people to be let into the app (`/invites.html`);
  the administrator approves, which adds the email to the Cloudflare Invitees group
  and gives the person an account, then emails them how to sign in. Adds
  `app/invites.py` (rules and quota), `app/routers/invites.py`, `app/notify.py`, an
  `Invite` model + migration, the page, and `invites_left`/`pending_invites` on
  `GET /api/me`. Needs the Cloudflare and SMTP settings in the shared file
  (`DEPLOYMENT.md`). It only gets someone through the gate and into an account:
  what they can then see is the app's own `owner_id` scoping, so do not move the app
  onto the "Shared apps" Access application until that is done. The group is shared by
  all apps, so being let in here lets the person through the gate for every shared app.
  Sharing a specific thing with a person (members + roles, as in lists and
  trip-planning) is not included: build it when the app needs it.

## Accounts

Every scaffolded app has accounts built in, following the pattern first
shipped in `lists` (read its README's "Accounts and sharing" for the full
version). The short form:

- No login form. Cloudflare Access signs people in; `shared_python.auth`
  verifies the signed token it attaches and `app/auth.py` creates a `users` row
  on first sight. The token details (audiences, expiry, signature) are tested in
  shared-python, not per app. In production the app **refuses every request**
  unless `CF_TEAM_DOMAIN` and `CF_ACCESS_AUD` are set in
  `/etc/personal-apps/shared.env`, and it never trusts the plain email header (a hostname that bypasses Access would let
  anyone forge it). Locally every request is `DEV_USER_EMAIL`, or someone else
  via a header or the `dev_user` cookie.
- **When you add tables:** anything a person creates gets
  `owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)`, every
  query - including lookups by id - filters on the signed-in user's id, and a
  row that isn't theirs is a 404. Write a two-person isolation test for every
  endpoint using the `alice`/`bob` fixtures; it is the only guard against the
  one bug that leaks data between people. (Sharing between people, as in
  `lists`, is a `<thing>_members` table with a role per person - build it when
  the app needs it, not by default.)
- **Who can reach the app is a Cloudflare setting.** A new app's hostname falls
  under the wildcard Access application (the owner only). Do not add it to the
  "Shared apps" application - the one that lets invited people in - until every
  table is scoped by `owner_id`; before that, anyone let in would see all of
  the owner's data. Moving it over is: add the hostname to "Shared apps" (never
  to both applications). `CF_ACCESS_AUD` in the shared secrets file should list
  **both** Access applications' tags (wildcard and "Shared apps",
  comma-separated), so a new app works from day one and keeps working after the
  move. See the root `DEPLOYMENT.md`.
- Show who's signed in with `Global.mountUserBadge()` (shared-assets); it adds
  the email and a Log out link to `.app-header`.

## After scaffolding

This is the natural next-step checklist - work through it once the project
exists:

1. Define the real tables in `app/models.py`.
2. Add matching Pydantic schemas in `app/schemas.py` (Base/Create/Update/
   read-model, following the pattern in `models.py`'s docstring comment).
3. Add CRUD functions in `app/crud.py` and a router in `app/routers/`,
   then wire the router into `app/main.py` (there's a `# TODO` marking
   exactly where).
4. Generate and review the migration for your tables (the `users` table
   already has one):
   ```bash
   cd <project> && source venv/bin/activate
   alembic upgrade head
   alembic revision --autogenerate -m "add <your tables>"
   alembic upgrade head
   ```
   Give each of your tables an `owner_id` first (see "Accounts" above) and
   add the two-person access tests to `tests/` - then `pytest`.
5. Build out the real frontend in `static/`.
6. Update the README's placeholder sections with the actual endpoints and
   any project-specific notes.

## Design notes worth knowing

- SQLite's `ALTER TABLE` can't add constraints directly, which is why
  `migrations/env.py` sets `render_as_batch=True` - Alembic then wraps
  those changes in `op.batch_alter_table(...)` and SQLite rebuilds the
  table under the hood. If autogenerate ever produces an unnamed
  `batch_op.create_foreign_key(None, ...)`, give it an explicit name in
  both `upgrade()` and `downgrade()` - SQLite's batch mode needs a name to
  reference.
- The app never calls `Base.metadata.create_all()` - schema is owned
  entirely by Alembic so it can never silently drift from the migration
  history. This means `alembic upgrade head` must be run once before the
  app's first start, or every DB query 500s with "no such table". The
  generated README says this explicitly; don't skip documenting it.
- The backend is a plain JSON REST API under `/api/...` with zero knowledge
  of the frontend, and the frontend is a thin `fetch()`-based client with no
  build step. That split is what makes the backend independently testable
  and lets the frontend be swapped later without touching the API.
- The `no-store` `Cache-Control` middleware exists because plain
  `StaticFiles` sends no cache header at all, which lets browsers apply
  their own heuristic caching - and standalone/home-screen PWAs on iOS
  cache even more aggressively than a normal browser tab, sometimes not
  picking up a deployed change at all short of deleting and re-adding the
  app. `no-cache` (permits caching but requires revalidation first) was
  tried in trip-planning and wasn't strong enough - a CDN or PWA cache
  layer isn't obliged to actually revalidate. `no-store` is the
  unambiguous "never cache this, anywhere" signal, and these are
  single-user local tools, so there's no real cost to it. If the app sits
  behind Cloudflare, also add its hostname to any cache-bypass/Page Rules
  the other apps use - an origin header alone doesn't guarantee the edge
  honors it.
- `#app-version` is deliberately plain in-flow text at the end of `<main>`,
  not `position: fixed` - a fixed corner badge sounds nice but tends to
  land in an awkward spot once a real layout (and possibly a fixed-to-
  bottom mobile nav bar) exists around it. Simplest fix was no fix: let it
  scroll with the page like everything else, so it shows up right where
  the content ends.
- If the project grows into a multi-page app with a bottom nav bar (see
  time-management's or trip-planning's `static/*.html` + `.app-nav` CSS),
  two more small conventions are worth copying at that point rather than
  reinventing:
  - `static/icons.js` (a `data-icon="name"` → inline-SVG registry with an
    `applyIcons(root)` function, so nav/button icons are plain generic
    SVGs instead of emoji, and can be re-applied to DOM built dynamically
    after page load).
  - A `<button class="app-nav-link" onclick="location.reload()">Refresh</button>`
    nav item (see either app's nav bar for the exact markup, and
    trip-planning's `button.app-nav-link` CSS override so it doesn't
    inherit the generic `button {...}` styling). `no-store` should make a
    plain reload always fetch fresh once it's taken effect once, but a
    resource cached by the browser *before* that middleware existed can
    still get served without a network round-trip until something forces
    one - an always-visible reload button is a cheap way to give yourself
    that escape hatch without needing devtools or a hard-refresh shortcut,
    which isn't available at all in a standalone/home-screen PWA.
