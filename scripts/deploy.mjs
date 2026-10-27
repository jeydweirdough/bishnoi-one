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
 *
 * Every Vercel project builds from its folder (its Root Directory, e.g.
 * bishnoi-crm/backend), so each is sent from the repository's top. What's sent
 * is only that app's folder: for the run, the top .vercelignore is written for
 * that app (every other app, documents and tools left out, and never settings,
 * local databases or installed packages), then put back as it was. The CLI
 * doesn't read .gitignore, so this is what keeps secrets off Vercel.
 *
 * Deploy the Platform first, then the APIs, then the one app.
 * "What to redeploy" (GitHub Actions) says which apps have changes waiting.
 */

import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const IGNORE = join(ROOT, ".vercelignore");

// name: [its folder (the Vercel project's Root Directory), its Vercel project]
// Executive Admin, Pharmacy, In-Licensing and Regulatory have no Vercel project yet.
const APPS = {
  platform: ["bishnoi-platform/backend", "bishnoione-platform-backend"],
  crm: ["bishnoi-crm/backend", "bishnoione-crm-backend"],
  inventory: ["bishnoi-inventory/backend", "bishnoione-inventory-backend"],
  finance: ["bishnoi-finance/backend", "bishnoione-finance-backend"],
  "one-app": ["bishnoi-one-app/frontend", "bishnoi-one-app"],
};

// Never sent, wherever they are.
const NEVER = [
  ".env", ".env.*", "!.env.example", "**/.env", "**/.env.*", "!**/.env.example",
  "**/.data", "**/*.db", "**/*.db-*", "**/.venv", "**/__pycache__", "**/.pytest_cache", "**/.ruff_cache",
  "**/node_modules", "**/.next", "**/tests",
];

/** The upload filter for one app: everything at the top but its folder, and never the secrets. */
function filterFor(folder) {
  const [top, inside] = folder.split("/");
  const others = readdirSync(ROOT).filter((n) => n !== top && n !== ".vercelignore").map((n) => `/${n}`);
  const siblings = readdirSync(join(ROOT, top)).filter((n) => n !== inside).map((n) => `/${top}/${n}`);
  return [
    `# Written by scripts/deploy.mjs for ${folder}, and put back afterwards.`,
    ...others, ...siblings, ...NEVER, "",
  ].join("\n");
}

const windows = process.platform === "win32";

function vercel(args) {
  const r = spawnSync("vercel", args, { cwd: ROOT, shell: windows, encoding: "utf8", stdio: ["inherit", "pipe", "pipe"] });
  process.stdout.write(r.stdout ?? "");
  process.stderr.write(r.stderr ?? "");
  const text = [r.stdout ?? "", r.stderr ?? ""].join("\n");
  // Not installed: Node says ENOENT, or (through the Windows shell) the shell says it isn't recognised.
  const missing = r.error?.code === "ENOENT" || (r.status !== 0 && /not recognized|command not found/i.test(text));
  return { ok: r.status === 0, text, missing };
}

function deploy(name) {
  const [folder, project] = APPS[name];
  console.log(`\nLinking to ${project}…`);
  if (!vercel(["link", "--yes", "--project", project]).ok) return false;
  const kept = existsSync(IGNORE) ? readFileSync(IGNORE, "utf8") : null;
  writeFileSync(IGNORE, filterFor(folder));
  try {
    console.log(`\nDeploying ${name} (${folder} -> ${project})…`);
    return vercel(["deploy", "--prod", "--yes"]).ok;
  } finally {
    if (kept === null) writeFileSync(IGNORE, "");
    else writeFileSync(IGNORE, kept);
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
  console.error(`Not an app on Vercel: ${unknown.join(", ")}. One of: ${Object.keys(APPS).join(", ")}.`);
  process.exit(1);
}
if (vercel(["--version"]).missing) {
  console.error("The Vercel CLI isn't installed: npm install --global vercel, then vercel login.");
  process.exit(1);
}
const failed = [];
for (const name of asked) if (!deploy(name)) failed.push(name);
console.log(failed.length ? `\nNot deployed: ${failed.join(", ")} (see above).` : `\nDeployed: ${asked.join(", ")}.`);
process.exit(failed.length ? 1 : 0);
