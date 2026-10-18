"""The few words each company names its own way (Settings → Terms).

The CRM speaks in general terms (an account visited, a product presentation),
so it fits any company. A company whose people say it differently sets its
own: GetMeds visits doctors, at their clinic, and details products by molecule.
Everything else the CRM says stays general; customer types, form fields,
departments and price types are already each company's own.
"""

from typing import Any

# key: (what it's for, the general word)
TERMS: dict[str, tuple[str, Any]] = {
    "visited": ("Who field agents visit, one and many", {"one": "Account", "many": "Accounts"}),
    # The customer type field agents visit (its code); None: any customer.
    "visited_type": ("The customer type field agents visit", None),
    "detailing": ("Talking through products on a visit", "Product presentation"),
    "site": ("Where a visit happens", "Location"),
    "generic_name": ("A product's base name, shared by its brands", "Product family"),
}

GENERAL = {k: v for k, (_, v) in TERMS.items()}

# A pharmaceutical company's words, offered as a starting point.
PHARMA = {
    "visited": {"one": "Doctor", "many": "Doctors"},
    "visited_type": "doctor",
    "detailing": "Detailing",
    "site": "Clinic",
    "generic_name": "Molecule",
}


def terms_of(saved: dict | None) -> dict:
    """The company's words: what it set, over the general ones."""
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in GENERAL.items()}
    for k, v in (saved or {}).items():
        if k not in out:
            continue
        if k == "visited" and isinstance(v, dict):
            out[k] = {"one": (v.get("one") or out[k]["one"]).strip(), "many": (v.get("many") or out[k]["many"]).strip()}
        elif k == "visited_type":
            out[k] = (v or None) if isinstance(v, str) or v is None else out[k]
        elif isinstance(v, str) and v.strip():
            out[k] = v.strip()
    return out


def out(saved: dict | None) -> dict:
    """For the screens: camelCase keys."""
    t = terms_of(saved)
    return {"visited": t["visited"], "visitedType": t["visited_type"], "detailing": t["detailing"], "site": t["site"], "genericName": t["generic_name"]}
