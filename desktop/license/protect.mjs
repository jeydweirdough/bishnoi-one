// Locking a secret to this Windows account on this PC (Windows DPAPI).
//
// Electron's own safeStorage can't be used for the license: its key lives in
// each app's own data folder, so what Nabhi CRM locked, Nabhi Inventory could
// never open. DPAPI's "current user" protection is the account's own, the same
// for every program the account runs, so every Nabhi app can open what any of
// them locked, and nobody else can: not another Windows account, not another PC.
//
// Windows PowerShell is on every Windows PC and reaches DPAPI directly, so no
// native module has to be built for each Electron version. It takes about half
// a second, once when an app starts.

import { spawnSync } from "node:child_process";
import { LicenseError } from "./file.mjs";

// Mixed into the protection, so a secret only unlocks as the Nabhi license.
const ENTROPY = "Nabhi license";

function run(script, input) {
  if (process.platform !== "win32") throw new LicenseError("For now the Nabhi license can only be kept on Windows.");
  const result = spawnSync(
    "powershell.exe",
    ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", `Add-Type -AssemblyName System.Security; $in = [Console]::In.ReadToEnd().Trim(); ${script}`],
    { input, encoding: "utf8", windowsHide: true, timeout: 30_000 },
  );
  if (result.status !== 0 || !result.stdout.trim()) {
    throw new LicenseError("Windows couldn't unlock the license on this account (it was set up by another Windows account, or copied from another PC). Set it up again with the Company ID, the activation key and the license file.");
  }
  return result.stdout.trim();
}

const ARGS = `[Text.Encoding]::UTF8.GetBytes('${ENTROPY}'), [Security.Cryptography.DataProtectionScope]::CurrentUser`;

/** Text locked to this Windows account, as base64. */
export function lock(text) {
  // In and out as base64, so no character is lost on the way through the console.
  return run(`[Convert]::ToBase64String([Security.Cryptography.ProtectedData]::Protect([Convert]::FromBase64String($in), ${ARGS}))`, Buffer.from(text, "utf8").toString("base64"));
}

/** What lock() locked, back as text. */
export function unlock(locked) {
  const plain = run(`[Convert]::ToBase64String([Security.Cryptography.ProtectedData]::Unprotect([Convert]::FromBase64String($in), ${ARGS}))`, locked);
  return Buffer.from(plain, "base64").toString("utf8");
}
