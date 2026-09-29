// A company's connection, encrypted: the .nabhi file.
//
// Each client company has its own Supabase database. We hand the company two
// IDs and one file:
//   - the Company ID (NBH-GETMEDS-01): which company; not a secret;
//   - the activation key (7KQ4M-2XD9P-...): the secret that opens the file;
//   - the .nabhi file: the database connection URLs (with their passwords)
//     and the Supabase project address, encrypted with that key.
// Nabhi.exe opens the file with the key once, on activation (lib shared with
// the tool that issues the files, so the two always agree).
//
// The file is text (JSON). Its header is readable (which company, which apps,
// when it was issued and when it expires) and is bound to the encrypted part,
// so changing a date or the company in it makes the file fail to open.
//
// Encryption: AES-256-GCM with a key made from the activation key by scrypt
// (deliberately slow: guessing keys takes impractically long) with a random
// salt, and a random nonce, for every file.

import { createCipheriv, createDecipheriv, randomBytes, scrypt } from "node:crypto";

export const FORMAT = "nabhi-connection";
export const VERSION = 1;

// scrypt: about a quarter of a second and 64 MB per try on a normal PC.
const KDF = { name: "scrypt", N: 2 ** 16, r: 8, p: 1, keyLength: 32 };

// Crockford's base32: no I, L, O or U, so a key read aloud or typed by hand
// can't be mistaken (O is read as 0; I and L as 1).
const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

export class ConnectionFileError extends Error {}

/** A new activation key: 25 characters in 5 groups, about 125 bits. */
export function newActivationKey() {
  const bytes = randomBytes(16);
  let bits = 0;
  let value = 0;
  let out = "";
  for (const byte of bytes) {
    value = (value << 8) | byte;
    bits += 8;
    while (bits >= 5 && out.length < 25) {
      out += ALPHABET[(value >>> (bits - 5)) & 31];
      bits -= 5;
    }
  }
  return out.match(/.{5}/g).join("-");
}

/** The key as typed: case, spaces and dashes don't matter; O reads as 0, I and L as 1. */
export function normalizeKey(typed) {
  const key = String(typed ?? "")
    .toUpperCase()
    .replace(/[\s-]/g, "")
    .replace(/O/g, "0")
    .replace(/[IL]/g, "1");
  if (key.length !== 25 || [...key].some((c) => !ALPHABET.includes(c))) {
    throw new ConnectionFileError("That isn't an activation key: it has 25 letters and numbers, like 7KQ4M-2XD9P-RTH6W-A3CFN-8B5JE.");
  }
  return key;
}

/** A first password for the company's first administrator: 16 characters, easy to read out. */
export function newPassword() {
  const letters = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789";
  return [...randomBytes(16)].map((b) => letters[b % letters.length]).join("");
}

/** A Company ID from a company name: NBH-GETMEDS-01. */
export function companyIdFrom(name, number = 1) {
  const slug = String(name)
    .toUpperCase()
    .replace(/\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|PHILIPPINES|PHILS?)\b\.?/g, "")
    .replace(/[^A-Z0-9]+/g, "")
    .slice(0, 12);
  if (!slug) throw new ConnectionFileError("Give the company a name with letters or numbers in it.");
  return `NBH-${slug}-${String(number).padStart(2, "0")}`;
}

export function checkCompanyId(id) {
  if (!/^NBH-[A-Z0-9]{1,12}-\d{2,4}$/.test(String(id))) {
    throw new ConnectionFileError("A Company ID looks like NBH-GETMEDS-01.");
  }
  return String(id);
}

/** A database connection URL, checked: Postgres, with a user, a password and a host.
 *  The full-access postgres user is refused unless allowed: each app should
 *  have its own user (scripts/supabase/app-users.sql). */
export function checkDatabaseUrl(url, { allowPostgres = false } = {}) {
  let parsed;
  try {
    parsed = new URL(String(url).trim());
  } catch {
    throw new ConnectionFileError("That isn't a connection URL. It starts with postgresql://");
  }
  if (!["postgresql:", "postgres:"].includes(parsed.protocol)) {
    throw new ConnectionFileError("A connection URL starts with postgresql://");
  }
  const user = decodeURIComponent(parsed.username);
  if (!user || !parsed.password || !parsed.hostname) {
    throw new ConnectionFileError("The connection URL needs a user, a password and a host: postgresql://user:password@host:6543/postgres");
  }
  if (!allowPostgres && (user === "postgres" || user.startsWith("postgres."))) {
    throw new ConnectionFileError(
      "This connection uses the postgres user, which can reach everything. Use the app's own user (nabhi_crm.<project-ref>) from scripts/supabase/app-users.sql.",
    );
  }
  return String(url).trim();
}

