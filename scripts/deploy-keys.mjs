#!/usr/bin/env node
/**
 * The one key a Bishnoi One deployment makes by hand: the Platform's signing key.
 *
 *   node scripts/deploy-keys.mjs
 *
 * Prints it beside the Vercel project it goes in. Nothing is saved: copy it into
 * Vercel (Settings > Environment Variables, Production). Running it again makes
 * a new one, which replaces it: everyone signs in again, and the outside
 * services' secrets saved on the Platform have to be typed in again.
 *
 *   - The Platform signs a pass when a Bishnoi One account opens an app. Each
 *     app fetches the public half from the Platform (GET /pass/key), so it isn't
 *     copied anywhere (PLATFORM_PUBLIC_KEY is only needed to pin it).
 *   - Everything between the apps (their addresses and keys), the companies'
 *     outside services (Zoho, email providers) and each app's key for its own
 *     secrets come from the Platform's Connections page, through each app's
 *     connect key (PLATFORM_APP_KEY), made there.
 */

import { generateKeyPairSync } from "node:crypto";

const b64 = (b64url) => Buffer.from(b64url, "base64url").toString("base64");
const { privateKey } = generateKeyPairSync("ed25519");
const signing = b64(privateKey.export({ format: "jwk" }).d);

console.log("Bishnoi One deployment key. Shown once; nothing is saved.\n");
console.log("bishnoi-one-platform-backend");
console.log(`  PASS_SIGNING_KEY=${signing}   (secret)`);
console.log("\nThen redeploy the Platform's API. Every other app's keys come from the Platform's Connections page (PLATFORM_APP_KEY).");
