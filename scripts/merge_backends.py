"""Stage M1 of docs/architecture/one-backend-plan.md: the eight APIs become modules of one backend.

    python scripts/merge_backends.py            # do it
    python scripts/merge_backends.py --dry-run  # say what it would move, change nothing

From the repository's top, on a clean tree (it was written against bc487a61). It:

1. `git mv`s each bishnoi-<x>/backend/app to backend/modules/<name> (history kept), with the
   app's migrations/, tests/, alembic.ini, .env.example and READMEs beside it
   (bishnoi-<x>/README.md -> README.md, backend/README.md -> API.md);
2. rewrites imports and references: `from app.` / `from app import` / `import app.` /
   `from tests.` / "app.x.y" strings (monkeypatch targets, "app.main:create_app") /
   `-m app.tools.x` / `app.tools.x` in text -> modules.<name>.;
3. points each config.py at the one backend: API_DIR = the module's folder (alembic.ini,
   migrations/), BACKEND_DIR/.env for settings, BACKEND_DIR/.data for local files, and
   <MODULE>_<SETTING> overrides (modules/module_settings.py);
4. fixes the few places that counted folders (copy_database backup names, seed_products,
   Finance's .env helpers, a test that reads the one app, two CRM tools' sys.path);
5. removes what one backend replaces (per-app main.py, pyproject.toml, uv.lock,
   .python-version, vercel.json, .gitignore);
6. on this computer only (gitignored files, never committed): merges every
   bishnoi-<x>/backend/.env into backend/.env (a setting two modules give differently becomes
   <MODULE>_<SETTING>; values are never printed), keeps the old files in
   backend/.data/old-env/, moves each .data/ into backend/.data/ and deletes .venv and caches.

Hand-written, not made here: backend/main.py, backend/pyproject.toml, backend/.gitignore,
backend/.env.example, backend/modules/__init__.py, backend/modules/module_settings.py.
A module already moved is skipped, so it can be run again after a partial run.
"""

from __future__ import annotations

import argparse
import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
MODULES_DIR = BACKEND / "modules"
DATA = BACKEND / ".data"

# Old folder -> package name, prefix of its own settings. Order: platform first, finance last.
MODULES = [
    ("platform", "platform", "PLATFORM_"),
    ("crm", "crm", "CRM_"),
    ("inventory", "inventory", "INVENTORY_"),
    ("admin", "admin", "ADMIN_"),
    ("pharmacy", "pharmacy", "PHARMACY_"),
    ("in-licensing", "in_licensing", "IN_LICENSING_"),
    ("regulatory", "regulatory", "REGULATORY_"),
    ("finance", "finance", "FINANCE_"),
]

# Settings a prefix would read from someone else's name: Finance's crm_company is read from
# CRM_COMPANY, which with the CRM_ prefix would also be the CRM's own `company`. The CRM's
# `company` is therefore never read with the prefix (COMPANY still sets it).
SKIP_PREFIXED = {"crm": ("company",)}

TEXT_SUFFIXES = {".py", ".ini", ".mako", ".md", ".txt", ".toml", ".cfg", ".json", ".example", ""}
DRY = False


def run(*args: str) -> None:
    print("  $", " ".join(args))
    if not DRY:
        subprocess.run(args, cwd=ROOT, check=True)


