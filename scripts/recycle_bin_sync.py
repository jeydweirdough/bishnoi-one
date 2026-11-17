"""Writes the shared recycle-bin engine (scripts/recycle_bin_template.py) into every module of the
one backend as backend/modules/<module>/recycle_bin.py, with the module's table prefix and package.
Edit the template, then run: python scripts/recycle_bin_sync.py"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULES = {"crm": "nbcm_", "inventory": "nbin_", "finance": "nbfi_", "admin": "nbad_", "pharmacy": "nbph_"}
template = (ROOT / "scripts" / "recycle_bin_template.py").read_text(encoding="utf-8")
for module, prefix in MODULES.items():
    text = template.replace("__PREFIX__", prefix).replace("__PACKAGE__", f"modules.{module}")
    (ROOT / "backend" / "modules" / module / "recycle_bin.py").write_text(text, encoding="utf-8")
    print(f"backend/modules/{module}/recycle_bin.py written")
