// The .nabhi license file: sealed with an activation key, opened only with it,
// and any change to it (dates, company, data) stops it opening.

import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  LicenseError,
  checkDatabaseUrl,
  companyIdFrom,
  maskUrl,
  newActivationKey,
  normalizeKey,
  open,
  readHeader,
  seal,
} from "../license/file.mjs";

const CRM = "postgresql://nabhi_crm.abcd1234:Vx9pQ2-sT7_wLm4Nz8Rk3Hy6Jb1Cd5Fa@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres";
const INV = "postgresql://nabhi_inventory.abcd1234:Qm3Lw8-Zr5_tYp2Kx7Vn4Hs9Gc6Bd1Je@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres";
const secret = { databases: { crm: CRM, inventory: INV }, supabase: { url: "https://abcd1234.supabase.co", anonKey: "anon.jwt.value" } };

test("activation keys: 25 characters in 5 groups, typed any way", () => {
  const key = newActivationKey();
  assert.match(key, /^[0-9A-HJKMNP-TV-Z]{5}(-[0-9A-HJKMNP-TV-Z]{5}){4}$/);
  assert.notEqual(newActivationKey(), key);
  assert.equal(normalizeKey(key.toLowerCase().replaceAll("-", " ")), key.replaceAll("-", ""));
  assert.equal(normalizeKey("OOOOO-IIIII-LLLLL-00000-11111"), "0000011111111110000011111");
  assert.throws(() => normalizeKey("short"), LicenseError);
});

test("Company IDs from names", () => {
  assert.equal(companyIdFrom("Getmeds Philippines Inc."), "NBH-GETMEDS-01");
  assert.equal(companyIdFrom("2MG Pharma Corp", 3), "NBH-2MGPHARMA-03");
});

