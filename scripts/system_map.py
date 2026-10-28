"""Writes docs/system-map.md: what each app has, read from the code (Phase 0 of
the feature plan, 2026-10-28). Run it again after a change to refresh the map:

    python scripts/system_map.py

For each app: its screens (the sidebar), records (tables), reports, permissions,
settings (names only, never values), links to other apps, and its API's endpoints.
Only reads files; needs nothing but Python.
"""

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONT = ROOT / "bishnoi-one-app" / "frontend" / "src" / "modules"
OUT = ROOT / "docs" / "system-map.md"

# app folder, name shown, its module folder in the one app, address in the one app
APPS = [
    ("bishnoi-platform", "Platform (Admin Console)", "../one/admin-console/frame.tsx", "/platform"),
    ("bishnoi-crm", "CRM", "crm", "/crm"),
    ("bishnoi-inventory", "Inventory", "inventory", "/inventory"),
    ("bishnoi-finance", "Finance (Books)", "finance", "/finance"),
    ("bishnoi-pharmacy", "Pharmacy", "pharmacy", "/pharmacy"),
    ("bishnoi-admin", "Executive Admin (Office)", "admin", "/admin"),
    ("bishnoi-in-licensing", "In-Licensing", "inlicensing", "/in-licensing"),
    ("bishnoi-regulatory", "Regulatory", "regulatory", "/regulatory"),
]


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# --- what's read ------------------------------------------------------------------


