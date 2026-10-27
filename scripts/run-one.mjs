/**
 * Bishnoi One's one app on this computer, with everything it needs, in one go
 * (decided 2026-10-23): every module's screens at http://localhost:4301, and
 * the Platform's API (the one sign-in) and each module's API behind them.
 *
 *   npm run one              # prepare what's missing, then run it all; Ctrl+C stops it all
 *   npm run one -- --setup   # prepare only
 *
 * Each part's output is labelled ([platform], [crm], …, [one]). Preparing is
 * what `npm run bishnoi-<app> -- --setup` does for each (.env files, the APIs'
 * .venv, the screens' node_modules); quick when nothing changed.
 */
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const WINDOWS = process.platform === "win32";
const COLOR = process.stdout.isTTY && !process.env.NO_COLOR;
const paint = (code, text) => (COLOR ? `\x1b[${code}m${text}\x1b[0m` : text);

// The APIs behind the one app, and the one app's screens. Platform first: the others ask it.
const PARTS = [
  { label: "platform", color: "33", app: "bishnoi-platform", dir: "backend", cmd: "uv", args: ["run", "main.py"], port: 8305 },
  { label: "crm", color: "34", app: "bishnoi-crm", dir: "backend", cmd: "uv", args: ["run", "main.py"], port: 8302 },
  { label: "inventory", color: "32", app: "bishnoi-inventory", dir: "backend", cmd: "uv", args: ["run", "main.py"], port: 8304 },
  { label: "finance", color: "36", app: "bishnoi-finance", dir: "backend", cmd: "uv", args: ["run", "main.py"], port: 8303 },
  { label: "admin", color: "35", app: "bishnoi-admin", dir: "backend", cmd: "uv", args: ["run", "main.py"], port: 8300 },
  { label: "pharmacy", color: "31", app: "bishnoi-pharmacy", dir: "backend", cmd: "uv", args: ["run", "main.py"], port: 8307 },
  { label: "one", color: "1", app: "bishnoi-one-app", dir: "frontend", cmd: "npm", args: ["run", "dev"], port: 4301 },
];

const setupOnly = process.argv.includes("--setup");
const line = (command, args) => (WINDOWS ? [[command, ...args].join(" "), []] : [command, args]);

// ---- Get ready -----------------------------------------------------------------------------
for (const app of [...new Set(PARTS.map((p) => p.app))]) {
  const part = PARTS.find((p) => p.app === app);
  const flag = part.dir === "backend" ? "--api" : "--web";
  console.log(paint("36", `→ Preparing ${app}`));
  const r = spawnSync(process.execPath, [join(ROOT, "scripts", "run-app.mjs"), app, "--setup", flag], { cwd: ROOT, stdio: "inherit" });
  if (r.status !== 0) {
    console.error(paint("31", `✗ ${app} couldn't be prepared (see above).`));
    process.exit(r.status ?? 1);
  }
}
if (setupOnly) {
  console.log(paint("32", "✓ Ready. Run it with: npm run one"));
  process.exit(0);
}

// ---- Run -----------------------------------------------------------------------------------
console.log(paint("32", "\n  Bishnoi One: http://localhost:4301   (sign in with your Bishnoi One account)"));
console.log(paint("2", `  APIs: ${PARTS.filter((p) => p.dir === "backend").map((p) => `${p.label} ${p.port}`).join(", ")}`));
console.log(paint("2", "  Ctrl+C stops everything.\n"));

const children = [];
let stopping = false;
function stopAll(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (child.exitCode !== null) continue;
    if (WINDOWS) spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    else {
      try {
        process.kill(-child.pid, "SIGTERM");
      } catch {
        /* already gone */
      }
    }
  }
  setTimeout(() => process.exit(code), 300);
}
process.on("SIGINT", () => stopAll(0));
process.on("SIGTERM", () => stopAll(0));

/** Whether a part's API answers its /health yet. */
async function answers(port) {
  try {
    const r = await fetch(`http://127.0.0.1:${port}/health`, { signal: AbortSignal.timeout(2000) });
    return r.ok;
  } catch {
    return false;
  }
}

// The Platform first, and only then the rest (2026-10-26): every module asks it for its links the
// moment it starts, so it must already be answering, or they each log "can't reach the platform".
let platformWaited = false;
for (const part of PARTS) {
  if (platformWaited === false && part.label !== "platform" && PARTS.some((p) => p.label === "platform")) {
    platformWaited = true;
    const until = Date.now() + 90_000;
    while (!stopping && Date.now() < until && !(await answers(8305))) await new Promise((r) => setTimeout(r, 1000));
    console.log(paint("2", (await answers(8305)) ? "  Platform is answering: starting the rest." : "  Platform isn't answering yet: starting the rest anyway."));
  }
  const cwd = join(ROOT, part.app, part.dir);
  if (!existsSync(cwd)) {
    console.log(paint("33", `! ${part.app}/${part.dir} isn't here: skipped.`));
    continue;
  }
  const env = { ...process.env, FORCE_COLOR: COLOR ? "1" : "0" };
  delete env.ELECTRON_RUN_AS_NODE;
  const child = spawn(...line(part.cmd, part.args), { cwd, shell: WINDOWS, detached: !WINDOWS, env });
  const tag = paint(part.color, `[${part.label}]`);
  for (const stream of [child.stdout, child.stderr]) {
    let rest = "";
    stream.on("data", (chunk) => {
      const lines = (rest + chunk.toString()).split(/\r?\n/);
      rest = lines.pop();
      for (const l of lines) process.stdout.write(`${tag} ${l}\n`);
    });
    stream.on("end", () => rest && process.stdout.write(`${tag} ${rest}\n`));
  }
  child.on("exit", (code) => {
    if (stopping) return;
    console.log(paint(code ? "31" : "2", `${tag} stopped${code ? ` (exit ${code})` : ""}; stopping the rest.`));
    stopAll(code ?? 0);
  });
  children.push(child);
}
