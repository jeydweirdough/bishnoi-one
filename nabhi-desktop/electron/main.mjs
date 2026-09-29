// Nabhi.exe: one window with the company's Nabhi apps, run on this PC.
//
// First time on a PC it asks for the Company ID, the activation key and the
// connection file (company-store.mjs). After that it starts each app's API and
// screens on this PC (services.mjs) and opens the first app.

import { app, BrowserWindow, dialog, ipcMain, Menu, shell } from "electron";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { APPS, HOST, webUrl } from "../lib/apps.mjs";
import { ConnectionFileError } from "../lib/connection-file.mjs";
import { activate, forget, replace, saved } from "./company-store.mjs";
import { start, stop, StartError } from "./services.mjs";

const here = dirname(fileURLToPath(import.meta.url));
// For trying Nabhi from the repo without touching a real setup.
if (!app.isPackaged && process.env.NABHI_USER_DATA) app.setPath("userData", process.env.NABHI_USER_DATA);

const WARN_DAYS = 7; // warn this long before the connection file expires
const GRACE_DAYS = 3; // keep working this long after, for a renewed file to arrive

let win = null;
let company = null; // the saved header, for the menu and screens
let started = [];

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });
  app.whenReady().then(boot);
}

// Links inside Nabhi stay inside; everything else opens in the browser.
const ours = (url) => {
  try {
    const u = new URL(url);
    return u.protocol === "file:" || (u.hostname === HOST && Object.values(APPS).some((a) => Number(u.port) === a.web));
  } catch {
    return false;
  }
};

function guard(contents) {
  contents.on("will-navigate", (event, url) => {
    if (!ours(url)) {
      event.preventDefault();
      if (/^https?:/.test(url)) shell.openExternal(url);
    }
  });
  contents.setWindowOpenHandler(({ url }) => {
    if (ours(url)) {
      return { action: "allow", overrideBrowserWindowOptions: { autoHideMenuBar: true, webPreferences: { sandbox: true, contextIsolation: true } } };
    }
    if (/^https?:/.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
}

app.on("web-contents-created", (_e, contents) => guard(contents));

function state(s) {
  if (win && !win.isDestroyed()) win.webContents.send("nabhi:state", { company, ...s });
}

async function showShell() {
  if (!win.webContents.getURL().startsWith("file:")) await win.loadFile(join(here, "ui", "shell.html"));
}

function menu() {
  const appItems = started.map((a, i) => ({
    label: APPS[a].name,
    accelerator: `CmdOrCtrl+${i + 1}`,
    click: () => win.loadURL(webUrl(a)),
  }));
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      {
        label: "Nabhi",
        submenu: [
          ...appItems,
          ...(appItems.length ? [{ type: "separator" }] : []),
          { label: "Reload", accelerator: "CmdOrCtrl+R", click: () => win.webContents.reload() },
          { label: "Use a renewed connection file…", click: pickRenewedFile, enabled: !!company },
          { label: "Remove this company from this PC…", click: confirmForget, enabled: !!company },
          { type: "separator" },
          { role: "quit", label: "Quit Nabhi" },
        ],
      },
      { role: "editMenu" },
      {
        label: "View",
        submenu: [
          { role: "zoomIn" },
          { role: "zoomOut" },
          { role: "resetZoom" },
          { type: "separator" },
          { role: "togglefullscreen" },
          ...(app.isPackaged ? [] : [{ role: "toggleDevTools" }]),
        ],
      },
      {
        label: "Help",
        submenu: [
          {
            label: "About Nabhi",
            click: () =>
              dialog.showMessageBox(win, {
                title: "About Nabhi",
                message: `Nabhi ${app.getVersion()}`,
                detail: company
                  ? `${company.companyName} (${company.companyId})\nConnection file valid until ${company.expiresAt.slice(0, 10)}.`
                  : "Not set up on this PC yet.",
              }),
          },
        ],
      },
    ]),
  );
}

async function boot() {
  win = new BrowserWindow({
    width: 1360,
    height: 880,
    minWidth: 960,
    minHeight: 640,
    show: false,
    title: "Nabhi",
    backgroundColor: "#eceef2",
    webPreferences: { preload: join(here, "preload.cjs"), contextIsolation: true, sandbox: true, nodeIntegration: false },
  });
  win.once("ready-to-show", () => win.show());
  win.on("closed", () => (win = null));
  menu();
  await win.loadFile(join(here, "ui", "shell.html"));
  checkForUpdates();
  await run();
}

