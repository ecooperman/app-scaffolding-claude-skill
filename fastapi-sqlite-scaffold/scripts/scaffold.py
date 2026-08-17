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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_name", help="Directory name to create, e.g. recipe-box")
    parser.add_argument("--title", help="FastAPI app title / README heading (default: title-cased project name)")
    parser.add_argument("--db-name", help="SQLite filename, e.g. recipes.db (default: <project_name>.db)")
    parser.add_argument("--root", default=".", help="Parent directory to scaffold into (default: current directory)")
    parser.add_argument("--host", default="127.0.0.1", help="Host for app/config.py (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, help="Override the auto-picked port")
    parser.add_argument("--no-venv", action="store_true", help="Skip creating venv/ and installing dependencies")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"--root {root} is not a directory")

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
    # Zip-packaged skills don't store empty directories, so migrations/versions/
    # may not exist in the on-disk template after install - ensure it anyway.
    (target / "migrations" / "versions").mkdir(parents=True, exist_ok=True)
    print(f"Scaffolded {target} (title={title!r}, host={args.host}, port={port}, db={db_name})")

    if not args.no_venv:
        venv_dir = target / "venv"
        print("Creating virtualenv and installing dependencies...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        pip = venv_dir / "bin" / "pip"
        subprocess.run([str(pip), "install", "-q", "-r", str(target / "requirements.txt")], check=True)

    print(
        "\nNext steps:\n"
        f"  1. Define tables in {target}/app/models.py\n"
        f"  2. Add schemas in {target}/app/schemas.py and CRUD functions in {target}/app/crud.py\n"
        f"  3. Add a router under {target}/app/routers/ and wire it into {target}/app/main.py\n"
        f"  4. cd {target} && source venv/bin/activate && alembic revision --autogenerate -m \"baseline schema\" && alembic upgrade head\n"
        f"  5. python -m app.main, then open http://{args.host}:{port}"
    )


if __name__ == "__main__":
    main()
