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
- `--no-venv` - skip creating a virtualenv and installing dependencies.
  By default the script does create `venv/` and `pip install -r
  requirements.txt`, so the project is immediately ready to migrate and run.

Run `python3 <skill_dir>/scripts/scaffold.py --help` for the full flag list.

## What gets generated vs. left as stubs

Generated in full (identical pattern across every project):
- `app/config.py`, `app/database.py`, `app/deps.py`, `app/main.py`
- `app/routers/__init__.py` (empty package, ready for route files)
- `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`,
  `migrations/README`, empty `migrations/versions/`
- `requirements.txt`, `.gitignore`
- `README.md` with the Alembic workflow and future-Postgres-upgrade sections
  already written (same as time-management/social-planning)
- `static/index.html`, `static/app.js`, `static/style.css` - a bare shell
  (title + empty mount point), not real UI

Left as near-empty stubs, because they're different for every project and
guessing at them would just create throwaway code to delete later:
- `app/models.py` - has the `Base` import ready, no tables
- `app/schemas.py` - has the Pydantic imports ready, no schemas
- `app/crud.py` - has the `models`/`schemas` imports ready, no functions
- No routers, no baseline Alembic migration, no seed data

## After scaffolding

This is the natural next-step checklist - work through it once the project
exists:

1. Define the real tables in `app/models.py`.
2. Add matching Pydantic schemas in `app/schemas.py` (Base/Create/Update/
   read-model, following the pattern in `models.py`'s docstring comment).
3. Add CRUD functions in `app/crud.py` and a router in `app/routers/`,
   then wire the router into `app/main.py` (there's a `# TODO` marking
   exactly where).
4. Generate and review the baseline migration:
   ```bash
   cd <project> && source venv/bin/activate
   alembic revision --autogenerate -m "baseline schema"
   alembic upgrade head
   ```
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
