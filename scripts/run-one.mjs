#!/usr/bin/env node
/**
 * Bishnoi One on this computer, in one go: the one backend (every module's API, port 8300)
 * and the one app (every module's screens, http://localhost:4301).
 *
 *   npm run one                  # prepare what's missing, then run both; Ctrl+C stops both
 *   npm run one -- --setup       # prepare only (npm run setup)
 *   npm run backend              # the backend only   (= npm run one -- --backend)
 *   npm run bishnoi-one-app      # the screens only   (= npm run one -- --web)
 *   npm run bishnoi-one-app:app  # both, the screens in a desktop window (desktop/main.mjs)
 *
 * Each line is marked [backend], [one] or [app]. If one part stops, the others are stopped too.
 * The backend starts first and the screens once it answers /health.
 */

import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { BACKEND, DESKTOP, FRONTEND, ROOT, WINDOWS, fail, line, paint, prepare } from "./setup-all.mjs";

const flags = process.argv.slice(2);
const setupOnly = flags.includes("--setup");
const asApp = flags.includes("--app");
const runBackend = !flags.includes("--web") || asApp;
const runWeb = !flags.includes("--backend");
if (!runBackend && !runWeb) fail("--backend and --web together leave nothing to run.");

// The backend's port, from backend/main.py (--port's default), the one place it's written.
const BACKEND_PORT = Number(readFileSync(join(BACKEND, "main.py"), "utf8").match(/"--port",[^)]*default=(\d+)/)?.[1] ?? 8300);
const WEB_PORT = Number(JSON.parse(readFileSync(join(FRONTEND, "package.json"), "utf8")).scripts?.dev?.match(/--port\s+(\d+)/)?.[1] ?? 4301);

// ---- Get ready -------------------------------------------------------------------------------
prepare({ backend: runBackend, web: runWeb, desktop: asApp });
if (setupOnly) {
  console.log(paint("32", "✓ Ready. Run it with: npm run one"));
  process.exit(0);
}

// ---- Run -------------------------------------------------------------------------------------
if (runWeb) console.log(paint("32", `\n  Bishnoi One: http://localhost:${WEB_PORT}   (sign in with your Bishnoi One account)`));
if (runBackend) console.log(paint("2", `  Backend:     http://127.0.0.1:${BACKEND_PORT}  (/health; each module under its path, docs at /<module>/docs)`));
console.log(paint("2", "  Ctrl+C stops everything.\n"));

const children = [];
let stopping = false;

function stopAll(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (child.exitCode !== null) continue;
    // uvicorn's reloader and Next start children of their own: stop the whole tree.
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

// direct: a program run as it is, with no shell between (its arguments may hold spaces).
function start(label, color, command, args, cwd, direct = false) {
  const env = { ...process.env, FORCE_COLOR: process.stdout.isTTY && !process.env.NO_COLOR ? "1" : "0" };
  // Set by some editors' terminals: with it, the desktop window would start as plain Node and open nothing.
  delete env.ELECTRON_RUN_AS_NODE;
  const child = spawn(...(direct ? [command, args] : line(command, args)), { cwd, shell: WINDOWS && !direct, detached: !WINDOWS, env });
  const tag = paint(color, `[${label}]`);
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
    console.log(paint(code ? "31" : "2", `${tag} ${label === "app" && !code ? "closed" : "stopped"}${code ? ` (exit ${code})` : ""}; stopping the rest.`));
    stopAll(code ?? 0);
  });
  children.push(child);
}

/** Whether the backend answers /health yet. */
async function backendAnswers() {
  try {
    return (await fetch(`http://127.0.0.1:${BACKEND_PORT}/health`, { signal: AbortSignal.timeout(2000) })).ok;
  } catch {
    return false;
  }
}

if (runBackend) start("backend", "35", "uv", ["run", "main.py"], BACKEND);
if (runBackend && runWeb) {
  // The screens ask the backend for every page: start them once it answers (its modules run their migrations first).
  const until = Date.now() + 120_000;
  while (!stopping && Date.now() < until && !(await backendAnswers())) await new Promise((r) => setTimeout(r, 1000));
  if (!stopping) console.log(paint("2", (await backendAnswers()) ? "  The backend is answering: starting the screens." : "  The backend isn't answering yet: starting the screens anyway."));
}
if (runWeb && !stopping) start("one", "34", "npm", ["run", "dev"], FRONTEND);
if (asApp && !stopping) {
  const electron = join(DESKTOP, "node_modules", "electron", "cli.js");
  if (!existsSync(electron)) fail("The desktop window's packages are missing: run npm install in desktop/.");
  start("app", "33", process.execPath, [electron, DESKTOP, "--bishnoi-app=bishnoi-one-app"], ROOT, true);
}

process.title = "bishnoi-one";
