#!/usr/bin/env node
/**
 * Runs one Bishnoi One app, API and screens together: `npm run bishnoi-crm`.
 *
 * Before starting, it gets the app ready, doing only what's missing:
 *   - backend/.env and frontend/.env.local, copied from their examples;
 *   - the API's Python environment, backend/.venv (`uv sync`);
 *   - the screens' packages, frontend/node_modules (`npm install`).
 *
 * Then it starts `uv run main.py` and `npm run dev`, with each line marked
 * [api] or [web]. Ctrl+C stops both; if one stops, the other is stopped too.
 *
 *   npm run bishnoi-crm              both
 *   npm run bishnoi-crm -- --api     the API only
 *   npm run bishnoi-crm -- --web     the screens only
 *   npm run bishnoi-crm -- --setup   get it ready, start nothing
 *   npm run bishnoi-crm:app          both, in a window of its own (--app)
 *
 * With --app the screens open as a desktop app (desktop/main.mjs), marked
 * [app]. Its packages, desktop/node_modules, are installed the first time.
 * Closing the window stops the app.
 *
 * Needs uv (https://docs.astral.sh/uv/) and Node.js. No packages of its own.
 */

import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, existsSync, readdirSync, readFileSync, statSync, utimesSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const WINDOWS = process.platform === "win32";
const COLOR = process.stdout.isTTY && !process.env.NO_COLOR;
const paint = (code, text) => (COLOR ? `\x1b[${code}m${text}\x1b[0m` : text);

const apps = readdirSync(ROOT).filter((name) => name.startsWith("bishnoi-") && existsSync(join(ROOT, name, "backend")));

function fail(message) {
  console.error(paint("31", `✗ ${message}`));
  process.exit(1);
}

const [asked, ...flags] = process.argv.slice(2);
const app = asked && (apps.includes(asked) ? asked : apps.includes(`bishnoi-${asked}`) ? `bishnoi-${asked}` : null);
if (!app) fail(`Which app? ${asked ? `"${asked}" isn't one. ` : ""}One of: ${apps.join(", ")}`);

const only = { api: flags.includes("--api"), web: flags.includes("--web") };
const setupOnly = flags.includes("--setup");
const asApp = flags.includes("--app");
const backend = join(ROOT, app, "backend");
const frontend = join(ROOT, app, "frontend");
const frontendPackage = join(frontend, "package.json");
const devScript = existsSync(frontendPackage) ? JSON.parse(readFileSync(frontendPackage, "utf8")).scripts?.dev : undefined;
const runApi = !only.web;
const runWeb = !only.api && Boolean(devScript);
const desktop = join(ROOT, "desktop");
if (asApp && !devScript) fail(`${app} has no screens yet, so there is no window to open. Its API runs with: npm run ${app}`);
if (asApp && only.api) fail("--app opens the screens in a window, so it can't go with --api.");

// On Windows, npm is npm.cmd and needs a shell. The commands here are fixed
// words, so they're handed over as one line (Node warns about args + shell).
const line = (command, args) => (WINDOWS ? [[command, ...args].join(" "), []] : [command, args]);

function has(command) {
  return spawnSync(...line(command, ["--version"]), { shell: WINDOWS, stdio: "ignore" }).status === 0;
}

function step(what, command, args, cwd) {
  console.log(paint("36", `→ ${what}`));
  const result = spawnSync(...line(command, args), { cwd, stdio: "inherit", shell: WINDOWS });
  if (result.status !== 0) fail(`${what} failed. Fix the error above, then run it again.`);
}

function copyExample(dir, example, target) {
  const from = join(dir, example);
  const to = join(dir, target);
  if (!existsSync(to) && existsSync(from)) {
    copyFileSync(from, to);
    console.log(paint("36", `→ Made ${app}/${dir === backend ? "backend" : "frontend"}/${target} from ${example}`));
  }
}

const newer = (a, b) => existsSync(a) && (!existsSync(b) || statSync(a).mtimeMs > statSync(b).mtimeMs);

// npm install, when a folder's packages are missing or older than what it asks for.
function packages(dir, what) {
  const installed = join(dir, "node_modules", ".package-lock.json");
  if (existsSync(installed) && !newer(join(dir, "package-lock.json"), installed) && !newer(join(dir, "package.json"), installed)) return;
  step(what, "npm", ["install"], dir);
  // npm leaves this file alone when nothing changed: mark it, so the next start skips the install.
  if (existsSync(installed)) utimesSync(installed, new Date(), new Date());
}

// ---- Get ready ----

console.log(paint("1", `\n${app}`));

if (runApi || setupOnly) {
  if (!has("uv")) fail("uv isn't installed. Get it from https://docs.astral.sh/uv/, then run this again.");
  copyExample(backend, ".env.example", ".env");
  // uv sync makes backend/.venv, or brings it up to date with uv.lock. It's quick when nothing changed.
  step(existsSync(join(backend, ".venv")) ? "Checking the API's Python environment (.venv)" : "Making the API's Python environment (.venv)", "uv", ["sync"], backend);
}

if (runWeb || (setupOnly && devScript)) {
  copyExample(frontend, ".env.example", ".env.local");
  packages(frontend, "Installing the screens' packages (npm install)");
}

if (asApp) packages(desktop, "Installing the desktop window's packages (npm install)");

if (setupOnly) {
  console.log(paint("32", `✓ ${app} is ready. Run it with: npm run ${app}${asApp ? ":app" : ""}`));
  process.exit(0);
}

// ---- Run ----

if (!devScript && !only.api) console.log(paint("33", `! ${app} has no screens yet: running its API only.`));
const webPort = devScript?.match(/--port\s+(\d+)/)?.[1];
const mainPy = join(backend, "main.py");
const apiPort = existsSync(mainPy) ? readFileSync(mainPy, "utf8").match(/"--port",[^)]*default=(\d+)/)?.[1] : undefined;
if (runWeb && webPort) console.log(paint("32", `  Screens: http://localhost:${webPort}`));
if (runApi && apiPort) console.log(paint("32", `  API:     http://127.0.0.1:${apiPort}  (docs at /docs)`));
if (asApp) console.log(paint("32", "  Window:  opens by itself once the screens are ready"));
console.log(paint("2", asApp ? "  Closing the window, or Ctrl+C here, stops everything.\n" : "  Ctrl+C stops both.\n"));