def git_mv(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if not DRY:
        dst.parent.mkdir(parents=True, exist_ok=True)
    run("git", "mv", str(src.relative_to(ROOT)), str(dst.relative_to(ROOT)))


def git_rm(path: Path) -> None:
    if path.exists():
        run("git", "rm", "-q", str(path.relative_to(ROOT)))


# ---------------------------------------------------------------- rewriting

def top_level_names(package: Path) -> set[str]:
    names = set()
    for p in package.iterdir():
        if p.is_dir() and (p / "__init__.py").exists():
            names.add(p.name)
        elif p.suffix == ".py":
            names.add(p.stem)
    return names - {"__init__"}


def rewrite_text(text: str, name: str, names: set[str]) -> str:
    pkg = f"modules.{name}"
    text = re.sub(r"(?m)(^|[^\w.])from app(\.|\s+import\b)", rf"\1from {pkg}\2", text)
    text = re.sub(r"(?m)(^|[^\w.])import app\.", rf"\1import {pkg}.", text)
    text = re.sub(r"(?m)(^|[^\w.])from tests(\.|\s+import\b)", rf"\1from {pkg}.tests\2", text)
    text = re.sub(r"(?m)(^|[^\w.])import tests\b", rf"\1import {pkg}.tests", text)
    text = re.sub(r"-m app\.", f"-m {pkg}.", text)
    alt = "|".join(sorted(map(re.escape, names), key=len, reverse=True))
    # "app.zoho_delivery.payload", 'app.main:create_app', `app.tools.users`: only real submodules,
    # so a FastAPI object's attribute in a docstring (`app.routes`) stays as it is.
    text = re.sub(rf"([\"'`])app\.({alt})\b", rf"\1{pkg}.\2", text)
    text = re.sub(r"(?<![\w./])app\.tools\.", f"{pkg}.tools.", text)
    return text


CONFIG_DIRS_OLD = 'API_DIR = Path(__file__).resolve().parent.parent\nDATA_DIR = API_DIR / ".data"\n'
CONFIG_DIRS_NEW = (
    "# This module's folder (backend/modules/<name>): its alembic.ini and migrations/.\n"
    "API_DIR = Path(__file__).resolve().parent\n"
    "# The one backend (backend/): its .env, and .data/ with every module's local files.\n"
    "BACKEND_DIR = API_DIR.parent.parent\n"
    'DATA_DIR = BACKEND_DIR / ".data"\n'
)


def rewrite_config(text: str, name: str, prefix: str) -> str:
    if "BACKEND_DIR" in text:
        return text
    assert CONFIG_DIRS_OLD in text, f"{name}: config.py's folders aren't as expected"
    text = text.replace(CONFIG_DIRS_OLD, CONFIG_DIRS_NEW)
    old = 'model_config = SettingsConfigDict(env_file=API_DIR / ".env"'
    assert old in text, f"{name}: config.py's model_config isn't as expected"
    text = text.replace(old, 'model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env"')
    text = text.replace(
        "from pydantic_settings import BaseSettings, SettingsConfigDict\n",
        "from pydantic_settings import BaseSettings, SettingsConfigDict\n\nfrom modules.module_settings import module_sources\n",
        1,
    )
    skip = SKIP_PREFIXED.get(name, ())
    hook = (
        "\n"
        "    @classmethod\n"
        "    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):\n"
        f"        # {prefix}<SETTING> (e.g. {prefix}DATABASE_URL) wins over <SETTING> for this module, in the\n"
        "        # environment and in backend/.env; on a server one DATABASE_URL serves every module.\n"
        f"        return module_sources({prefix!r}, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings"
        + (f", skip={skip!r}" if skip else "")
        + ")\n"
    )
    line = re.search(r'(?m)^    model_config = SettingsConfigDict\(env_file=BACKEND_DIR / "\.env".*\n', text)
    text = text[: line.end()] + hook + text[line.end():]
    return text


# One-off fixes for code that counted folders from where it used to be.
FIXES: dict[str, list[tuple[str, str]]] = {
    "*:tools/copy_database.py": [
        ('API_DIR.parent.name.removeprefix("bishnoi-")', "API_DIR.name"),
    ],
    "inventory:tools/seed_products.py": [
        ("APP_DIR = Path(__file__).resolve().parent.parent.parent  # bishnoi-inventory/backend",
         "APP_DIR = Path(__file__).resolve().parents[3]  # backend/ (the one backend)"),
        ("MODULE_DIR = APP_DIR.parent  # bishnoi-inventory", "MODULE_DIR = APP_DIR / \"modules\" / \"inventory\""),
        ("REPO_DIR = MODULE_DIR.parent  # bishnoi-one", "REPO_DIR = APP_DIR.parent  # bishnoi-one"),
        ('REPO_DIR / "bishnoi-crm" / "backend" / ".data" / "crm-getmeds.db"', 'APP_DIR / ".data" / "crm-getmeds.db"'),
        ('REPO_DIR / "bishnoi-crm" / "backend" / ".data" / "crm.db"', 'APP_DIR / ".data" / "crm.db"'),
    ],
    "finance:tools/setup_zoho.py": [
        ("from modules.finance.config import API_DIR", "from modules.finance.config import BACKEND_DIR"),
        ("path = API_DIR / '.env'", "path = BACKEND_DIR / '.env'"),
    ],
    "finance:tools/neon_preflight.py": [
        ("from modules.finance.config import API_DIR", "from modules.finance.config import BACKEND_DIR"),
        ("dotenv_values(API_DIR/'.env')", "dotenv_values(BACKEND_DIR/'.env')"),
    ],
    "finance:tests/test_budget_screen_contract.py": [
        ("Path(__file__).resolve().parents[3]", "Path(__file__).resolve().parents[4]"),
    ],
    "crm:tools/import_employees_structure.py": [
        ('os.path.join(os.path.dirname(__file__), "..", "..")', 'os.path.join(os.path.dirname(__file__), "..", "..", "..")'),
    ],
    "crm:tools/sync_neon_live.py": [
        ('os.path.join(os.path.dirname(__file__), "..", "..")', 'os.path.join(os.path.dirname(__file__), "..", "..", "..")'),
    ],
}


def apply_fixes(name: str, package: Path) -> None:
    for key, pairs in FIXES.items():
        who, rel = key.split(":", 1)
        if who not in ("*", name):
            continue
        file = package / rel
        if not file.exists():
            continue
        text = file.read_text(encoding="utf-8-sig") if not DRY else ""
        for old, new in pairs:
            if DRY:
                continue
            if old in text:
                text = text.replace(old, new)
            elif new not in text:
                print(f"  ! {name}/{rel}: expected text not found: {old[:60]}")
        if not DRY:
            write_keeping_bom(file, text)


def write_keeping_bom(file: Path, text: str) -> None:
    raw = file.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    crlf = b"\r\n" in raw
    if crlf:
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    file.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def read(file: Path) -> str:
    return file.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")


def rewrite_module(name: str, prefix: str, package: Path) -> None:
    names = top_level_names(package)
    changed = 0
    for file in package.rglob("*"):
        if not file.is_file() or "__pycache__" in file.parts:
            continue
        if file.suffix not in TEXT_SUFFIXES and file.name != "alembic.ini":
            continue
        try:
            text = read(file)
        except UnicodeDecodeError:
            continue
        new = rewrite_text(text, name, names)
        if file.name == "config.py" and file.parent == package:
            new = rewrite_config(new, name, prefix)
        if file.name == "alembic.ini" and file.parent == package:
            # The one backend's folder on the path, so `alembic -c modules/<name>/alembic.ini` finds modules.<name>.
            new = new.replace("prepend_sys_path = .\n", "prepend_sys_path = %(here)s/../..\n")
            new = new.replace("uv run alembic upgrade head", f"uv run alembic -c modules/{name}/alembic.ini upgrade head")
        if new != text:
            changed += 1
            write_keeping_bom(file, new)
    apply_fixes(name, package)
    print(f"  rewrote {changed} files in modules/{name}")


# ---------------------------------------------------------------- moving

def move_module(folder: str, name: str, prefix: str) -> None:
    old = ROOT / f"bishnoi-{folder}"
    api = old / "backend"
    package = MODULES_DIR / name
    print(f"== {folder} -> backend/modules/{name}")
    if package.exists():
        print("  already moved")
    elif not (api / "app").exists():
        print("  nothing to move")
        return
    else:
        git_mv(api / "app", package)
        git_mv(api / "migrations", package / "migrations")
        git_mv(api / "tests", package / "tests")
        git_mv(api / "alembic.ini", package / "alembic.ini")
        git_mv(api / ".env.example", package / ".env.example")
        git_mv(old / "README.md", package / "README.md")
        git_mv(api / "README.md", package / "API.md")
        for doc in sorted(old.glob("*.md")):
            git_mv(doc, package / doc.name)
        for gone in ("main.py", "pyproject.toml", "uv.lock", ".python-version", "vercel.json", ".vercelignore"):
            git_rm(api / gone)
        git_rm(old / ".gitignore")
        if not DRY:
            rewrite_module(name, prefix, package)
    if not DRY:
        local_files(folder, name)


# ---------------------------------------------------------------- this computer's files

def settings_fields() -> dict[str, set[str]]:
    """Each module's settings (field names), read from its config.py."""
    out = {}
    for _, name, _ in MODULES:
        config = MODULES_DIR / name / "config.py"
        if not config.exists():
            out[name] = set()
            continue
        tree = ast.parse(read(config))
        fields = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Settings":
                fields |= {b.target.id for b in node.body if isinstance(b, ast.AnnAssign) and isinstance(b.target, ast.Name)}
        out[name] = fields
    return out


def env_pairs(file: Path) -> list[tuple[str, str]]:
    pairs = []
    for line in read(file).splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, value = s.split("=", 1)
        pairs.append((key.strip().removeprefix("export ").strip(), value.strip()))
    return pairs


def merge_env() -> None:
    """backend/.env from every module's old .env, once (an existing backend/.env is kept)."""
    target = BACKEND / ".env"
    found = {name: ROOT / f"bishnoi-{folder}" / "backend" / ".env" for folder, name, _ in MODULES}
    found = {n: f for n, f in found.items() if f.exists()}
    if not found:
        return
    if target.exists():
        print("  backend/.env exists: old .env files are only kept in .data/old-env/")
    else:
        fields = settings_fields()
        prefix = {name: p for _, name, p in MODULES}
        values: dict[str, dict[str, str]] = {}
        for name, file in found.items():
            for key, value in env_pairs(file):
                values.setdefault(key, {})[name] = value
        shared, own, unread = [], {n: [] for n in found}, []
        for key, given in values.items():
            readers = {n for n, f in fields.items() if key.lower() in f}
            setters = {n for n in given if n in readers}
            if not readers:
                # Nobody reads it as a setting (a tool may, from the environment): kept as it was.
                if len(set(given.values())) == 1:
                    shared.append((key, next(iter(given.values())), "read by no module's settings"))
                else:
                    for n, v in given.items():
                        unread.append((n, key, v))
            elif readers <= set(given) and len({given[n] for n in readers}) == 1:
                shared.append((key, given[next(iter(readers))], None))
            else:
                for n in sorted(setters):
                    own[n].append((prefix[n] + key, given[n]))
                for n in sorted(set(given) - readers):
                    unread.append((n, key, given[n]))
        lines = [
            "# Settings for the one backend (every module). Kept on this computer only: never committed.",
            "# A setting applies to every module that has it; <MODULE>_<SETTING> (PLATFORM_, CRM_, INVENTORY_,",
            "# FINANCE_, ADMIN_, PHARMACY_, IN_LICENSING_, REGULATORY_) applies to one module and wins over it,",
            "# e.g. CRM_DATABASE_URL. Made by scripts/merge_backends.py from each module's old backend/.env",
            "# (copies in .data/old-env/); a setting the modules gave differently is a module's own here.",
            "",
        ]
        for key, value, note in shared:
            if note:
                lines.append(f"# {note}")
            lines.append(f"{key}={value}")
        for n, pairs in own.items():
            if pairs:
                lines += ["", f"# {n}"] + [f"{k}={v}" for k, v in pairs]
        if unread:
            lines += ["", "# Given in a module's old .env, but that module has no such setting:"]
            lines += [f"# ({n}) {k}={v}" for n, k, v in unread]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  backend/.env: {len(shared)} shared settings, "
              f"{sum(map(len, own.values()))} module-only, {len(unread)} commented (names only shown in the file)")


