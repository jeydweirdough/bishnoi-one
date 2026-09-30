#!/usr/bin/env node
// Issues a company's license file (.nabhi) and its two IDs.
//
//   npm run license -- issue          a new company: Company ID, activation key, file
//   npm run license -- renew <file>   a new file with the same IDs: new passwords, or a new expiry
//   npm run license -- check <file>   what's inside, passwords hidden
//   add --local to type "local" for an app's database: it then uses its own
//   backend/.env, for trying the apps as desktop apps on this PC
//
// Passwords and the activation key are typed in, never passed on the command
// line (it's kept in shell history) and never written anywhere but the
// encrypted file. Files go to desktop/issued/, which git ignores.

import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createInterface } from "node:readline";
import {
  LicenseError,
  checkCompanyId,
  checkDatabaseUrl,
  companyIdFrom,
  maskUrl,
  newActivationKey,
  newPassword,
  normalizeKey,
  open,
  readHeader,
  seal,
} from "../license/file.mjs";

const OUT = process.env.NABHI_ISSUED_DIR || join(dirname(fileURLToPath(import.meta.url)), "..", "issued");
const ALLOW_POSTGRES = process.argv.includes("--allow-postgres");
// For trying the apps on a developer's PC: "local" is the app's own backend/.env database.
const ALLOW_LOCAL = process.argv.includes("--local");

// --- asking -------------------------------------------------------------------------------

const lines = [];
let waiting = null;
const rl = createInterface({ input: process.stdin, terminal: false });
rl.on("line", (l) => (waiting ? (waiting(l), (waiting = null)) : lines.push(l)));
rl.on("close", () => waiting && (waiting(null), (waiting = null)));

function readLine() {
  return lines.length ? Promise.resolve(lines.shift()) : new Promise((r) => (waiting = r));
}

async function ask(question, fallback = "") {
  process.stdout.write(`${question}${fallback ? ` [${fallback}]` : ""}: `);
  const answer = await readLine();
  if (answer === null) throw new LicenseError("Stopped before all the answers were given.");
  return answer.trim() || fallback;
}

/** Typed without showing it on screen (on a terminal). */
async function askHidden(question) {
  if (!process.stdin.isTTY) return ask(question);
  process.stdout.write(`${question} (hidden): `);
  rl.pause();
  const stdin = process.stdin;
  stdin.setRawMode(true);
  stdin.resume();
  return new Promise((resolveAnswer, reject) => {
    let typed = "";
    const onData = (chunk) => {
      for (const ch of chunk.toString("utf8")) {
        if (ch === "\r" || ch === "\n") {
          stdin.setRawMode(false);
          stdin.off("data", onData);
          process.stdout.write("\n");
          rl.resume();
          return resolveAnswer(typed.trim());
        }
        if (ch === "\u0003") {
          stdin.setRawMode(false);
          return reject(new LicenseError("Stopped."));
        }
        if (ch === "\u007f" || ch === "\b") typed = typed.slice(0, -1);
        else typed += ch;
      }
    };
    stdin.on("data", onData);
  });
}