const children = [];
let stopping = false;

function stopAll(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (child.exitCode !== null) continue;
    // The dev servers start children of their own: stop the whole tree.
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

// direct: a program run as it is, with no shell between (its arguments may hold spaces).
function start(label, color, command, args, cwd, direct = false) {
  const env = { ...process.env, FORCE_COLOR: COLOR ? "1" : "0" };
  // Set by some editors' terminals: with it, the desktop window would start as plain Node and open nothing.
  delete env.ELECTRON_RUN_AS_NODE;
  const child = spawn(...(direct ? [command, args] : line(command, args)), { cwd, shell: WINDOWS && !direct, detached: !WINDOWS, env });
  const tag = paint(color, `[${label}]`);
  for (const stream of [child.stdout, child.stderr]) {
    let rest = "";
    stream.on("data", (chunk) => {
      const lines = (rest + chunk.toString()).split(/\r?\n/);
      rest = lines.pop();
      for (const line of lines) process.stdout.write(`${tag} ${line}\n`);
    });
    stream.on("end", () => rest && process.stdout.write(`${tag} ${rest}\n`));
  }
  child.on("exit", (code) => {
    if (stopping) return;
    console.log(paint(code ? "31" : "2", `${tag} ${label === "app" && !code ? "closed" : "stopped"}${code ? ` (exit ${code})` : ""}; stopping the rest.`));
    stopAll(code ?? 0);
  });
  children.push(child);
}

if (runApi) start("api", "35", "uv", ["run", "main.py"], backend);
if (runWeb) start("web", "34", "npm", ["run", "dev"], frontend);
if (asApp) start("app", "33", process.execPath, [join(desktop, "node_modules", "electron", "cli.js"), desktop, `--bishnoi-app=${app}`], ROOT, true);
if (!children.length) fail("Nothing to run.");

// The terminal tab is named after the app. Next.js renames its process to
// "next-server (vX)", which on Windows renames the shared console too, so the
// name is put back every few seconds.
function nameTheTab() {
  process.title = app;
  if (process.stdout.isTTY && !WINDOWS) process.stdout.write(`\x1b]0;${app}\x07`);
}
nameTheTab();
if (process.stdout.isTTY) setInterval(nameTheTab, 2000).unref();

process.on("SIGINT", () => stopAll(0));
process.on("SIGTERM", () => stopAll(0));
