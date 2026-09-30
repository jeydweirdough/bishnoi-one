// The license kept on a PC: set up once, shared by every Nabhi app, renewed in
// place, and refused when it's for another company or has run out.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { newActivationKey, seal } from "../license/file.mjs";
import { licenseKeyOf, licensePath, licenseStore, stateOf } from "../license/store.mjs";

// Windows' lock stands in as a reversible marker: the real one is tried by hand (protect.mjs).
const fakeLock = { lock: (t) => `locked:${Buffer.from(t).toString("base64")}`, unlock: (l) => Buffer.from(l.slice(7), "base64").toString() };
const secret = { databases: { crm: "local", inventory: "local" } };
const place = () => join(mkdtempSync(join(tmpdir(), "nabhi-license-")), "Nabhi", "license.json");

async function issued({ companyId = "NBH-GETMEDS-01", key = newActivationKey(), validDays = 30, now = new Date() } = {}) {
  return { key, text: await seal({ companyId, companyName: "Getmeds", secret, activationKey: key, validDays, now }) };
}

test("set up once, it opens for every app on the PC", async () => {
  const file = place();
  const { key, text } = await issued();
  const crm = licenseStore(file, fakeLock);
  assert.equal(await crm.load(), null);
  await crm.activate({ companyId: "nbh-getmeds-01", activationKey: key, fileText: text });
  // Another app, started later, reading the same place.
  const inventory = licenseStore(file, fakeLock);
  const found = await inventory.load();
  assert.equal(found.header.companyId, "NBH-GETMEDS-01");
  assert.deepEqual(found.header.apps, ["crm", "inventory"]);
  assert.deepEqual(found.secret, secret);
  // The key is kept locked, never as typed.
  assert.ok(!readFileSync(file, "utf8").includes(key.replaceAll("-", "")));
});

test("the wrong Company ID or key is refused, and nothing is kept", async () => {
  const file = place();
  const { key, text } = await issued();
  const store = licenseStore(file, fakeLock);
  await assert.rejects(store.activate({ companyId: "NBH-OTHER-01", activationKey: key, fileText: text }), /is for NBH-GETMEDS-01/);
  await assert.rejects(store.activate({ companyId: "NBH-GETMEDS-01", activationKey: newActivationKey(), fileText: text }), /doesn't open this file/);
  assert.equal(await store.load(), null);
});

test("a renewed file opens with the key already kept; another company's doesn't", async () => {
  const file = place();
  const first = await issued({ validDays: 5 });
  const store = licenseStore(file, fakeLock);
  await store.activate({ companyId: "NBH-GETMEDS-01", activationKey: first.key, fileText: first.text });
  const renewed = await issued({ key: first.key, validDays: 60 });
  const header = await store.renew(renewed.text);
  assert.ok(new Date(header.expiresAt) > new Date(Date.now() + 50 * 86_400_000));
  const other = await issued({ companyId: "NBH-OTHER-01" });
  await assert.rejects(store.renew(other.text), /this PC runs under NBH-GETMEDS-01/);
  store.remove();
  assert.equal(await store.load(), null);
});

test("running out: a warning first, a few days' grace, then it stops", async () => {
  const header = { expiresAt: "2026-10-10T00:00:00.000Z" };
  assert.deepEqual(
    [stateOf(header, new Date("2026-09-01")), stateOf(header, new Date("2026-10-05")), stateOf(header, new Date("2026-10-11")), stateOf(header, new Date("2026-10-20"))].map(
      (s) => [s.expiring, s.expired, s.ended],
    ),
    [
      [false, false, false],
      [true, false, false],
      [false, true, false],
      [false, true, true],
    ],
  );
  const ended = await issued({ validDays: 1, now: new Date("2026-01-01") });
  await assert.rejects(licenseStore(place(), fakeLock).activate({ companyId: "NBH-GETMEDS-01", activationKey: ended.key, fileText: ended.text }), /ran out/);
});

test("one place for every app; trying from the repo keeps its own", () => {
  assert.equal(licenseKeyOf("nabhi-crm"), "crm");
  assert.equal(licensePath("C:/Users/x/AppData/Roaming", { development: false }), join("C:/Users/x/AppData/Roaming", "Nabhi", "license.json"));
  assert.equal(licensePath("C:/Users/x/AppData/Roaming", { development: true }), join("C:/Users/x/AppData/Roaming", "Nabhi development", "license.json"));
});
