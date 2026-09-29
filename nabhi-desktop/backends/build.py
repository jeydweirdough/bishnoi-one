"""Packages one Nabhi API to run inside Nabhi.exe, with Python and its
packages included: nothing to install on the company's PCs.

Run with that API's own Python (its packages are the ones bundled):

    cd nabhi-crm/backend
    uv run --with pyinstaller python ../../nabhi-desktop/backends/build.py crm

    cd nabhi-inventory/backend
    uv run --with pyinstaller python ../../nabhi-desktop/backends/build.py inventory

The result is a folder, nabhi-desktop/dist/backends/<app>/, holding
nabhi-<app>-api.exe and what it needs. Its migrations and alembic.ini go
beside the program, where the API looks for them (app/config.py API_DIR).
"""

import os
import sys
from pathlib import Path

APPS = {"crm": "nabhi-crm", "inventory": "nabhi-inventory"}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in APPS:
        sys.exit(f"Use: build.py {' | '.join(APPS)}")
    app = sys.argv[1]
    here = Path(__file__).resolve().parent
    desktop = here.parent
    backend = desktop.parent / APPS[app] / "backend"
    if Path.cwd().resolve() != backend.resolve():
        sys.exit(f"Run it from {backend}, with that API's Python (uv run --with pyinstaller python ...).")

    import PyInstaller.__main__

    sep = os.pathsep
    PyInstaller.__main__.run([
        str(here / "entry.py"),
        "--name", f"nabhi-{app}-api",
        "--onedir",
        "--noconfirm",
        "--clean",
        "--console",  # Nabhi.exe reads its "ready" line; the window itself is never shown
        "--distpath", str(desktop / "dist" / "backends"),
        "--workpath", str(desktop / "build" / app),
        "--specpath", str(desktop / "build" / app),
        "--paths", str(backend),
        "--add-data", f"{backend / 'alembic.ini'}{sep}.",
        "--add-data", f"{backend / 'migrations'}{sep}migrations",
        "--collect-submodules", "app",
        "--collect-submodules", "uvicorn",
        "--collect-submodules", "psycopg",
        "--collect-all", "psycopg_binary",
        "--collect-submodules", "alembic",
        "--collect-data", "alembic",
        "--hidden-import", "email_validator",
    ])
    print(f"\nBuilt: {desktop / 'dist' / 'backends' / f'nabhi-{app}-api'}")


if __name__ == "__main__":
    main()
