#!/usr/bin/env node
/**
 * Gets Bishnoi One ready to run on this computer, without starting anything: `npm run setup`.
 * Does only what's missing:
 *
 *   - backend/.env from backend/.env.example, and the backend's Python environment
 *     (backend/.venv, `uv sync`): the one backend, every module's API;
 *   - bishnoi-one-app/frontend/.env.local from its .env.example, and its packages
 *     (`npm install`): the one app, every module's screens.
 *
 * scripts/run-one.mjs calls the same steps before it starts anything.
 * Needs uv (https://docs.astral.sh/uv/) and Node.js. No packages of its own.
 */

import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, statSync, utimesSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const BACKEND = join(ROOT, "backend");
export const FRONTEND = join(ROOT, "bishnoi-one-app", "frontend");
export const DESKTOP = join(ROOT, "desktop");
export const WINDOWS = process.platform === "win32";
const COLOR = process.stdout.isTTY && !process.env.NO_COLOR;
export const paint = (code, text) => (COLOR ? `\x1b[${code}m${text}\x1b[0m` : text);

// On Windows, npm is npm.cmd and needs a shell. The commands here are fixed words,
// so they're handed over as one line (Node warns about args + shell).
export const line = (command, args) => (WINDOWS ? [[command, ...args].join(" "), []] : [command, args]);

export function fail(message) {
  console.error(paint("31", `✗ ${message}`));
  process.exit(1);
}

const has = (command) => spawnSync(...line(command, ["--version"]), { shell: WINDOWS, stdio: "ignore" }).status === 0;

function step(what, command, args, cwd) {
  console.log(paint("36", `→ ${what}`));
  const result = spawnSync(...line(command, args), { cwd, stdio: "inherit", shell: WINDOWS });
  if (result.status !== 0) fail(`${what} failed. Fix the error above, then run it again.`);
}

function copyExample(dir, example, target, label) {
  const from = join(dir, example);
  const to = join(dir, target);
  if (!existsSync(to) && existsSync(from)) {
    copyFileSync(from, to);
    console.log(paint("36", `→ Made ${label}/${target} from ${example}`));
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

/** Prepares the parts asked for: { backend, web, desktop }. */
export function prepare({ backend = true, web = true, desktop = false } = {}) {
  if (backend) {
    if (!has("uv")) fail("uv isn't installed. Get it from https://docs.astral.sh/uv/, then run this again.");
    copyExample(BACKEND, ".env.example", ".env", "backend");
    // uv sync makes backend/.venv, or brings it up to date with uv.lock. Quick when nothing changed.
    step(existsSync(join(BACKEND, ".venv")) ? "Checking the backend's Python environment (.venv)" : "Making the backend's Python environment (.venv)", "uv", ["sync"], BACKEND);
  }
  if (web) {
    copyExample(FRONTEND, ".env.example", ".env.local", "bishnoi-one-app/frontend");
    packages(FRONTEND, "Installing the one app's packages (npm install)");
  }
  if (desktop) packages(DESKTOP, "Installing the desktop window's packages (npm install)");
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  prepare({ backend: true, web: true });
  console.log(paint("32", "\n✓ Ready. Run it with: npm run one"));
}
