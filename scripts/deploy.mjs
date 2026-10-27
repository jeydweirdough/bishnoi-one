#!/usr/bin/env node
/**
 * Deploys one app to Vercel production, by hand (decided 2026-10-27): pushing
 * deploys nothing, so only what you name is built.
 *
 *   npm run deploy -- crm              the CRM API
 *   npm run deploy -- one-app          the one app (every module's screens)
 *   npm run deploy -- platform crm     several, in the order given
 *   npm run deploy                     lists the apps
 *
 * Needs the Vercel CLI, once: npm install --global vercel, then vercel login.
 * The first time an app is deployed it's linked to its Vercel project (saved in
 * a .vercel folder, which git ignores). Each is deployed from where its Vercel
 * project expects it: the one app from the repository's top (its project's Root
 * Directory is bishnoi-one-app/frontend), each API from its own folder. What's
 * uploaded is filtered by the .vercelignore there: never settings or local data.
 *
 * Deploy the Platform first, then the APIs, then the one app.
 * "What to redeploy" (GitHub Actions) says which apps have changes waiting.
 */

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

// name: [its folder, its Vercel project, where it's deployed from]
const APPS = {
  platform: ["bishnoi-platform/backend", "bishnoione-platform-backend", "bishnoi-platform/backend"],
  crm: ["bishnoi-crm/backend", "bishnoione-crm-backend", "bishnoi-crm/backend"],
  inventory: ["bishnoi-inventory/backend", "bishnoione-inventory-backend", "bishnoi-inventory/backend"],
  finance: ["bishnoi-finance/backend", "bishnoione-finance-backend", "bishnoi-finance/backend"],
  admin: ["bishnoi-admin/backend", "bishnoi-one-admin-backend", "bishnoi-admin/backend"],
  // Its project's Root Directory is bishnoi-one-app/frontend: from the top (the root .vercelignore keeps the rest out).
  "one-app": ["bishnoi-one-app/frontend", "bishnoi-one-app", "."],
};

const windows = process.platform === "win32";

function vercel(args, cwd) {
  const r = spawnSync("vercel", args, { cwd, shell: windows, encoding: "utf8", stdio: ["inherit", "pipe", "pipe"] });
  process.stdout.write(r.stdout ?? "");
  process.stderr.write(r.stderr ?? "");
  const text = [r.stdout ?? "", r.stderr ?? ""].join("\n");
  // Not installed: Node says ENOENT, or (through the Windows shell) the shell says it isn't recognised.
  const missing = r.error?.code === "ENOENT" || (r.status !== 0 && /not recognized|command not found/i.test(text));
  return { ok: r.status === 0, text, missing };
}

function deploy(name) {
  const [, project, from] = APPS[name];
  const where = join(ROOT, from);
  if (!existsSync(join(where, ".vercel", "project.json")) || !linkedTo(where, project)) {
    console.log(`\nLinking ${where} to ${project}…`);
    if (!vercel(["link", "--yes", "--project", project], where).ok) return false;
  }
  console.log(`\nDeploying ${name} (${project}) from ${where}…`);
  return vercel(["deploy", "--prod", "--yes"], where).ok;
}

function linkedTo(where, project) {
  try {
    return JSON.parse(readFileSync(join(where, ".vercel", "project.json"), "utf8")).projectName === project;
  } catch {
    return false;
  }
}

const asked = process.argv.slice(2);
if (!asked.length) {
  console.log("Deploys apps to Vercel production: npm run deploy -- <app> [<app>…]\n");
  for (const [name, [folder, project]] of Object.entries(APPS)) console.log(`  ${name.padEnd(10)} ${folder.padEnd(28)} ${project}`);
  console.log("\nDeploy the Platform first, then the APIs, then the one app.");
  process.exit(0);
}
const unknown = asked.filter((a) => !APPS[a]);
if (unknown.length) {
  console.error(`Not an app: ${unknown.join(", ")}. One of: ${Object.keys(APPS).join(", ")}.`);
  process.exit(1);
}
if (vercel(["--version"], ROOT).missing) {
  console.error("The Vercel CLI isn't installed: npm install --global vercel, then vercel login.");
  process.exit(1);
}
const failed = [];
for (const name of asked) if (!deploy(name)) failed.push(name);
console.log(failed.length ? `\nNot deployed: ${failed.join(", ")} (see above).` : `\nDeployed: ${asked.join(", ")}.`);
process.exit(failed.length ? 1 : 0);
