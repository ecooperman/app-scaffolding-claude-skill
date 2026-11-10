#!/usr/bin/env python3
"""Scaffold a new FastAPI + SQLAlchemy + Alembic + SQLite project from the
template/ directory next to this script. See SKILL.md for the full picture;
this docstring only covers the mechanics.
"""
import argparse
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR.parent / "template"
MODULES_DIR = SCRIPT_DIR.parent / "modules"

# Optional features, copied in on request (see SKILL.md, "Optional modules"). Each
# lives in modules/<name>/: files/ is copied into the project as-is, and inject/
# holds snippets spliced into the template's marker lines. The order is the order
# their migrations chain after the baseline users migration.
MODULES = ["api-keys", "invites"]
BASE_REVISION = "b1e7c0a95d42"  # the template's create-users migration
MODULE_REVISIONS = {"api-keys": "c3e1a7f905d2", "invites": "d7b4f2a60c18"}

# A line like "# @@routers@@" or "<!-- @@nav@@ -->" in a template file: replaced by
# whatever the chosen modules inject for that name, or dropped if there is nothing.
MARKER_RE = re.compile(r"^[ \t]*(?:#|<!--) @@(\w+)@@(?: -->)?[ \t]*\n", re.MULTILINE)
# What goes between two modules' snippets for the same marker (default: nothing).
JOINERS = {"models": "\n\n", "schemas": "\n\n", "pages": "\n\n"}
# Markers whose snippets are wrapped as a group when there are any.
WRAPPERS = {"nav": ('  <nav class="app-links">\n', "  </nav>\n")}

PLACEHOLDERS = ("__PROJECT_TITLE__", "__PORT__", "__HOST__", "__DB_NAME__", "__PROJECT_DIR__")


def title_case_from_slug(slug: str) -> str:
    return " ".join(word.capitalize() for word in re.split(r"[-_]+", slug) if word)


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


def find_next_port(root: Path, host: str, start: int = 8000, step: int = 10) -> int:
    """Scan sibling projects under `root` for their app/config.py PORT value,
    and return the next free port above the highest one in use. Falls back
    to `start` if no sibling projects are found yet.
    """
    highest = start - step
    for config_path in root.glob("*/app/config.py"):
        text = config_path.read_text(errors="ignore")
        m = re.search(r"^PORT\s*=\s*(\d+)", text, re.MULTILINE)
        if m:
            highest = max(highest, int(m.group(1)))

    candidate = highest + step
    # Also make sure nothing is actually listening on the candidate port,
    # in case a sibling project used a port outside the step sequence.
    while port_in_use(host, candidate):
        candidate += step
    return candidate


def find_python() -> str:
    """A Python (3.10+, what the pinned dependencies need) to build the venv
    with: this one if it is new enough, else the newest on PATH. macOS's system
    python3 is 3.9, which can't install the template's requirements."""
    if sys.version_info >= (3, 10):
        return sys.executable
    for name in ("python3.13", "python3.12", "python3.11", "python3.10"):
        found = shutil.which(name)
        if found:
            return found
    sys.exit("Need Python 3.10 or newer for the virtualenv (found " + sys.version.split()[0] + ") - install one, or use --no-venv")


def substitute(text: str, values: dict) -> str:
    for key, value in values.items():
        text = text.replace(key, value)
    return text


def copy_template(target: Path, values: dict) -> None:
    for src in TEMPLATE_DIR.rglob("*"):
        rel = Path(substitute(str(src.relative_to(TEMPLATE_DIR)), values))
        dst = target / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = src.read_text()
        except UnicodeDecodeError:
            shutil.copyfile(src, dst)
            continue
        dst.write_text(substitute(text, values))


