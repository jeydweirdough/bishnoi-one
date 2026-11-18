"use client";

// What a field agent's phone keeps while it has no signal (Step 4H, 2026-11-18): trail points and logged
// visits with their photos, in this browser's IndexedDB, until the API has them.
//
// - Each item has the phone's own id (clientId). The API keeps a visit, a photo or a point once however often
//   it's sent (routers/field.py, routers/photos.py), so an item is only taken off once the API has answered.
// - Sent in the order kept: points in batches, then each visit, then that visit's photos one by one.
// - Points are kept 8 days (the API takes them up to 7 days old); visits are never dropped: one the API refuses
//   for good stays, marked with why, so nothing is lost silently.
// - Sent when the app opens, when the phone comes back online, every few minutes, and on Background Sync
//   where the phone has it (public/sw.js asks the open page to send).
// - Only the signed-in person's items are sent: a shared phone never sends one person's visits as another's.

export type QueuedPointData = { latitude: number; longitude: number; accuracyM: number; at: string };
export type QueuedPhoto = { clientId: string; blob: Blob; name: string };

type PointItem = { clientId: string; userId: string; kind: "point"; savedAt: number; point: QueuedPointData };
type VisitItem = {
  clientId: string;
  userId: string;
  kind: "visit";
  savedAt: number;
  /** What the visit form sends to POST /visits (clientId added when sent). */
  visit: Record<string, unknown>;
  /** The doctor's name, for the chip's tip. */
  label: string;
  photos: QueuedPhoto[];
  /** Set once the API has the visit: only its photos are left to send. */
  visitId?: string;
  /** Why the API refused it for good, when it did. */
  error?: string;
};
type Item = PointItem | VisitItem;

export type QueueCounts = { visits: number; points: number; photos: number; refused: { label: string; error: string }[] };

const DB_NAME = "bishnoi-field";
const STORE = "items";
const POINT_DAYS = 8;
const BATCH = 1000;
const CLOSING_BATCH = 300;
export const SYNC_TAG = "bishnoi-field-send";

let user: string | null = null;
/** Who is signed in on this phone (set by the field tracker): their items are the ones kept and sent. */
export function setQueueUser(userId: string | null) {
  user = userId;
}
export function queueUser() {
  return user;
}

export function newClientId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

// --- storage ------------------------------------------------------------------------------------

let opening: Promise<IDBDatabase> | null = null;
function db(): Promise<IDBDatabase> {
  if (typeof indexedDB === "undefined") return Promise.reject(new Error("No storage on this browser."));
  opening ??= new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const store = req.result.createObjectStore(STORE, { keyPath: "clientId" });
      store.createIndex("user", "userId");
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => {
      opening = null;
      reject(req.error);
    };
  });
  return opening;
}

function done(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = tx.onabort = () => reject(tx.error);
  });
}

async function itemsOf(userId: string): Promise<Item[]> {
  const tx = (await db()).transaction(STORE, "readonly");
  const req = tx.objectStore(STORE).index("user").getAll(userId);
  await done(tx);
  return (req.result as Item[]).sort((a, b) => a.savedAt - b.savedAt);
}

async function put(...items: Item[]) {
  const tx = (await db()).transaction(STORE, "readwrite");
  for (const item of items) tx.objectStore(STORE).put(item);
  await done(tx);
  changed();
}

async function remove(ids: string[]) {
  if (!ids.length) return;
  const tx = (await db()).transaction(STORE, "readwrite");
  for (const id of ids) tx.objectStore(STORE).delete(id);
  await done(tx);
  changed();
}

// --- telling the screen -------------------------------------------------------------------------

const listeners = new Set<() => void>();
const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("bishnoi-field") : null;
channel?.addEventListener("message", () => listeners.forEach((l) => l()));
function changed() {
  listeners.forEach((l) => l());
  channel?.postMessage("changed");
}
/** Calls back whenever the queue changes (in this tab or another); returns the way to stop. */
export function onQueueChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Asks the phone to send by itself once it's back online (Background Sync), where it can. */
async function askForSync() {
  try {
    const reg = await navigator.serviceWorker?.ready;
    await (reg as ServiceWorkerRegistration & { sync?: { register(tag: string): Promise<void> } })?.sync?.register(SYNC_TAG);
  } catch {
    // No Background Sync here: the page sends when it's open and online.
  }
}

// --- keeping --------------------------------------------------------------------------------------

export async function keepPoint(userId: string, point: QueuedPointData) {
  await put({ clientId: newClientId(), userId, kind: "point", savedAt: Date.now(), point });
}