def screens(module: str, base: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """The sidebar: groups and their pages, in order."""
    # A module's sidebar is its nav.tsx; the Admin Console's menu is a file of its own.
    if module.endswith(".tsx"):
        navs = [(FRONT / module).resolve()]
    else:
        navs = sorted((FRONT / module).rglob("nav.tsx")) if (FRONT / module).exists() else []
    if not navs:
        return []
    text = read(navs[0])
    groups: list[tuple[str, list[tuple[str, str]]]] = []
    for line in text.splitlines():
        # A group's name: a label with no address before it on the line ("label: "Inventory", icon…").
        group = re.match(r'^\s*\{?\s*label:\s*"([^"]+)"', line)
        if group:
            groups.append((group.group(1), []))
        for href, label in re.findall(r'href:\s*[`"]([^`"]+)[`"][^{}]*?label:\s*"([^"]+)"', line):
            if href == base:  # the module's Home, listed last in some sidebars: a group of its own
                if not any(g == "Home" for g, _ in groups):
                    groups.insert(0, ("Home", [(label, href)]))
                continue
            if not groups:
                groups.append(("Pages", []))
            if (label, href) not in groups[-1][1]:
                groups[-1][1].append((label, href))
    return [(g, pages) for g, pages in groups if pages]


def tables(backend: Path) -> list[tuple[str, str, str]]:
    """(table, class, what it is) from models.py."""
    text = read(backend / "app" / "models.py")
    out = []
    for m in re.finditer(r'^class (\w+)\([^)]*\):\n(?:\s+"""(.*?)"""\n)?(?:.*\n){0,6}?\s+__tablename__ = "([^"]+)"', text, re.M | re.S):
        cls, doc, table = m.groups()
        about = " ".join((doc or "").split())
        about = about.split(". ")[0].rstrip(".")[:140]
        out.append((table, cls, about))
    seen = {t for t, _, _ in out}
    for table in re.findall(r'__tablename__ = "([^"]+)"', text):
        if table not in seen:
            out.append((table, "", ""))
    return out


def endpoints(backend: Path) -> list[tuple[str, list[str]]]:
    """Per router file: METHOD path."""
    out = []
    for f in sorted((backend / "app" / "routers").glob("*.py")):
        text = read(f)
        prefix = re.search(r'APIRouter\([^)]*prefix="([^"]*)"', text)
        prefix = prefix.group(1) if prefix else ""
        found = [f"{m.upper()} {prefix}{path}" for m, path in re.findall(r'@router\.(get|post|put|patch|delete)\(\s*"([^"]*)"', text)]
        if found:
            out.append((f.stem, found))
    return out


def permissions(backend: Path) -> list[tuple[str, str, str]]:
    """(area name, group, actions)."""
    text = read(backend / "app" / "permissions.py")
    consts = {name: re.findall(r'"([a-z_]+)"', body) for name, body in re.findall(r'^([A-Z_]+)\s*=\s*\(([^)]*)\)', text, re.M)}
    out = []
    for m in re.finditer(r'Area\(\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*(\([^)]*\)|[A-Z_]+)', text):
        key, name, group, actions = m.groups()
        acts = consts.get(actions) or re.findall(r'"([a-z_]+)"', actions)
        out.append((f"{name} (`{key}`)", group, ", ".join(acts)))
    return out


def reports(backend: Path) -> list[tuple[str, str, bool]]:
    """(group, title, fixed) from the reports registry."""
    out = []
    for f in list((backend / "app" / "routers").glob("*.py")) + list((backend / "app").glob("*.py")):
        for m in re.finditer(r'Report\(\s*"[a-z0-9-]+",\s*"([^"]+)",\s*"([^"]+)"(.*?)\)\s*,?\s*$', read(f), re.M):
            title, group, rest = m.groups()
            out.append((group, title, "fixed=True" in rest))
    return sorted(set(out), key=lambda r: (r[0], r[1]))


def settings(backend: Path) -> list[str]:
    """Setting names (as .env takes them); never values."""
    text = read(backend / "app" / "config.py")
    body = text.split("class Settings", 1)[-1]
    names = re.findall(r'^    ([a-z_][a-z0-9_]*)\s*:\s*[^=\n]+', body, re.M)
    return [n.upper() for n in names if not n.startswith("_") and n != "model_config"]


def links(backend: Path) -> tuple[list[str], list[str]]:
    """(apps it calls, endpoints it offers other apps)."""
    uses = re.search(r"USES[^=]*=\s*\{(.*?)\n\}", read(backend / "app" / "platform_links.py"), re.S)
    calls = re.findall(r'^\s*"([a-z_]+)":', uses.group(1), re.M) if uses else []
    offers = []
    for name, found in endpoints(backend):
        offers += [e for e in found if "/integration" in e or "/connect" in e]
    return calls, offers


def migration(backend: Path) -> str:
    revs = sorted(p.stem for p in (backend / "migrations" / "versions").glob("*.py"))
    return revs[-1] if revs else "none"


# --- the document -----------------------------------------------------------------


def main() -> None:
    lines = [
        "# System map",
        "",
        f"What each app has, read from the code on {date.today().isoformat()} by `scripts/system_map.py`.",
        "Don't edit by hand: change the code, then run `python scripts/system_map.py` again.",
        "Settings are listed by name only. The feature plan (Desktop, `bishnoi-one-feature-plan.html`) says where each app is going.",
        "",
        "## At a glance",
        "",
        "| App | Address | Screens | Records (tables) | Reports | Permission areas | API endpoints | Latest migration |",
        "|---|---|---|---|---|---|---|---|",
    ]
    sections = []
    for folder, name, module, base in APPS:
        backend = ROOT / folder / "backend"
        if not backend.exists():
            continue
        sc, tb, ep, pm, rp = screens(module, base), tables(backend), endpoints(backend), permissions(backend), reports(backend)
        st, (calls, offers) = settings(backend), links(backend)
        n_pages = sum(len(p) for _, p in sc)
        n_eps = sum(len(e) for _, e in ep)
        lines.append(f"| [{name}](#{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}) | `{base}` | {n_pages} | {len(tb)} | {len(rp)} | {len(pm)} | {n_eps} | {migration(backend)} |")

        s = [f"## {name}", "", f"Folder `{folder}/backend`, screens at `{base}` in the one app.", ""]
        s += ["### Screens (the sidebar)", ""]
        if sc:
            for group, pages in sc:
                s.append(f"- **{group}:** " + ", ".join(f"{label} (`{href}`)" for label, href in pages))
        else:
            s.append("- None found.")
        s += ["", "### Records (tables)", "", "| Table | What it is |", "|---|---|"]
        s += [f"| `{t}` | {about or cls} |" for t, cls, about in tb] or ["| none | |"]
        s += ["", "### Reports", ""]
        if rp:
            groups: dict[str, list[str]] = {}
            for group, title, fixed in rp:
                groups.setdefault(group, []).append(title + (" *(fixed)*" if fixed else ""))
            s += [f"- **{g}:** " + ", ".join(ts) for g, ts in groups.items()]
        else:
            s.append("- None.")
        s += ["", "### Permissions", ""]
        if pm:
            s += ["| Area | Group | Actions |", "|---|---|---|"] + [f"| {a} | {g} | {acts} |" for a, g, acts in pm]
        else:
            s.append("- None declared.")
        s += ["", "### Links to other apps", ""]
        s.append(f"- **Calls:** {', '.join(calls) if calls else 'none'}")
        s.append(f"- **Offers to other apps:** {', '.join(f'`{o}`' for o in offers) if offers else 'none'}")
        s += ["", "### Settings (names only)", "", ", ".join(f"`{n}`" for n in st) or "None.", ""]
        s += ["### API endpoints", "", "<details><summary>" + f"{n_eps} endpoints in {len(ep)} files" + "</summary>", ""]
        for file, found in ep:
            s.append(f"- **{file}:** " + ", ".join(f"`{e}`" for e in found))
        s += ["", "</details>", ""]
        sections.append("\n".join(s))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n\n" + "\n".join(sections), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    sys.exit(main())
