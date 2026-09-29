// The company this PC works for: its connection, locked to this PC.
//
// On activation the .nabhi file is opened with the activation key, then the
// connection and the key are encrypted again with Windows' own protection
// (DPAPI, through Electron's safeStorage): only this Windows account on this
// PC can read them back. The key is kept (locked the same way) so a renewed
// file for the same company opens without asking for it again.

import { app, safeStorage } from "electron";
import { existsSync, readFileSync, rmSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { ConnectionFileError, normalizeKey, open, readHeader } from "../lib/connection-file.mjs";

const file = () => join(app.getPath("userData"), "company.json");

function lock(text) {
  if (!safeStorage.isEncryptionAvailable()) {
    throw new ConnectionFileError("Windows can't protect the connection on this account, so it isn't saved. Sign in to Windows with your own account and try again.");
  }
  return safeStorage.encryptString(text).toString("base64");
}

function unlock(base64) {
  return safeStorage.decryptString(Buffer.from(base64, "base64"));
}

function store(header, secret, key) {
  mkdirSync(app.getPath("userData"), { recursive: true });
  writeFileSync(file(), JSON.stringify({ header, secret: lock(JSON.stringify(secret)), key: lock(key) }, null, 2), { encoding: "utf8", mode: 0o600 });
}

/** The saved company, or null before activation. */
export function saved() {
  if (!existsSync(file())) return null;
  const s = JSON.parse(readFileSync(file(), "utf8"));
  try {
    return { header: s.header, secret: JSON.parse(unlock(s.secret)), key: unlock(s.key) };
  } catch {
    throw new ConnectionFileError("The saved connection can't be unlocked on this Windows account (it was set up by someone else, or copied from another PC). Activate Nabhi again.");
  }
}

function expiredMessage(header) {
  return `This connection file expired on ${header.expiresAt.slice(0, 10)}. Ask your administrator for the renewed file.`;
}

/** First time on this PC: the two IDs and the file. */
export async function activate({ companyId, activationKey, fileText }) {
  const header = readHeader(fileText);
  const typed = String(companyId ?? "").trim().toUpperCase();
  if (header.companyId !== typed) {
    throw new ConnectionFileError(`This file is for ${header.companyId}, not ${typed || "the Company ID typed"}. Check the Company ID, or use the file sent for it.`);
  }
  const opened = await open(fileText, activationKey);
  if (opened.expired) throw new ConnectionFileError(expiredMessage(opened.header));
  store(opened.header, opened.secret, normalizeKey(activationKey));
  return opened.header;
}

/** A renewed file for the same company: opens with the key already saved. */
export async function replace(fileText) {
  const current = saved();
  if (!current) throw new ConnectionFileError("Activate Nabhi first.");
  const header = readHeader(fileText);
  if (header.companyId !== current.header.companyId) {
    throw new ConnectionFileError(`This file is for ${header.companyId}; this PC works for ${current.header.companyId}. To switch companies, remove this company from the PC first.`);
  }
  const opened = await open(fileText, current.key);
  if (opened.expired) throw new ConnectionFileError(expiredMessage(opened.header));
  store(opened.header, opened.secret, current.key);
  return opened.header;
}

export function forget() {
  rmSync(file(), { force: true });
}