async function askDatabases(apps, current = {}) {
  const databases = { ...current };
  for (const app of apps) {
    for (;;) {
      const keep = current[app] ? " (Enter keeps the current one)" : "";
      const url = await askHidden(`Database connection for ${app}${keep}${ALLOW_LOCAL ? ', or "local"' : ""}`);
      if (!url && current[app]) break;
      if (ALLOW_LOCAL && url.toLowerCase() === "local") {
        databases[app] = "local";
        console.log("  local: the app's own backend/.env database");
        break;
      }
      try {
        databases[app] = checkDatabaseUrl(url, { allowPostgres: ALLOW_POSTGRES });
        console.log(`  ${maskUrl(databases[app])}`);
        if (!/:6543\//.test(databases[app])) console.log("  Note: Supabase's pooler (port 6543) is the one to use for many PCs at once.");
        break;
      } catch (e) {
        console.log(`  ${e.message}`);
      }
    }
  }
  return databases;
}

async function askSupabase(current) {
  const url = await ask("Supabase project URL, for live updates (optional)", current?.url ?? "");
  if (!url) return undefined;
  if (!/^https:\/\/[a-z0-9-]+\.supabase\.co\/?$/.test(url)) throw new LicenseError("A Supabase project URL looks like https://abcd1234.supabase.co");
  const anonKey = (await askHidden(`Supabase anon key${current?.anonKey ? " (Enter keeps the current one)" : ""}`)) || current?.anonKey || "";
  return { url: url.replace(/\/$/, ""), anonKey };
}

function write(companyId, text) {
  mkdirSync(OUT, { recursive: true });
  const file = join(OUT, `${companyId}.nabhi`);
  writeFileSync(file, text, "utf8");
  return file;
}

// --- the commands ---------------------------------------------------------------------------

async function issue() {
  const name = await ask("Company name");
  const companyId = checkCompanyId(await ask("Company ID", companyIdFrom(name)));
  if (existsSync(join(OUT, `${companyId}.nabhi`))) {
    throw new LicenseError(`${companyId} was issued already. Use "renew" to give it a new file with the same IDs.`);
  }
  const apps = (await ask("Apps, separated by commas (admin, crm, finance, inventory, pharmacy)", "crm,inventory"))
    .split(",")
    .map((a) => a.trim().toLowerCase())
    .filter(Boolean);
  const databases = await askDatabases(apps);
  const supabase = await askSupabase();
  // The company's first administrator: made on the first start, only while the
  // database has no accounts yet (a renewed file never replaces anyone).
  const adminEmail = (await ask("First administrator's email (optional)", "")).toLowerCase();
  let firstAdmin;
  if (adminEmail) {
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(adminEmail)) throw new LicenseError("That isn't an email address.");
    firstAdmin = { email: adminEmail, name: await ask("Their name", "Administrator"), password: newPassword() };
  }
  const validDays = Number(await ask("Valid for how many days", "30"));
  if (!Number.isInteger(validDays) || validDays < 1 || validDays > 366) throw new LicenseError("Valid for 1 to 366 days.");
  const activationKey = newActivationKey();
  const secret = { databases, ...(supabase ? { supabase } : {}), ...(firstAdmin ? { firstAdmin } : {}) };
  const text = await seal({ companyId, companyName: name, secret, activationKey, validDays });
  await open(text, activationKey); // proves the file opens before anyone gets it
  const file = write(companyId, text);
  const { expiresAt } = readHeader(text);
  console.log(`
Issued for ${name}
  Company ID       ${companyId}
  Activation key   ${activationKey}
  File             ${file}
  Expires          ${expiresAt.slice(0, 10)}${firstAdmin ? `
  First admin      ${firstAdmin.email}, first password ${firstAdmin.password} (they change it after signing in)` : ""}

Give the Company ID and the file to the company. Give the activation key to
their administrator separately (another channel, or in person). It is shown
only now: keep it somewhere safe, it is needed to renew the file.`);
}

async function renew(path) {
  const text = readFileSync(resolve(path), "utf8");
  const header = readHeader(text);
  console.log(`Renewing ${header.companyId} (${header.companyName}), apps: ${header.apps.join(", ")}`);
  const activationKey = normalizeKey(await askHidden("Activation key"));
  const { secret } = await open(text, activationKey);
  const more = (await ask("Apps to add, separated by commas (optional)", ""))
    .split(",")
    .map((a) => a.trim().toLowerCase())
    .filter(Boolean);
  const apps = [...new Set([...header.apps, ...more])];
  const databases = await askDatabases(apps, secret.databases);
  const supabase = (await ask("Change the Supabase project URL or anon key? (y/N)", "n")).toLowerCase().startsWith("y")
    ? await askSupabase(secret.supabase)
    : secret.supabase;
  const validDays = Number(await ask("Valid for how many days from today", "30"));
  if (!Number.isInteger(validDays) || validDays < 1 || validDays > 366) throw new LicenseError("Valid for 1 to 366 days.");
  const next = await seal({
    companyId: header.companyId,
    companyName: header.companyName,
    secret: { databases, ...(supabase ? { supabase } : {}), ...(secret.firstAdmin ? { firstAdmin: secret.firstAdmin } : {}) },
    activationKey,
    validDays,
  });
  await open(next, activationKey);
  const file = write(header.companyId, next);
  console.log(`\nRenewed: ${file}, expires ${readHeader(next).expiresAt.slice(0, 10)}. Same Company ID and activation key.`);
}

async function check(path) {
  const text = readFileSync(resolve(path), "utf8");
  const header = readHeader(text);
  const activationKey = await askHidden("Activation key");
  const { secret, expired } = await open(text, activationKey);
  console.log(`
${header.companyName} (${header.companyId})
  Issued    ${header.issuedAt.slice(0, 10)}
  Expires   ${header.expiresAt.slice(0, 10)}${expired ? "  EXPIRED: renew it" : ""}`);
  for (const [app, url] of Object.entries(secret.databases)) console.log(`  ${app.padEnd(9)} ${url === "local" ? "local (the app's own backend/.env database)" : maskUrl(url)}`);
  if (secret.supabase) console.log(`  realtime  ${secret.supabase.url}${secret.supabase.anonKey ? " (with anon key)" : ""}`);
  if (secret.firstAdmin) console.log(`  first admin ${secret.firstAdmin.email} (made only while the database has no accounts)`);
}

const [command, arg] = process.argv.slice(2).filter((a) => !a.startsWith("--"));
try {
  if (command === "issue") await issue();
  else if (command === "renew" && arg) await renew(arg);
  else if (command === "check" && arg) await check(arg);
  else {
    console.log("Use: npm run license -- issue | renew <file.nabhi> | check <file.nabhi>");
    process.exitCode = 2;
  }
} catch (e) {
  console.error(e instanceof LicenseError ? `\n${e.message}` : e);
  process.exitCode = 1;
} finally {
  rl.close();
}