test("the postgres user is refused; an app's own user is taken", () => {
  assert.throws(
    () => checkDatabaseUrl("postgresql://postgres.abcd1234:secret@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"),
    /postgres user/,
  );
  assert.equal(checkDatabaseUrl(CRM), CRM);
  assert.ok(checkDatabaseUrl("postgresql://postgres:x@localhost:5432/postgres", { allowPostgres: true }));
  assert.throws(() => checkDatabaseUrl("https://example.com"), /postgresql:\/\//);
  assert.throws(() => checkDatabaseUrl("postgresql://nabhi_crm@host/postgres"), /password/);
});

test("sealed with the key, opened with the key", async () => {
  const key = newActivationKey();
  const text = await seal({ companyId: "NBH-GETMEDS-01", companyName: "Getmeds", secret, activationKey: key, validDays: 30 });
  assert.ok(!text.includes("Vx9pQ2") && !text.includes("nabhi_crm") && !text.includes("pooler"), "no password, user or host in the file");
  const header = readHeader(text);
  assert.deepEqual(header.apps, ["crm", "inventory"]);
  const opened = await open(text, key.toLowerCase());
  assert.deepEqual(opened.secret, secret);
  assert.equal(opened.header.companyId, "NBH-GETMEDS-01");
  assert.equal(opened.expired, false);
});

test("the wrong key doesn't open it", async () => {
  const text = await seal({ companyId: "NBH-GETMEDS-01", companyName: "Getmeds", secret, activationKey: newActivationKey() });
  await assert.rejects(open(text, newActivationKey()), /doesn't open this file/);
});

test("changing the dates, the company or the data stops it opening", async () => {
  const key = newActivationKey();
  const text = await seal({ companyId: "NBH-GETMEDS-01", companyName: "Getmeds", secret, activationKey: key });
  const file = JSON.parse(text);
  const later = { ...file, expiresAt: "2099-01-01T00:00:00.000Z" };
  await assert.rejects(open(JSON.stringify(later), key), /doesn't open this file/);
  const other = { ...file, companyId: "NBH-OTHER-01" };
  await assert.rejects(open(JSON.stringify(other), key), /doesn't open this file/);
  const bytes = Buffer.from(file.data, "base64");
  bytes[3] ^= 1;
  await assert.rejects(open(JSON.stringify({ ...file, data: bytes.toString("base64") }), key), /doesn't open this file/);
  await assert.rejects(open(JSON.stringify({ ...file, kdf: { ...file.kdf, N: 2 } }), key), /changed/);
});

test("two files for the same company never look alike", async () => {
  const key = newActivationKey();
  const a = JSON.parse(await seal({ companyId: "NBH-GETMEDS-01", companyName: "Getmeds", secret, activationKey: key }));
  const b = JSON.parse(await seal({ companyId: "NBH-GETMEDS-01", companyName: "Getmeds", secret, activationKey: key }));
  assert.notEqual(a.data, b.data);
  assert.notEqual(a.kdf.salt, b.kdf.salt);
});

test("an expired file still opens, and says it's expired", async () => {
  const key = newActivationKey();
  const text = await seal({ companyId: "NBH-GETMEDS-01", companyName: "Getmeds", secret, activationKey: key, validDays: 1, now: new Date("2026-01-01") });
  assert.equal((await open(text, key, { now: new Date("2026-01-03") })).expired, true);
});

test("a file from a newer Nabhi asks for an update", () => {
  assert.throws(() => readHeader(JSON.stringify({ format: "nabhi-license", version: 2 })), /Update the Nabhi app/);
  assert.throws(() => readHeader("not json"), /isn't a Nabhi license file/);
});

test("passwords are hidden when shown", () => {
  assert.equal(
    maskUrl(CRM),
    "postgresql://nabhi_crm.abcd1234:•••• (32 characters)@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres",
  );
});

test("the tool issues a file, and checks it with the key", () => {
  const dir = mkdtempSync(join(tmpdir(), "nabhi-issued-"));
  const tool = join(import.meta.dirname, "..", "tools", "license.mjs");
  const env = { ...process.env, NABHI_ISSUED_DIR: dir };
  const issued = spawnSync(process.execPath, [tool, "issue"], {
    env,
    encoding: "utf8",
    input: ["Getmeds Philippines Inc.", "", "crm,inventory", CRM, INV, "https://abcd1234.supabase.co", "anon.jwt.value", "mila@getmeds.ph", "Mila Aguilar", "30", ""].join("\n"),
  });
  assert.equal(issued.status, 0, issued.stderr + issued.stdout);
  assert.match(issued.stdout, /Company ID\s+NBH-GETMEDS-01/);
  assert.match(issued.stdout, /First admin\s+mila@getmeds\.ph, first password [A-Za-z0-9]{16}/);
  assert.ok(!issued.stdout.includes("Vx9pQ2"), "the password isn't printed");
  const key = issued.stdout.match(/Activation key\s+([0-9A-Z-]{29})/)[1];
  assert.deepEqual(readdirSync(dir), ["NBH-GETMEDS-01.nabhi"]);
  const file = join(dir, "NBH-GETMEDS-01.nabhi");
  assert.ok(!readFileSync(file, "utf8").includes("nabhi_crm"));

  const checked = spawnSync(process.execPath, [tool, "check", file], { env, encoding: "utf8", input: `${key}\n` });
  assert.equal(checked.status, 0, checked.stderr);
  assert.match(checked.stdout, /crm\s+postgresql:\/\/nabhi_crm\.abcd1234:•••• \(32 characters\)/);
  assert.match(checked.stdout, /first admin mila@getmeds\.ph/);
  assert.ok(!checked.stdout.includes(issued.stdout.match(/first password (\w+)/)[1]), "the first password isn't shown by check");
  assert.ok(!checked.stdout.includes("Vx9pQ2"));

  const again = spawnSync(process.execPath, [tool, "issue"], { env, encoding: "utf8", input: "Getmeds Philippines Inc.\n\n" });
  assert.equal(again.status, 1);
  assert.match(again.stderr, /issued already/);

  const refused = spawnSync(process.execPath, [tool, "issue"], {
    env: { ...env, NABHI_ISSUED_DIR: mkdtempSync(join(tmpdir(), "nabhi-issued-")) },
    encoding: "utf8",
    input: ["Other Co", "", "crm", "postgresql://postgres.abcd:secret@h:6543/postgres", CRM, "", "", "30", ""].join("\n"),
  });
  assert.equal(refused.status, 0, refused.stderr);
  assert.match(refused.stdout, /postgres user/);
});
