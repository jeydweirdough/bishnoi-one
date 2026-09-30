// The license this PC runs under: kept once, for every Nabhi app.
//
// It sits in one place for the Windows account, %APPDATA%\Nabhi\license.json,
// outside any one app's own folder. So the company's administrator sets it up
// once, in whichever Nabhi app they install first, and every Nabhi app
// installed after it (CRM, Inventory, Pharmacy...) opens with it already.
//
// What is kept: the license file exactly as issued (already encrypted), and
// the activation key, locked to this Windows account (protect.mjs). The file's
// readable header says which company and apps and until when; the contents
// are only ever opened with the key, which also proves the file is genuine
// and unchanged. A renewed file for the same company replaces the old one and
// opens with the key already kept.

import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { LicenseError, normalizeKey, open, readHeader } from "./file.mjs";
import { lock as defaultLock, unlock as defaultUnlock } from "./protect.mjs";

/** How long before it runs out an app starts to warn, and how long after it keeps working. */
export const WARN_DAYS = 7;
export const GRACE_DAYS = 3;

const DAY = 86_400_000;

/**
 * The license kept at `file` (license.json). `lock`/`unlock` are Windows'
 * protection; tests pass their own.
 */
export function licenseStore(file, { lock = defaultLock, unlock = defaultUnlock } = {}) {
  function write(fileText, key) {
    mkdirSync(dirname(file), { recursive: true });
    const kept = { header: readHeader(fileText), file: fileText, key: lock(key), savedAt: new Date().toISOString() };
    writeFileSync(file, JSON.stringify(kept, null, 2), { encoding: "utf8", mode: 0o600 });
  }

  function kept() {
    if (!existsSync(file)) return null;
    try {
      return JSON.parse(readFileSync(file, "utf8"));
    } catch {
      throw new LicenseError("The license kept on this PC is damaged. Set it up again with the Company ID, the activation key and the license file.");
    }
  }

  /** The license, opened: { header, secret, key, state }, or null before one is set up. */
  async function load({ now = new Date() } = {}) {
    const k = kept();
    if (!k) return null;
    const key = unlock(k.key);
    const opened = await open(k.file, key, { now });
    return { header: opened.header, secret: opened.secret, key, state: stateOf(opened.header, now) };
  }

  /** First time on this PC: the Company ID, the activation key and the file. */
  async function activate({ companyId, activationKey, fileText, now = new Date() }) {
    const header = readHeader(fileText);
    const typed = String(companyId ?? "").trim().toUpperCase();
    if (header.companyId !== typed) {
      throw new LicenseError(`This license file is for ${header.companyId}, not ${typed || "the Company ID typed"}. Check the Company ID, or use the file sent for it.`);
    }
    const opened = await open(fileText, activationKey, { now });
    if (stateOf(opened.header, now).ended) throw new LicenseError(endedMessage(opened.header));
    write(fileText, normalizeKey(activationKey));
    return opened.header;
  }

  /** A renewed file for the same company: opens with the key already kept. */
  async function renew(fileText, { now = new Date() } = {}) {
    const current = await load({ now });
    if (!current) throw new LicenseError("Set up the license first.");
    const header = readHeader(fileText);
    if (header.companyId !== current.header.companyId) {
      throw new LicenseError(`This license file is for ${header.companyId}; this PC runs under ${current.header.companyId}. To change companies, remove the license from this PC first.`);
    }
    const opened = await open(fileText, current.key, { now });
    if (stateOf(opened.header, now).ended) throw new LicenseError(endedMessage(opened.header));
    write(fileText, current.key);
    return opened.header;
  }

  function remove() {
    rmSync(file, { force: true });
  }

  /** Which company, without opening anything: for saying who the PC is set up for. */
  function header() {
    return kept()?.header ?? null;
  }

  return { load, activate, renew, remove, header, file };
}

/** Where a license stands on a day: in force, running out soon, in its grace days, or ended. */
export function stateOf(header, now = new Date()) {
  const days = (new Date(header.expiresAt).getTime() - now.getTime()) / DAY;
  return {
    days,
    expiring: days >= 0 && days < WARN_DAYS,
    expired: days < 0,
    ended: days < -GRACE_DAYS,
    graceUntil: new Date(new Date(header.expiresAt).getTime() + GRACE_DAYS * DAY).toISOString(),
  };
}

export function endedMessage(header) {
  return `The license for ${header.companyName || header.companyId} ran out on ${header.expiresAt.slice(0, 10)}. Ask your administrator for the renewed license file.`;
}

/** The license file's key for an app folder: nabhi-crm is "crm". */
export const licenseKeyOf = (folder) => folder.replace(/^nabhi-/, "");

/** Where the license is kept for this Windows account. Trying the apps from the repo keeps its own, apart from a real one. */
export function licensePath(appData, { development }) {
  return process.env.NABHI_LICENSE_FILE || join(appData, development ? "Nabhi development" : "Nabhi", "license.json");
}