function kdf(key, salt, params) {
  return new Promise((resolve, reject) =>
    scrypt(key, salt, params.keyLength, { N: params.N, r: params.r, p: params.p, maxmem: 256 * 1024 * 1024 }, (err, out) =>
      err ? reject(err) : resolve(out),
    ),
  );
}

// The header, as bound to the encrypted part: same fields, same order, every time.
function headerBytes(h) {
  return Buffer.from(
    JSON.stringify([h.format, h.version, h.companyId, h.companyName, h.apps, h.issuedAt, h.expiresAt]),
    "utf8",
  );
}

/**
 * Encrypts a company's connection into the text of a .nabhi file.
 * secret: { databases: { crm: "postgresql://...", ... }, supabase?: { url, anonKey } }
 */
export async function seal({ companyId, companyName, secret, activationKey, validDays = 30, now = new Date() }) {
  checkCompanyId(companyId);
  const key = normalizeKey(activationKey);
  const apps = Object.keys(secret?.databases ?? {}).sort();
  if (apps.length === 0) throw new ConnectionFileError("Add at least one app's database connection.");
  for (const app of apps) {
    if (!/^[a-z][a-z0-9_-]{1,30}$/.test(app)) throw new ConnectionFileError(`"${app}" isn't an app name like crm or inventory.`);
  }
  const header = {
    format: FORMAT,
    version: VERSION,
    companyId,
    companyName: String(companyName ?? "").trim(),
    apps,
    issuedAt: now.toISOString(),
    expiresAt: new Date(now.getTime() + validDays * 86_400_000).toISOString(),
  };
  const salt = randomBytes(16);
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", await kdf(key, salt, KDF), iv);
  cipher.setAAD(headerBytes(header));
  const data = Buffer.concat([cipher.update(JSON.stringify(secret), "utf8"), cipher.final()]);
  const file = {
    ...header,
    kdf: { name: KDF.name, N: KDF.N, r: KDF.r, p: KDF.p, salt: salt.toString("base64") },
    cipher: { name: "aes-256-gcm", iv: iv.toString("base64"), tag: cipher.getAuthTag().toString("base64") },
    data: data.toString("base64"),
  };
  return JSON.stringify(file, null, 2) + "\n";
}

/** The readable header of a .nabhi file, without the key. */
export function readHeader(text) {
  let file;
  try {
    file = JSON.parse(text);
  } catch {
    throw new ConnectionFileError("This isn't a Nabhi connection file.");
  }
  if (file?.format !== FORMAT) throw new ConnectionFileError("This isn't a Nabhi connection file.");
  if (file.version !== VERSION) throw new ConnectionFileError("This connection file is from a newer Nabhi. Update Nabhi.exe to open it.");
  return file;
}

/** Opens a .nabhi file with its activation key: { header, secret }. */
export async function open(text, activationKey, { now = new Date() } = {}) {
  const file = readHeader(text);
  const key = normalizeKey(activationKey);
  if (file.kdf?.name !== "scrypt" || file.cipher?.name !== "aes-256-gcm") {
    throw new ConnectionFileError("This connection file uses an encryption this Nabhi doesn't know. Update Nabhi.exe.");
  }
  const params = { N: file.kdf.N, r: file.kdf.r, p: file.kdf.p, keyLength: KDF.keyLength };
  if (!(params.N >= 2 ** 14 && params.N <= 2 ** 20 && params.r <= 16 && params.p <= 4)) {
    throw new ConnectionFileError("This connection file has been changed and can't be opened.");
  }
  const header = {
    format: file.format,
    version: file.version,
    companyId: file.companyId,
    companyName: file.companyName,
    apps: file.apps,
    issuedAt: file.issuedAt,
    expiresAt: file.expiresAt,
  };
  let plain;
  try {
    const decipher = createDecipheriv("aes-256-gcm", await kdf(key, Buffer.from(file.kdf.salt, "base64"), params), Buffer.from(file.cipher.iv, "base64"));
    decipher.setAAD(headerBytes(header));
    decipher.setAuthTag(Buffer.from(file.cipher.tag, "base64"));
    plain = Buffer.concat([decipher.update(Buffer.from(file.data, "base64")), decipher.final()]).toString("utf8");
  } catch {
    // A wrong key and a changed file look the same to GCM; say both.
    throw new ConnectionFileError("The activation key doesn't open this file. Check the key, or ask for a new file if this one was changed.");
  }
  const secret = JSON.parse(plain);
  return { header, secret, expired: new Date(header.expiresAt) <= now };
}

/** A connection URL with its password hidden, for showing on screen. */
export function maskUrl(url) {
  try {
    const u = new URL(url);
    return `${u.protocol}//${decodeURIComponent(u.username)}:•••• (${decodeURIComponent(u.password).length} characters)@${u.host}${u.pathname}`;
  } catch {
    return "(not a URL)";
  }
}
