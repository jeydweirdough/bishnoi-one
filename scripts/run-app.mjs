#!/usr/bin/env node
/**
 * Runs one Nabhi app, API and screens together: `npm run nabhi-crm`.
 *
 * Before starting, it gets the app ready, doing only what's missing:
 *   - backend/.env and frontend/.env.local, copied from their examples;
 *   - the API's Python environment, backend/.venv (`uv sync`);
 *   - the screens' packages, frontend/node_modules (`npm install`).
 *
 * Then it starts `uv run main.py` and `npm run dev`, with each line marked
 * [api] or [web]. Ctrl+C stops both; if one stops, the other is stopped too.
 *
 *   npm run nabhi-crm              both
 *   npm run nabhi-crm -- --api     the API only
 *   npm run nabhi-crm -- --web     the screens only
 *   npm run nabhi-crm -- --setup   get it ready, start nothing
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

const apps = readdirSync(ROOT).filter((name) => name.startsWith("nabhi-") && existsSync(join(ROOT, name, "backend")));

function fail(message) {
  console.error(paint("31", `✗ ${message}`));
  process.exit(1);
}

const [asked, ...flags] = process.argv.slice(2);
const app = asked && (apps.includes(asked) ? asked : apps.includes(`nabhi-${asked}`) ? `nabhi-${asked}` : null);
if (!app) fail(`Which app? ${asked ? `"${asked}" isn't one. ` : ""}One of: ${apps.join(", ")}`);

const only = { api: flags.includes("--api"), web: flags.includes("--web") };
const setupOnly = flags.includes("--setup");
const backend = join(ROOT, app, "backend");
const frontend = join(ROOT, app, "frontend");
const frontendPackage = join(frontend, "package.json");
const devScript = existsSync(frontendPackage) ? JSON.parse(readFileSync(frontendPackage, "utf8")).scripts?.dev : undefined;
const runApi = !only.web;
const runWeb = !only.api && Boolean(devScript);

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
  const installed = join(frontend, "node_modules", ".package-lock.json");
  if (!existsSync(installed) || newer(join(frontend, "package-lock.json"), installed) || newer(frontendPackage, installed)) {
    step("Installing the screens' packages (npm install)", "npm", ["install"], frontend);
    // npm leaves this file alone when nothing changed: mark it, so the next start skips the install.
    if (existsSync(installed)) utimesSync(installed, new Date(), new Date());
  }
}

if (setupOnly) {
  console.log(paint("32", `✓ ${app} is ready. Run it with: npm run ${app}`));
  process.exit(0);
}

// ---- Run ----

if (!devScript && !only.api) console.log(paint("33", `! ${app} has no screens yet: running its API only.`));
const webPort = devScript?.match(/--port\s+(\d+)/)?.[1];
const mainPy = join(backend, "main.py");
const apiPort = existsSync(mainPy) ? readFileSync(mainPy, "utf8").match(/"--port",[^)]*default=(\d+)/)?.[1] : undefined;
if (runWeb && webPort) console.log(paint("32", `  Screens: http://localhost:${webPort}`));
if (runApi && apiPort) console.log(paint("32", `  API:     http://127.0.0.1:${apiPort}  (docs at /docs)`));
console.log(paint("2", "  Ctrl+C stops both.\n"));

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

function start(label, color, command, args, cwd) {
  const child = spawn(...line(command, args), { cwd, shell: WINDOWS, detached: !WINDOWS, env: { ...process.env, FORCE_COLOR: COLOR ? "1" : "0" } });
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
    console.log(paint(code ? "31" : "2", `${tag} stopped${code ? ` (exit ${code})` : ""}; stopping the rest.`));
    stopAll(code ?? 0);
  });
  children.push(child);
}

if (runApi) start("api", "35", "uv", ["run", "main.py"], backend);
if (runWeb) start("web", "34", "npm", ["run", "dev"], frontend);
if (!children.length) fail("Nothing to run.");

process.on("SIGINT", () => stopAll(0));
process.on("SIGTERM", () => stopAll(0));
