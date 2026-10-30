"""Writes the shared recycle-bin engine (scripts/recycle_bin_template.py) into every app as app/recycle_bin.py,
with the app's table prefix. Edit the template, then run: python scripts/recycle_bin_sync.py"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
APPS = {"crm": "nbcm_", "inventory": "nbin_", "finance": "nbfi_", "admin": "nbad_", "pharmacy": "nbph_"}
template = (ROOT / "scripts" / "recycle_bin_template.py").read_text(encoding="utf-8")
for app, prefix in APPS.items():
    (ROOT / f"bishnoi-{app}" / "backend" / "app" / "recycle_bin.py").write_text(template.replace("__PREFIX__", prefix), encoding="utf-8")
    print(f"bishnoi-{app}: app/recycle_bin.py written")