export async function keepVisit(userId: string, visit: Record<string, unknown> & { clientId: string }, label: string, files: File[]) {
  const photos = files.map((f) => ({ clientId: newClientId(), blob: f as Blob, name: f.name || "photo.jpg" }));
  await put({ clientId: visit.clientId, userId, kind: "visit", savedAt: Date.now(), visit, label, photos });
  void askForSync();
}

export async function counts(userId: string): Promise<QueueCounts> {
  const items = await itemsOf(userId).catch(() => [] as Item[]);
  const out: QueueCounts = { visits: 0, points: 0, photos: 0, refused: [] };
  for (const i of items) {
    if (i.kind === "point") out.points += 1;
    else if (i.error) out.refused.push({ label: i.label, error: i.error });
    else if (i.visitId) out.photos += i.photos.length;
    else out.visits += 1;
  }
  return out;
}

/** Points kept in this browser's localStorage before Step 4H: moved into the queue once. */
export async function moveOldPoints(userId: string) {
  const key = `bishnoi-trail:${userId}`;
  let old: QueuedPointData[] = [];
  try {
    old = JSON.parse(localStorage.getItem(key) ?? "[]");
  } catch {
    old = [];
  }
  if (!old.length) return;
  await put(...old.map((point, n) => ({ clientId: newClientId(), userId, kind: "point" as const, savedAt: Date.parse(point.at) || Date.now() + n, point })));
  localStorage.removeItem(key);
}

// --- sending ------------------------------------------------------------------------------------

/** A refusal that sending again won't change (not signed in, rate limits and server trouble are worth retrying). */
const forGood = (status: number) => status >= 400 && status < 500 && ![401, 403, 408, 425, 429].includes(status);

async function detailOf(r: Response): Promise<string> {
  try {
    const body = await r.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) return body.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(" ");
  } catch {
    // Not JSON.
  }
  return "The CRM couldn't take it.";
}

// redirect "manual": a signed-out session is sent to /login, which mustn't count as sent.
const post = (url: string, body: BodyInit, json: boolean, keepalive = false) =>
  fetch(url, { method: "POST", body, keepalive, redirect: "manual", headers: json ? { "Content-Type": "application/json" } : undefined, credentials: "same-origin" });

let sending: Promise<void> | null = null;

/** Sends what's waiting, oldest first; each item comes off only once the API has it. */
export function sendQueue(userId: string, { closing = false } = {}): Promise<void> {
  if (sending) return sending;
  sending = run(userId, closing)
    .catch(() => {})
    .finally(() => {
      sending = null;
    });
  return sending;
}

async function run(userId: string, closing: boolean) {
  const items = await itemsOf(userId);
  const oldest = Date.now() - POINT_DAYS * 86_400_000;
  const stale = items.filter((i) => i.kind === "point" && Date.parse(i.point.at) < oldest).map((i) => i.clientId);
  await remove(stale);
  const points = items.filter((i): i is PointItem => i.kind === "point" && !stale.includes(i.clientId));

  for (let n = 0; n < points.length; n += closing ? CLOSING_BATCH : BATCH) {
    const batch = points.slice(n, n + (closing ? CLOSING_BATCH : BATCH));
    const r = await post("/crm/api/trail", JSON.stringify({ points: batch.map((p) => ({ ...p.point, clientId: p.clientId })) }), true, closing);
    // Refused for good (e.g. a malformed point): these can never go up, so they don't block the rest.
    if (r.ok || forGood(r.status)) await remove(batch.map((p) => p.clientId));
    else return;
    if (closing) return;
  }
  if (closing) return;

  for (const item of items) {
    if (item.kind !== "visit" || item.error) continue;
    let visitId = item.visitId;
    if (!visitId) {
      const r = await post("/crm/api/visits", JSON.stringify({ ...item.visit, clientId: item.clientId }), true);
      if (forGood(r.status)) {
        await put({ ...item, error: await detailOf(r) });
        continue;
      }
      if (!r.ok) return;
      visitId = ((await r.json()) as { id: string }).id;
      await put({ ...item, visitId });
    }
    let photos = item.photos;
    for (const photo of item.photos) {
      const form = new FormData();
      form.append("file", photo.blob, photo.name);
      form.append("targetId", visitId);
      form.append("clientId", photo.clientId);
      const r = await post("/crm/api/photos", form, false);
      if (!r.ok && !forGood(r.status)) return;
      // Sent, or refused for good (too many, not a picture): either way it's done with.
      photos = photos.filter((p) => p.clientId !== photo.clientId);
      await put({ ...item, visitId, photos });
    }
    await remove([item.clientId]);
  }
}

/** Takes a refused visit off the phone, once the person has seen why. */
export async function dropRefused(userId: string) {
  const items = await itemsOf(userId);
  await remove(items.filter((i) => i.kind === "visit" && i.error).map((i) => i.clientId));
}