def merge_tree(src: Path, dst: Path, module: str) -> None:
    """Move src's contents into dst; a file already there keeps its place and ours gets '<module>-' in front."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in list(src.iterdir()):
        target = dst / item.name
        if not target.exists():
            shutil.move(str(item), str(target))
        elif item.is_dir() and target.is_dir():
            merge_tree(item, target, module)
        else:
            shutil.move(str(item), str(dst / f"{module}-{item.name}"))
    src.rmdir()


def local_files(folder: str, name: str) -> None:
    old = ROOT / f"bishnoi-{folder}"
    api = old / "backend"
    keep = DATA / "old-env"
    for env in (api / ".env", api / ".env.local"):
        if env.exists():
            keep.mkdir(parents=True, exist_ok=True)
            shutil.copy2(env, keep / f"{name}{env.name}")
    if (api / ".data").exists():
        merge_tree(api / ".data", DATA, name)
        print(f"  moved .data/ into backend/.data/")
    # Anything else kept here and ignored by Git (old SQLite files, a data/ folder, a Claude
    # plugin's folder) is moved, not deleted, into backend/.data/old-<module>/.
    leftovers = DATA / f"old-{name}"
    for junk in (".venv", ".pytest_cache", ".ruff_cache", "__pycache__", ".mypy_cache"):
        shutil.rmtree(api / junk, ignore_errors=True)
    for place in (api, old):
        if not place.exists():
            continue
        for item in list(place.iterdir()):
            if item.name in (".env", ".env.local") or item == api:
                continue
            leftovers.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(leftovers / (item.name if place == old else f"backend-{item.name}")))
    # The old .env files stay until finish_local() has merged them into backend/.env.


def finish_local() -> None:
    merge_env()
    for folder, name, _ in MODULES:
        old = ROOT / f"bishnoi-{folder}"
        api = old / "backend"
        if (BACKEND / ".env").exists():
            for env in (api / ".env", api / ".env.local"):
                env.unlink(missing_ok=True)
        for place in (api, old):
            try:
                place.rmdir()
            except OSError:
                if place.exists():
                    print(f"  ! {place.relative_to(ROOT)} isn't empty: left as it is")


def main() -> None:
    global DRY
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true")
    DRY = parser.parse_args().dry_run
    if not (MODULES_DIR / "__init__.py").exists():
        print("! backend/modules/__init__.py is missing: add the hand-written backend files too (see the docstring).")
    for folder, name, prefix in MODULES:
        move_module(folder, name, prefix)
    if not DRY:
        finish_local()
    print("Done. Next: cd backend && uv lock && uv run python -m pytest modules/<name>/tests -q")


if __name__ == "__main__":
    sys.exit(main())
