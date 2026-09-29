// The Nabhi apps that open as a desktop app: what each is called, and where
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
const KNOWN = {
  "nabhi-admin": { name: "Nabhi Admin", mark: "A", color: "#172233" },
  "nabhi-crm": { name: "Nabhi CRM", mark: "C", color: "#3a3f9c" },
  "nabhi-finance": { name: "Nabhi Finance", mark: "F", color: "#1f6f47" },
  "nabhi-inventory": { name: "Nabhi Inventory", mark: "I", color: "#8a4b0f" },
  "nabhi-pharmacy": { name: "Nabhi Pharmacy", mark: "Rx", color: "#0f6470" },
  "nabhi-platform": { name: "Nabhi Platform", mark: "P", color: "#414d60" },
};

function port(folder) {
  const file = join(ROOT, folder, "frontend", "package.json");
  if (!existsSync(file)) return null;
  const found = JSON.parse(readFileSync(file, "utf8")).scripts?.dev?.match(/--port\s+(\d+)/)?.[1];
  return found ? Number(found) : null;
}

export const APPS = Object.fromEntries(
  Object.entries(KNOWN)
    .map(([folder, app]) => [folder, { ...app, port: port(folder) }])
    .filter(([, app]) => app.port),
);

export const webUrl = (folder, path = "/") => `http://${HOST}:${APPS[folder].port}${path}`;
