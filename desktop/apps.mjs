// The Bishnoi One apps that open as a desktop app: what each is called, and where
// its screens run on this PC.
//
// The port is read from the app's own frontend/package.json (its dev script),
// the same place scripts/run-app.mjs reads it, so it is written down once. An
// app with no screens yet (In-licensing, Regulatory) has no dev script and is
// left out.

import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const HOST = "localhost";

// The mark and colour are for the icon (make-icons.mjs), until each app has its own artwork.
// Since 2026-10-24 there is one: the one app, every module's screens (the app frontends were removed).
const KNOWN = {
  "bishnoi-one-app": { name: "Bishnoi One", mark: "B", color: "#e2701b" },
};

// The app's API port, from its backend/main.py (--port's default), as scripts/run-app.mjs reads it.
function apiPort(folder) {
  const file = join(ROOT, folder, "backend", "main.py");
  if (!existsSync(file)) return null;
  const found = readFileSync(file, "utf8").match(/"--port",[^)]*default=(\d+)/)?.[1];
  return found ? Number(found) : null;
}

function port(folder) {
  const file = join(ROOT, folder, "frontend", "package.json");
  if (!existsSync(file)) return null;
  const found = JSON.parse(readFileSync(file, "utf8")).scripts?.dev?.match(/--port\s+(\d+)/)?.[1];
  return found ? Number(found) : null;
}

export const APPS = Object.fromEntries(
  Object.entries(KNOWN)
    .map(([folder, app]) => [folder, { ...app, port: port(folder), apiPort: apiPort(folder) }])
    .filter(([, app]) => app.port),
);

export const webUrl = (folder, path = "/") => `http://${HOST}:${APPS[folder].port}${path}`;