def copy_modules(target: Path, chosen: list, values: dict) -> dict:
    """Copy each chosen module's files into the project and return its injection
    snippets as {(relative path, marker): [text, ...]}."""
    snippets: dict = {}
    previous = BASE_REVISION
    for name in MODULES:
        if name not in chosen:
            continue
        module_values = {**values, "__DOWN_REVISION__": previous}
        previous = MODULE_REVISIONS[name]
        files_dir = MODULES_DIR / name / "files"
        for src in sorted(files_dir.rglob("*")):
            if src.is_dir():
                continue
            dst = target / substitute(str(src.relative_to(files_dir)), module_values)
            if dst.exists():
                sys.exit(f"module {name} would overwrite {dst.relative_to(target)}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(substitute(src.read_text(), module_values))
        inject_dir = MODULES_DIR / name / "inject"
        # inject/<path of the file to change>/<marker>.txt, e.g. inject/app/main.py/routers.txt
        for src in sorted(inject_dir.rglob("*.txt")):
            rel = str(src.parent.relative_to(inject_dir))
            snippets.setdefault((rel, src.stem), []).append(substitute(src.read_text(), module_values))
    return snippets


def splice_markers(target: Path, snippets: dict) -> None:
    """Replace every marker line in the project with its snippets (or nothing)."""
    for path in sorted(target.rglob("*")):
        if not path.is_file() or path.suffix not in (".py", ".html", ".md", ".css", ".js"):
            continue
        rel = str(path.relative_to(target))
        text = path.read_text()
        if "@@" not in text:
            continue

        def replace(match):
            parts = snippets.get((rel, match.group(1)), [])
            if not parts:
                return ""
            marker = match.group(1)
            # Whole classes/functions need two blank lines between them; one-line
            # snippets (imports, routers, args) none.
            body = JOINERS.get(marker, "").join(part if part.endswith("\n") else part + "\n" for part in parts)
            if marker.endswith("imports"):
                # Modules may both need the same import: keep each line once.
                seen, lines = set(), []
                for line in body.splitlines(keepends=True):
                    if line.strip() and line in seen:
                        continue
                    seen.add(line)
                    lines.append(line)
                body = "".join(lines)
            before, after = WRAPPERS.get(marker, ("", ""))
            if marker in WRAPPERS:
                body = "".join("    " + line for line in body.splitlines(keepends=True))
            return before + body + after

        new = MARKER_RE.sub(replace, text)
        if path.suffix == ".py":
            new = re.sub(r"\n{4,}", "\n\n\n", new)  # a dropped marker can leave a gap
        path.write_text(new)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_name", help="Directory name to create, e.g. recipe-box")
    parser.add_argument("--title", help="FastAPI app title / README heading (default: title-cased project name)")
    parser.add_argument("--db-name", help="SQLite filename, e.g. recipes.db (default: <project_name>.db)")
    parser.add_argument("--root", default=".", help="Parent directory to scaffold into (default: current directory)")
    parser.add_argument("--host", default="127.0.0.1", help="Host for app/config.py (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, help="Override the auto-picked port")
    parser.add_argument("--with-api-keys", action="store_true", help="Add the api-keys module: people's own encrypted API keys + a Profile page")
    parser.add_argument("--with-invites", action="store_true", help="Add the invites module: ask for new people to be let into the app, the administrator approves")
    parser.add_argument("--no-venv", action="store_true", help="Skip creating venv/ and installing dependencies")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"--root {root} is not a directory")

    # requirements.txt installs the shared package from ../shared-python, so it
    # must sit next to the new project (on the droplet: /opt/apps/shared-python).
    if not (root / "shared-python" / "pyproject.toml").is_file():
        sys.exit(f"{root / 'shared-python'} not found - clone the shared-python repo next to the projects first (see DEPLOYMENT.md)")

    target = root / args.project_name
    if target.exists() and any(target.iterdir()):
        sys.exit(f"{target} already exists and is not empty - refusing to overwrite")

    title = args.title or title_case_from_slug(args.project_name)
    db_name = args.db_name or f"{args.project_name.replace('-', '_')}.db"
    port = args.port if args.port is not None else find_next_port(root, args.host)

    values = {
        "__PROJECT_TITLE__": title,
        "__PORT__": str(port),
        "__HOST__": args.host,
        "__DB_NAME__": db_name,
        "__PROJECT_DIR__": args.project_name,
    }

    target.mkdir(parents=True, exist_ok=True)
    copy_template(target, values)
    chosen = [name for name, flag in (("api-keys", args.with_api_keys), ("invites", args.with_invites)) if flag]
    splice_markers(target, copy_modules(target, chosen, values))
    # Zip-packaged skills don't store empty directories, so migrations/versions/
    # may not exist in the on-disk template after install - ensure it anyway.
    (target / "migrations" / "versions").mkdir(parents=True, exist_ok=True)
    print(f"Scaffolded {target} (title={title!r}, host={args.host}, port={port}, db={db_name})")

    if not args.no_venv:
        venv_dir = target / "venv"
        print("Creating virtualenv and installing dependencies...")
        subprocess.run([find_python(), "-m", "venv", str(venv_dir)], check=True)
        pip = venv_dir / "bin" / "pip"
        # A fresh venv ships whatever pip came with the Python that made it; the
        # one in macOS's system Python is too old to install shared-python
        # (a pyproject.toml-only package) in editable mode.
        subprocess.run([str(pip), "install", "-q", "--upgrade", "pip"], check=True)
        # Run from the project folder: pip resolves "-e ../shared-python" in
        # requirements.txt against the current directory, not the file's.
        subprocess.run(
            [str(pip), "install", "-q", "-r", "requirements.txt", "-r", "requirements-dev.txt"],
            check=True,
            cwd=target,
        )

    print(
        "\nNext steps:\n"
        f"  1. Define tables in {target}/app/models.py - give each an owner_id (accounts are built in, see README)\n"
        f"  2. Add schemas in {target}/app/schemas.py and CRUD functions in {target}/app/crud.py\n"
        f"  3. Add a router under {target}/app/routers/ and wire it into {target}/app/main.py\n"
        f"  4. cd {target} && source venv/bin/activate && alembic upgrade head && alembic revision --autogenerate -m \"add my tables\" && alembic upgrade head\n"
        f"  5. Add two-person access tests under tests/ and run pytest\n"
        f"  6. python -m app.main, then open http://{args.host}:{port}"
    )


if __name__ == "__main__":
    main()
