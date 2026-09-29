// Starts each app's API and screens on this PC, and stops them.
//
// The APIs get the company's connection as an environment variable, in
// memory only; they listen on 127.0.0.1, so nothing outside this PC reaches
// them. The screens run on Electron's own Node (no Node to install).

import { app } from "electron";
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import net from "node:net";
import { dirname, join } from "node:path";
import { APPS, HOST, apiUrl, webUrl } from "../lib/apps.mjs";

export class StartError extends Error {}

const children = new Set();
let stopping = false;

/** Where the packaged APIs and screens are: beside the app when installed, dist/ when run from the repo. */
function resources() {
  return app.isPackaged ? process.resourcesPath : join(app.getAppPath(), "dist");
}

function portFree(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => server.close(() => resolve(true)));
    server.listen(port, HOST);
  });
}

const pause = (ms) => new Promise((r) => setTimeout(r, ms));

// Only what a program needs from Windows; nothing else from Nabhi's own environment.
function baseEnv() {
  const keep = ["SystemRoot", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH", "Path", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "HOMEDRIVE", "HOMEPATH", "COMPUTERNAME", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE"];
  return Object.fromEntries(keep.filter((k) => process.env[k] !== undefined).map((k) => [k, process.env[k]]));
}

function launch(file, args, { cwd, env, name }) {
  const child = spawn(file, args, { cwd, env, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
  child.nabhiName = name;
  child.log = "";
  const keep = (d) => (child.log = (child.log + d).slice(-4000));
  child.stdout.on("data", keep);
  child.stderr.on("data", keep);
  children.add(child);
  child.on("exit", () => children.delete(child));
  return child;
}

/** Waits until the process says it's ready, or answers on its address. */
async function ready(child, check, seconds) {
  for (let i = 0; i < seconds * 4; i++) {
    if (child.exitCode !== null) return false;
    if (await check().catch(() => false)) return true;
    await pause(250);
  }
  return false;
}

const get = async (url) => {
  const response = await fetch(url, { redirect: "manual", signal: AbortSignal.timeout(3000) });
  return response;
};

/**
 * Starts every app in the company's connection that this Nabhi.exe carries.
 * onStep(text) reports progress for the starting screen. Resolves to the apps started.
 */
export async function start(secret, { onStep = () => {}, onExit = () => {} } = {}) {
  stopping = false;
  const apps = Object.keys(secret.databases ?? {}).filter((a) => APPS[a]);
  if (apps.length === 0) throw new StartError("This connection file has no app this copy of Nabhi carries. Update Nabhi.exe, or ask for the right file.");

  for (const a of apps) {
    for (const port of [APPS[a].api, APPS[a].web]) {
      if (!(await portFree(port))) {
        throw new StartError(`Port ${port} on this PC is already in use (another Nabhi still closing, or another program). Wait a moment and try again, or restart the PC.`);
      }
    }
  }

  // The apps prove themselves to each other with a key made for this start only.
  const link = randomBytes(24).toString("hex");
  const firstAdmin = secret.firstAdmin
    ? { FIRST_ADMIN_EMAIL: secret.firstAdmin.email, FIRST_ADMIN_NAME: secret.firstAdmin.name, FIRST_ADMIN_PASSWORD: secret.firstAdmin.password }
    : {};

  const apis = apps.map(async (a) => {
    onStep(`Starting ${APPS[a].name}…`);
    const exe = join(resources(), "backends", `nabhi-${a}-api`, `nabhi-${a}-api.exe`);
    if (!existsSync(exe)) throw new StartError(`${APPS[a].name} is missing from this installation. Install Nabhi again.`);
    const env = {
      ...baseEnv(),
      NABHI_PORT: String(APPS[a].api),
      DATABASE_URL: secret.databases[a],
      SESSION_HOURS: "720",
      ...firstAdmin,
      ...(a === "crm" && apps.includes("inventory")
        ? { INVENTORY_API_URL: apiUrl("inventory"), INVENTORY_API_KEY: link, INVENTORY_APP_URL: webUrl("inventory") }
        : {}),
      ...(a === "inventory" && apps.includes("crm") ? { INTEGRATION_KEYS: JSON.stringify([`crm:${link}`]) } : {}),
    };
    const child = launch(exe, [], { cwd: dirname(exe), env, name: `${a}-api` });
    child.on("exit", (code) => !stopping && onExit(`${APPS[a].name} stopped (code ${code}).`));
    const ok = await ready(child, async () => child.log.includes("NABHI_READY"), 120);
    if (!ok) throw new StartError(`${APPS[a].name} didn't start.\n\n${child.log.trim().split("\n").slice(-6).join("\n")}`);
    // It starts even when the database refuses; its health says why.
    const health = await get(`${apiUrl(a)}/health`).then((r) => r.json()).catch(() => null);
    if (health?.problem) {
      const why = {
        database: "The company's database can't be reached, or refused the connection. Check the internet connection; if it keeps happening, ask your administrator for a renewed connection file.",
        version: "The company's database was updated by a newer Nabhi. Update Nabhi.exe.",
        settings: "This copy of Nabhi is set up wrongly. Install Nabhi again.",
      }[health.problem] ?? health.hint;
      throw new StartError(`${APPS[a].name}: ${why}`);
    }
  });
  await Promise.all(apis);

  await Promise.all(
    apps.map(async (a) => {
      onStep(`Opening ${APPS[a].name}…`);
      const dir = join(resources(), "web", a);
      const meta = JSON.parse(readFileSync(join(dir, "nabhi-web.json"), "utf8"));
      const server = join(dir, meta.server);
      const env = {
        ...baseEnv(),
        ELECTRON_RUN_AS_NODE: "1",
        NODE_ENV: "production",
        NEXT_TELEMETRY_DISABLED: "1",
        PORT: String(APPS[a].web),
        HOSTNAME: HOST,
        API_URL: apiUrl(a),
      };
      const child = launch(process.execPath, [server], { cwd: dirname(server), env, name: `${a}-web` });
      child.on("exit", (code) => !stopping && onExit(`${APPS[a].name} screens stopped (code ${code}).`));
      const ok = await ready(child, async () => (await get(`${webUrl(a)}/login`)).status < 500, 90);
      if (!ok) throw new StartError(`${APPS[a].name} screens didn't open.\n\n${child.log.trim().split("\n").slice(-6).join("\n")}`);
    }),
  );
  return apps;
}

export function stop() {
  stopping = true;
  for (const child of children) child.kill();
  children.clear();
}
