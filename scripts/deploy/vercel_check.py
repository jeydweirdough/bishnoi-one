"""Before and after an app goes on Vercel: is everything set up, and did it start?

Run by the Deploy workflow (.github/workflows/deploy.yml) for each ticked app, from
the repo's root, with VERCEL_TOKEN (and VERCEL_SCOPE, for a team) set:

    python3 scripts/deploy/vercel_check.py check  --app bishnoi-crm --part "screens and API"
    python3 scripts/deploy/vercel_check.py health --project bishnoi-one-crm-backend --side backend

`check` goes through what the app needs (.github/deploy.json): its code can
run on Vercel, the token works, its Vercel projects exist with the right Root
Directory, their Production environment variables are there (names only,
never values), and the apps it depends on are online. Each result goes in the
run's summary as a checklist with what to do next. Anything missing that's
required stops the run before anything is deployed (exit 1).

`health` asks the freshly deployed project whether it started (an API's
/health, the screens' sign-in page) and, when it didn't, says which setting
to look at. It runs on a PC too: the same token and command.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = "https://api.vercel.com"
PARTS = {"screens and API": ("backend", "frontend"), "API only": ("backend",), "screens only": ("frontend",)}
SIDE = {"backend": "API", "frontend": "screens"}
GUIDE = "MAINTAINING.md, Putting an app online"


class Report:
    """The checklist: each line passed, a warning, or blocking; and what to do next."""

    def __init__(self, title: str) -> None:
        self.title, self.lines, self.todo = title, [], []

    def ok(self, what: str) -> None:
        self.lines.append(("✅", what))

    def warn(self, what: str, do: str | None = None) -> None:
        self.lines.append(("⚠️", what))
        if do:
            self.todo.append(("later", do))

    def block(self, what: str, do: str) -> None:
        self.lines.append(("❌", what))
        self.todo.append(("now", do))

    @property
    def blocked(self) -> bool:
        return any(mark == "❌" for mark, _ in self.lines)

    def write(self, verdict: str) -> None:
        out = [f"### {self.title}", "", f"**{verdict}**", ""]
        out += [f"- {mark} {what}" for mark, what in self.lines]
        now = [d for when, d in self.todo if when == "now"]
        later = [d for when, d in self.todo if when == "later"]
        if now:
            out += ["", "#### What to do before deploying", ""] + [f"{i}. {d}" for i, d in enumerate(now, 1)]
            out += ["", "Then run this workflow again."]
        if later:
            out += ["", "#### Worth doing (not blocking)", ""] + [f"- {d}" for d in later]
        text = "\n".join(out) + "\n"
        print(text)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write(text + "\n")


def output(**values: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            for k, v in values.items():
                f.write(f"{k}={v}\n")


class Vercel:
    def __init__(self, token: str, team: str | None) -> None:
        self.token, self.team = token, team

    def get(self, path: str, **params) -> dict:
        if self.team:
            params["slug"] = self.team
        url = f"{API}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}"})
        with urllib.request.urlopen(request, timeout=20) as r:  # noqa: S310 (Vercel's API)
            return json.loads(r.read())

    def project(self, name: str) -> dict | None:
        try:
            return self.get(f"/v9/projects/{urllib.parse.quote(name)}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def production_env(self, project_id: str) -> set[str]:
        """The names of the variables set for Production (values aren't read)."""
        envs = self.get(f"/v10/projects/{project_id}/env", decrypt="false").get("envs", [])
        names = set()
        for e in envs:
            target = e.get("target") or []
            if "production" in (target if isinstance(target, list) else [target]):
                names.add(e["key"])
        return names

    def live(self, project_id: str) -> dict | None:
        """The project's newest ready Production deployment, if it has one."""
        found = self.get("/v6/deployments", projectId=project_id, target="production", state="READY", limit="1").get("deployments", [])
        return found[0] if found else None


def address(project: dict) -> str | None:
    """The project's production address (its own .vercel.app, or a domain added to it)."""
    aliases = (project.get("targets") or {}).get("production", {}).get("alias") or []
    aliases += [a.get("domain") for a in project.get("alias") or [] if isinstance(a, dict)]
    aliases = [a for a in aliases if a]
    ours = [a for a in aliases if a.endswith(".vercel.app")]
    return (ours or aliases or [f"{project.get('name')}.vercel.app"])[0]


def load_config() -> dict:
    return json.loads((ROOT / ".github" / "deploy.json").read_text(encoding="utf-8"))


def connect(report: Report, config: dict) -> Vercel | None:
    token = os.environ.get("VERCEL_TOKEN", "").strip()
    if not token:
        report.block("No VERCEL_TOKEN secret", "On vercel.com: Account Settings > Tokens > Create (scope: the account or team the projects are in). "
                     "On GitHub: Settings > Secrets and variables > Actions > New repository secret, name VERCEL_TOKEN.")
        return None
    try:
        user = Vercel(token, None).get("/v2/user")["user"]["username"]
    except urllib.error.HTTPError:
        report.block("Vercel refused VERCEL_TOKEN", "The token is wrong or has expired: make a new one on vercel.com (Account Settings > Tokens) and replace the VERCEL_TOKEN secret.")
        return None
    except urllib.error.URLError:
        report.block("Vercel couldn't be reached", "Run the workflow again in a few minutes (vercel-status.com shows outages).")
        return None
    scope = (os.environ.get("VERCEL_SCOPE") or config.get("scope") or "").strip()
    if scope and scope != user:
        teams = [t["slug"] for t in Vercel(token, None).get("/v2/teams", limit="100").get("teams", [])]
        if scope not in teams:
            seen = ", ".join(["your own account"] + teams)
            report.block(f"The token (account {user}) can't see '{scope}'",
                         f"It can see: {seen}. If the projects are on your own account, set \"scope\" to \"\" in .github/deploy.json (or the repo variable VERCEL_SCOPE to {user}); else make the token in that team.")
            return None
        report.ok(f"Vercel token works (account {user}, team {scope})")
        return Vercel(token, scope)
    report.ok(f"Vercel token works (account {user})")
    return Vercel(token, None)


def code_ready(report: Report, app: str, spec: dict) -> bool:
    if not spec.get("ready"):
        report.block(f"{spec.get('name', app)}'s code isn't ready for Vercel", spec.get("not_ready", "See .github/deploy.json."))
        return False
    backend = ROOT / app / "backend"
    missing = [what for what, there in (
        ("backend/app/server.py (the Vercel entry point)", (backend / "app" / "server.py").exists()),
        ("[tool.vercel] in backend/pyproject.toml", "[tool.vercel]" in (backend / "pyproject.toml").read_text(encoding="utf-8")),
        ("the Postgres driver (psycopg) in backend/pyproject.toml", "psycopg" in (backend / "pyproject.toml").read_text(encoding="utf-8").lower()),
        ("frontend/vercel.json", (ROOT / app / "frontend" / "vercel.json").exists()),
    ) if not there]
    if missing:
        report.block("The code is missing what Vercel needs: " + "; ".join(missing), "Add them (copy from bishnoi-crm), commit, and push to main.")
        return False
    report.ok("The code can run on Vercel (entry point, Postgres driver, vercel.json)")
    return True


def check_env(report: Report, label: str, names: set[str], need: dict) -> None:
    missing = [k for k in need.get("required", {}) if k not in names]
    for k in missing:
        report.block(f"{label}: {k} isn't set for Production", f"Vercel > {label} > Settings > Environment Variables > add **{k}** (Production): {need['required'][k]}")
    if not missing and need.get("required"):
        report.ok(f"{label}: the required settings are there ({', '.join(need['required'])})")
    for k, why in need.get("never", {}).items():
        if k in names:
            report.block(f"{label}: {k} is set, and must not be online", f"Vercel > {label} > Settings > Environment Variables: {why}")
    for k, why in need.get("recommended", {}).items():
        if k not in names:
            report.warn(f"{label}: {k} isn't set (optional)", f"{label}: **{k}**: {why}")


def merged(config: dict, spec: dict, side: str) -> dict:
    out: dict = {}
    for source in (config.get("every", {}).get(side, {}), spec.get(side, {})):
        for kind, values in source.items():
            out.setdefault(kind, {}).update(values)
    return out


def is_live(report: Report, vercel: Vercel, project: dict, label: str, what_for: str, side: str = "backend") -> bool:
    deployment = vercel.live(project["id"])
    if deployment is None:
        report.block(f"{label} isn't online yet", what_for)
        return False
    ok, said = probe(address(project), side, tries=2)
    if ok:
        report.ok(f"{label} is online and answering ({address(project)})")
        return True
    report.block(f"{label} is deployed but not answering: {said}", f"Fix {label} first: {said} Then run its Deploy workflow again. {what_for}")
    return False


def check(app: str, part: str) -> int:
    config = load_config()
    spec = config.get("apps", {}).get(app)
    report = Report(f"Deploy {spec.get('name', app) if spec else app}: {part}")
    if spec is None:
        report.block(f"{app} isn't in .github/deploy.json", "Add it under \"apps\" (copy another app's entry).")
        report.write("Blocked: nothing was deployed")
        output(ready="false")
        return 1

    sides = PARTS[part]
    plan: dict[str, str] = {}
    if code_ready(report, app, spec):
        for side in sides:
            folder = f"{app}/{side}"
            name = config["projects"].get(folder)
            if name is None:
                report.block(f"No Vercel project for {folder}", f"Make it on Vercel (Add New > Project > this repo, Root Directory {folder}) and add \"{folder}\": \"<its name>\" to \"projects\" in .github/deploy.json.")
            else:
                plan[side] = name

    vercel = connect(report, config)
    if vercel is not None and plan:
        projects = {}
        for side, name in plan.items():
            label = f"{name} ({SIDE[side]})"
            project = vercel.project(name)
            if project is None:
                report.block(f"There's no Vercel project called {name}", f"On Vercel: Add New > Project > import this repo, name it **{name}**, Root Directory **{app}/{side}**. Don't deploy it from there: this workflow does. ({GUIDE})")
                continue
            projects[side] = project
            root = (project.get("rootDirectory") or "").strip("/")
            if root != f"{app}/{side}":
                report.block(f"{label}: its Root Directory is '{root or '(the repo root)'}'", f"Vercel > {name} > Settings > Build and Deployment > Root Directory: **{app}/{side}**.")
            else:
                report.ok(f"{label} exists, building {app}/{side}")
            check_env(report, name, vercel.production_env(project["id"]), merged(config, spec, side))

        # The screens alone need their API online already.
        if sides == ("frontend",):
            api_name = config["projects"].get(f"{app}/backend")
            api = vercel.project(api_name) if api_name else None
            if api is None:
                report.block(f"{spec['name']}'s API has no Vercel project", "Deploy the API first (part: API only).")
            else:
                is_live(report, vercel, api, f"{spec['name']}'s API ({api_name})", "Deploy the API first: run this workflow with part API only.")

        # Apps this one depends on.
        if "backend" in sides:
            for other, why in spec.get("after", {}).items():
                other_name = config["apps"].get(other, {}).get("name", other)
                other_api = config["projects"].get(f"{other}/backend")
                found = vercel.project(other_api) if other_api else None
                if found is None:
                    report.block(f"{other_name}'s API isn't on Vercel", f"{why} Tick **{other_name}** in Actions > Deploy too (it goes first), or deploy it first.")
                else:
                    is_live(report, vercel, found, f"{other_name}'s API ({other_api})", f"{why} Tick **{other_name}** in Actions > Deploy too (it goes first), or deploy it first.")

    if report.blocked:
        report.write("Blocked: nothing was deployed. Do the steps below, then run this workflow again.")
        output(ready="false")
        return 1
    report.write("Ready: deploying " + " and then ".join(f"{SIDE[s]} ({plan[s]})" for s in ("backend", "frontend") if s in plan))
    output(ready="true", api=plan.get("backend", ""), screens=plan.get("frontend", ""))
    return 0


def probe(host: str | None, side: str, tries: int = 6) -> tuple[bool, str]:
    """Asks the deployed project whether it started: (answered well, what it said)."""
    if not host:
        return False, "it has no production address."
    url = f"https://{host}" + ("/health" if side == "backend" else "/login")
    said = ""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bishnoi-deploy-check"}), timeout=30) as r:  # noqa: S310
                body = r.read()
                if side == "frontend" or json.loads(body or b"{}").get("ok"):
                    return True, f"{url} answered {r.status}"
                said = f"{url} answered without ok: {body[:200]!r}"
        except urllib.error.HTTPError as e:
            body = e.read()[:2000]
            try:
                data = json.loads(body)
            except ValueError:
                data = {}
            if e.code == 503 and data.get("problem"):
                checks = ", ".join(data.get("check") or [])
                return False, f"it couldn't start ({data['problem']}): check {checks}. {data.get('hint', '')}".strip()
            if e.code == 400 and b"host" in body.lower():
                return False, f"it refused its own address: add \"{host}\" to ALLOWED_HOSTS (as JSON) and deploy again."
            if e.code in (401, 403):  # neither page needs a sign-in: it's Vercel's own lock
                return False, (f"{url} answered {e.code}: Vercel's Deployment Protection is probably on. "
                               "Settings > Deployment Protection > Vercel Authentication: Standard Protection (production stays public).")
            said = f"{url} answered {e.code}"
        except (urllib.error.URLError, TimeoutError) as e:
            said = f"{url} can't be reached ({getattr(e, 'reason', e)})"
        if attempt < tries - 1:
            time.sleep(10)  # a first start runs the migrations
    return False, said + "."


def health(project_name: str, side: str) -> int:
    config = load_config()
    report = Report(f"After deploying {project_name}")
    vercel = connect(report, config)
    if vercel is None:
        report.write("Couldn't check")
        return 1
    project = vercel.project(project_name)
    ok, said = probe(address(project) if project else None, side)
    if ok:
        report.ok(f"{project_name} is online: {said}")
        report.write("Online")
        return 0
    report.block(f"{project_name} was deployed, but {said}",
                 f"Fix it (Vercel > {project_name} > Logs show the full error), then run the workflow again. The deploy before this one can be put back from Vercel > Deployments > Instant Rollback.")
    report.write("Deployed, but not answering")
    return 1


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # the marks, on a Windows console too
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check")
    c.add_argument("--app", required=True)
    c.add_argument("--part", choices=list(PARTS), default="screens and API")
    h = sub.add_parser("health")
    h.add_argument("--project", required=True)
    h.add_argument("--side", choices=["backend", "frontend"], required=True)
    args = parser.parse_args()
    try:
        return check(args.app, args.part) if args.command == "check" else health(args.project, args.side)
    except urllib.error.HTTPError as e:
        print(f"::error::Vercel answered {e.code} to {e.url}: {e.read()[:300]!r}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
