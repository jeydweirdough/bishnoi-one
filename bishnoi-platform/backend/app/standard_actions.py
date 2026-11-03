"""The standard actions every role is described in (2026-11-04), whatever app and area it is for.

CRUD:      create, read, update, delete
Workflow:  submit, approve, reject, return, cancel, reopen
Special:   import, export, print, assign, transfer, post, void
Other:     anything an app offers that isn't one of these (receive, dispatch, release, verify...): kept as the app names it.

Each app keeps declaring and enforcing its own permissions ("customers.edit"); this only names them the same way, so a
role is read, compared and set in one vocabulary, and the defaults of Mentor, Coach and Coachee are written once.
Nothing here grants anything by itself: a standard action is only what an app's own action word means.
"""

CRUD = ("create", "read", "update", "delete")
WORKFLOW = ("submit", "approve", "reject", "return", "cancel", "reopen")
SPECIAL = ("import", "export", "print", "assign", "transfer", "post", "void")
STANDARD = CRUD + WORKFLOW + SPECIAL

# What an app's own action word means. Only words with one clear meaning: the rest stay "other", never guessed.
WORDS = {"view": "read", "edit": "update", **{a: a for a in STANDARD if a not in ("read", "update")}}

# What a role may do by default (Mentor above Coach above Coachee). Delete, post and void are never default.
COACHEE = ("read", "create", "update", "submit", "print")
COACH = COACHEE + ("approve", "reject", "return", "assign", "export")
MENTOR = COACH + ("import", "cancel", "reopen", "transfer")
LEVELS = {"coachee": COACHEE, "coach": COACH, "mentor": MENTOR}
# Whose records each level reaches, in the order a module's scopes are tried.
REACH = {"coachee": ("own",), "coach": ("managed", "team", "own"), "mentor": ("managed", "team", "own")}


def standard_of(action_key: str) -> str | None:
    """The standard action an app's action word means, or None for an "other" action."""
    return WORDS.get(str(action_key).strip().lower())


def kind_of(standard: str | None) -> str:
    return "crud" if standard in CRUD else "workflow" if standard in WORKFLOW else "special" if standard in SPECIAL else "other"


def describe(areas: list[dict]) -> list[dict]:
    """The module's areas, each action carrying its standard action and kind."""
    out = []
    for area in areas:
        actions = []
        for a in area.get("actions", []):
            std = standard_of(a.get("key", ""))
            actions.append({**a, "standard": std, "kind": kind_of(std)})
        out.append({**area, "actions": actions})
    return out


def defaults(areas: list[dict], scopes: list[dict], level: str) -> tuple[list[str], str | None]:
    """The permissions a level holds by default in one module, and the reach it gets there (None: the module has none)."""
    allowed = set(LEVELS[level])
    held = sorted({a["permission"] for area in areas for a in area.get("actions", []) if standard_of(a.get("key", "")) in allowed})
    offered = {s.get("key") for s in scopes}
    reach = next((r for r in REACH[level] if r in offered), None)
    return held, reach
