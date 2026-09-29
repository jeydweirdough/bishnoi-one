#!/usr/bin/env node
/**
 * The keys the Nabhi apps use to trust each other, made once for a deployment.
 *
 *   node scripts/deploy-keys.mjs
 *
 * Prints each one beside the Vercel project and setting it goes in. Nothing is
 * saved: copy them into Vercel (Settings > Environment Variables, Production)
 * as you go. Running it again makes new ones, which replace all of them.
 *
 *   - The platform signs a pass when a Nabhi account opens an app; each app
 *     checks it with the public half. The private half stays on the platform.
 *   - The CRM asks Inventory (products, stock) and Finance (tax, fund
 *     requests) with a key each of them gave it.
 *
 * Nabhi Order's key comes from Nabhi Order (ORDERS_API_KEY), not from here.
 */

import { generateKeyPairSync, randomBytes } from "node:crypto";

const b64 = (b64url) => Buffer.from(b64url, "base64url").toString("base64");
const { privateKey, publicKey } = generateKeyPairSync("ed25519");
const signing = b64(privateKey.export({ format: "jwk" }).d);
const verifying = b64(publicKey.export({ format: "jwk" }).x);
const key = () => randomBytes(24).toString("base64url");
const inventoryKey = key();
const financeKey = key();

const rows = [
  ["nabhi-platform-backend", "PASS_SIGNING_KEY", signing, "secret"],
  ["nabhi-crm-backend", "PLATFORM_PUBLIC_KEY", verifying],
  ["nabhi-inventory-backend", "PLATFORM_PUBLIC_KEY", verifying],
  ["nabhi-finance-backend", "PLATFORM_PUBLIC_KEY", verifying],
  ["nabhi-admin-backend", "PLATFORM_PUBLIC_KEY", verifying],
  ["nabhi-pharmacy-backend", "PLATFORM_PUBLIC_KEY", verifying],
  ["nabhi-inventory-backend", "INTEGRATION_KEYS", JSON.stringify([`crm:${inventoryKey}`]), "secret"],
  ["nabhi-crm-backend", "INVENTORY_API_KEY", inventoryKey, "secret"],
  ["nabhi-finance-backend", "INTEGRATION_KEYS", JSON.stringify([`crm:${financeKey}`]), "secret"],
  ["nabhi-crm-backend", "FINANCE_API_KEY", financeKey, "secret"],
];

console.log("Nabhi deployment keys. Shown once; nothing is saved.\n");
let last = "";
for (const [project, name, value, secret] of rows.sort((a, b) => a[0].localeCompare(b[0]))) {
  if (project !== last) console.log(`${last ? "\n" : ""}${project}`);
  last = project;
  console.log(`  ${name}=${value}${secret ? "   (secret)" : ""}`);
}
console.log("\nAfter setting them, redeploy each project so it reads them.");
