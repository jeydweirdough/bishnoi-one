"""Which code this API is running: the commit it was built from, for the
sidebar's version line (beside the screens' own), so an update that reached
the screens but not the API shows.

On Vercel the commit is given (VERCEL_GIT_COMMIT_SHA). On this computer it's
asked of Git once, at start; "-dirty" means there were changes not yet
committed. Neither: None, and the screens say nothing about the API.
"""

import os
import subprocess
from pathlib import Path


def _commit() -> str | None:
    given = os.environ.get("VERCEL_GIT_COMMIT_SHA")
    if given:
        return given[:7]
    try:
        done = subprocess.run(
            ["git", "describe", "--always", "--dirty", "--abbrev=7", "--exclude", "*"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


COMMIT = _commit()
