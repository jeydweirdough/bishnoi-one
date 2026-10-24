#!/usr/bin/env node
/**
 * Gets every Bishnoi One app ready to run, without starting any: `npm run setup`.
 * For each: its .env files, its API's .venv (uv sync) and its screens'
 * node_modules (npm install), doing only what's missing.
 */

import { spawnSync } from "node:child_process";
import { existsSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const apps = readdirSync(ROOT).filter((name) => name.startsWith("bishnoi-") && (existsSync(join(ROOT, name, "backend")) || existsSync(join(ROOT, name, "frontend"))));
const failed = [];

for (const app of apps) {
  const result = spawnSync(process.execPath, [join(ROOT, "scripts", "run-app.mjs"), app, "--setup"], { stdio: "inherit" });
  if (result.status !== 0) failed.push(app);
}

if (failed.length) {
  console.error(`\n✗ Not ready: ${failed.join(", ")}. See the errors above.`);
  process.exit(1);
}
console.log(`\n✓ All ${apps.length} apps are ready. Run one with: npm run <app>, e.g. npm run bishnoi-crm`);