async function run() {
  stop();
  started = [];
  await showShell();
  let saved_;
  try {
    saved_ = saved();
  } catch (e) {
    company = null;
    menu();
    state({ view: "problem", error: e.message });
    return;
  }
  if (!saved_) {
    company = null;
    menu();
    return state({ view: "activate" });
  }
  company = saved_.header;
  menu();

  const expires = new Date(company.expiresAt);
  const days = (expires - Date.now()) / 86_400_000;
  if (days < -GRACE_DAYS) {
    return state({
      view: "problem",
      error: `The connection file expired on ${company.expiresAt.slice(0, 10)}. Ask your administrator for the renewed file, then choose "Use a renewed connection file".`,
    });
  }

  const steps = [];
  const step = (text) => {
    steps.push(text);
    state({ view: "starting", steps: [...steps] });
  };
  try {
    started = await start(saved_.secret, {
      onStep: step,
      onExit: (why) => {
        started = [];
        menu();
        showShell().then(() => state({ view: "problem", error: `${why} Try again; if it keeps happening, restart the PC.` }));
      },
    });
    menu();
    await win.loadURL(webUrl(started[0]));
    if (days < WARN_DAYS) {
      dialog.showMessageBox(win, {
        type: "warning",
        title: "Connection file",
        message: days < 0 ? "The connection file has expired" : `The connection file expires in ${Math.max(1, Math.ceil(days))} days`,
        detail: `Ask your administrator for the renewed file, then choose Nabhi > Use a renewed connection file. ${
          days < 0 ? `Nabhi keeps working until ${new Date(expires.getTime() + GRACE_DAYS * 86_400_000).toISOString().slice(0, 10)}.` : ""
        }`,
      });
    }
  } catch (e) {
    stop();
    started = [];
    menu();
    await showShell();
    state({ view: "problem", error: e instanceof StartError || e instanceof ConnectionFileError ? e.message : `Something went wrong: ${e.message}` });
  }
}

// --- the shell's buttons -----------------------------------------------------------------------

const fromShell = (event) => event.senderFrame?.url?.startsWith("file:");

ipcMain.handle("nabhi:activate", async (event, form) => {
  if (!fromShell(event)) return { ok: false, error: "Not allowed." };
  try {
    await activate(form);
    run();
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e instanceof ConnectionFileError ? e.message : `Something went wrong: ${e.message}` };
  }
});

ipcMain.handle("nabhi:replace", async (event, fileText) => {
  if (!fromShell(event)) return { ok: false, error: "Not allowed." };
  try {
    await replace(fileText);
    run();
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e instanceof ConnectionFileError ? e.message : `Something went wrong: ${e.message}` };
  }
});

ipcMain.handle("nabhi:retry", (event) => {
  if (fromShell(event)) run();
});

ipcMain.handle("nabhi:forget", async (event) => {
  if (fromShell(event)) await confirmForget();
});

async function pickRenewedFile() {
  const picked = await dialog.showOpenDialog(win, { title: "Renewed connection file", filters: [{ name: "Nabhi connection file", extensions: ["nabhi", "txt", "json"] }], properties: ["openFile"] });
  if (picked.canceled || !picked.filePaths[0]) return;
  const { readFileSync } = await import("node:fs");
  try {
    const header = await replace(readFileSync(picked.filePaths[0], "utf8"));
    await dialog.showMessageBox(win, { message: "Connection file renewed", detail: `Valid until ${header.expiresAt.slice(0, 10)}. Nabhi restarts its apps now.` });
    run();
  } catch (e) {
    dialog.showErrorBox("Not renewed", e instanceof ConnectionFileError ? e.message : e.message);
  }
}

async function confirmForget() {
  const answer = await dialog.showMessageBox(win, {
    type: "warning",
    buttons: ["Remove", "Cancel"],
    defaultId: 1,
    cancelId: 1,
    title: "Remove this company from this PC",
    message: `Remove ${company?.companyName ?? "the company"} from this PC?`,
    detail: "The saved connection is deleted from this PC. Nothing in the company's database changes. To use Nabhi here again, set it up with the Company ID, the activation key and the connection file.",
  });
  if (answer.response !== 0) return;
  stop();
  forget();
  company = null;
  run();
}

// --- updates ---------------------------------------------------------------------------------

async function checkForUpdates() {
  // Only an installed Nabhi built with an update address (electron-builder's publish setting) looks for updates.
  if (!app.isPackaged || !existsSync(join(process.resourcesPath, "app-update.yml"))) return;
  try {
    const { default: updater } = await import("electron-updater");
    updater.autoUpdater.checkForUpdatesAndNotify();
  } catch {
    // no connection, or no update address: try again next start
  }
}

app.on("before-quit", stop);
app.on("window-all-closed", () => app.quit());
