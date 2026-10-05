// One Bishnoi One app in a window of its own: `npm run bishnoi-crm:app`.
//
// scripts/run-app.mjs starts the app's API and screens, then this, which waits
// for the screens to answer and opens them. Each app is a program of its own:
// its own window, taskbar button, sign-in and saved settings. A link to
// another Bishnoi One app opens in that app's window.
//
// Which company may use an app is decided by the Platform (a company is
// registered there first), not by anything on this PC.

import { app, BrowserWindow, dialog, Menu, shell } from "electron";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { createConnection } from "node:net";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { APPS, HOST, webUrl } from "./apps.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const flag = (name) => process.argv.find((a) => a.startsWith(`--${name}=`))?.slice(name.length + 3) ?? "";

const folder = flag("bishnoi-app");
const me = APPS[folder];
const SUITE = "Bishnoi One";

let win = null;
let wanted = null; // the page to open once the screens answer
let opening = false;

const home = () => webUrl(folder);
const icon = () => {
  const file = join(here, "icons", `${folder}.png`);
  return existsSync(file) ? file : undefined;
};

// The screens title their pages "Customers · Bishnoi One"; the window says which app.
const titled = (title) => (title === SUITE ? me.name : title.endsWith(` · ${SUITE}`) ? `${title.slice(0, -SUITE.length)}${me.name}` : title);

// --- whose page is it ------------------------------------------------------------------------

const LOCAL = new Set(["localhost", "127.0.0.1"]);

/** The Bishnoi One app a page belongs to, or null for anywhere else. */
function ownerOf(url) {
  try {
    const u = new URL(url);
    if (!/^https?:$/.test(u.protocol) || !LOCAL.has(u.hostname)) return null;
    return Object.keys(APPS).find((f) => APPS[f].port === Number(u.port)) ?? null;
  } catch {
    return null;
  }
}

/**
 * This app's own pages stay in this window. So does signing in with a Bishnoi One
 * account: the Platform's sign-in page (/go) sends the person straight back here.
 */
function stays(url) {
  const owner = ownerOf(url);
  return owner === folder || (owner === "bishnoi-platform" && new URL(url).pathname === "/go");
}

function guard(contents) {
  const leave = (event, url) => {
    if (stays(url)) return;
    event.preventDefault();
    send(url);
  };
  contents.on("will-navigate", leave);
  contents.on("will-redirect", leave);
  contents.setWindowOpenHandler(({ url }) => {
    if (stays(url)) {
      return { action: "allow", overrideBrowserWindowOptions: { autoHideMenuBar: true, icon: icon(), webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false } } };
    }
    send(url);
    return { action: "deny" };
  });
}

/** A link that leaves this app: to the other Bishnoi One app's window, or the browser. */
async function send(url) {
  const owner = ownerOf(url);
  if (!owner) {
    if (/^(https?|mailto|tel):/i.test(url)) shell.openExternal(url);
    return;
  }
  if (!(await answers(APPS[owner].port))) return notRunning(owner);
  spawn(process.execPath, [here, `--bishnoi-app=${owner}`, `--bishnoi-open=${url}`], { detached: true, stdio: "ignore" }).unref();
}

function notRunning(owner) {
  dialog.showMessageBox(win, {
    type: "info",
    title: me.name,
    message: `${APPS[owner].name} isn't running on this PC`,
    detail: `Start it in a terminal, then try again:\n\nnpm run ${owner}:app`,
  });
}

// --- opening the screens -----------------------------------------------------------------------

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

const answers = (port, host = HOST) =>
  new Promise((done) => {
    const socket = createConnection({ host, port });
    const end = (ok) => {
      socket.destroy();
      done(ok);
    };
    socket.setTimeout(1000, () => end(false));
    socket.once("connect", () => end(true));
    socket.once("error", () => end(false));
  });

/** Shows the starting screen until the app's screens answer, then opens the page. */
async function open(url) {
  wanted = url;
  if (opening || !win) return;
  opening = true;
  try {
    await win.loadFile(join(here, "start.html"), { query: { name: me.name, run: `npm run ${folder}:app` } });
    // What the starting screen shows: 0 the server starting, 1 the screens
    // being prepared, 2 opening. Each step is real.
    const step = (n) => win?.webContents.send("start:step", n);
    step(0);
    // The API listens on 127.0.0.1 (localhost can mean ::1 on Windows).
    while (win && me.apiPort && !(await answers(me.apiPort, "127.0.0.1"))) await sleep(700);
    step(1);
    while (win && !(await answers(me.port))) await sleep(700);
    step(2);
    if (win) await win.loadURL(wanted);
  } catch {
    // The page didn't load: did-fail-load (in boot) starts this again.
  } finally {
    opening = false;
  }
}

function boot() {
  win = new BrowserWindow({
    width: 1360,
    height: 880,
    minWidth: 960,
    minHeight: 640,
    show: false,
    title: me.name,
    icon: icon(),
    backgroundColor: "#eceef2",
    // The bridge is only for Bishnoi One's own screens (preload.cjs); the app's screens get nothing.
    webPreferences: { preload: join(here, "preload.cjs"), contextIsolation: true, sandbox: true, nodeIntegration: false },
  });
  win.once("ready-to-show", () => win.show());
  // Closing the app's window closes the app, and any pages it opened beside it.
  win.on("closed", () => {
    win = null;
    app.quit();
  });
  win.webContents.on("did-fail-load", (_e, code, _text, url, mainFrame) => {
    // -3 is a page given up for another (a redirect, a second click): not a failure.
    if (!mainFrame || code === -3 || url.startsWith("file:")) return;
    const owner = ownerOf(url);
    // The screens stopped answering (restarted in the terminal): wait for them again.
    if (owner === folder) return void setTimeout(() => open(url), 1000);
    if (owner) notRunning(owner);
    setTimeout(() => open(home()), 0);
  });
  menu();
  const asked = flag("bishnoi-open");
  open(asked && ownerOf(asked) === folder ? asked : home());
}

// --- the menu ----------------------------------------------------------------------------------

function menu() {
  const page = (window) => (window ?? win)?.webContents;
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      {
        label: me.name,
        submenu: [
          { label: "Home", accelerator: "Alt+Home", click: () => open(home()) },
          { label: "Back", accelerator: "Alt+Left", click: (_i, w) => page(w)?.navigationHistory.goBack() },
          { label: "Forward", accelerator: "Alt+Right", click: (_i, w) => page(w)?.navigationHistory.goForward() },
          { label: "Reload", accelerator: "CmdOrCtrl+R", click: (_i, w) => page(w)?.reload() },
          { type: "separator" },
          { role: "quit", label: `Quit ${me.name}` },
        ],
      },
      { role: "editMenu" },
      {
        label: "View",
        submenu: [{ role: "zoomIn" }, { role: "zoomOut" }, { role: "resetZoom" }, { type: "separator" }, { role: "togglefullscreen" }, { role: "toggleDevTools" }],
      },
      {
        label: "Bishnoi One apps",
        submenu: Object.keys(APPS)
          .filter((f) => f !== folder)
          .map((f) => ({ label: APPS[f].name, click: () => send(webUrl(f)) })),
      },
      {
        label: "Help",
        submenu: [
          {
            label: `About ${me.name}`,
            click: () =>
              dialog.showMessageBox(win, {
                title: `About ${me.name}`,
                message: me.name,
                detail: `Development copy, run from the repo.\nScreens: ${home()}\nSigned-in sessions and settings are kept for this app only.`,
              }),
          },
        ],
      },
    ]),
  );
}

// --- start -------------------------------------------------------------------------------------

if (!me) {
  dialog.showErrorBox(SUITE, `Which app? ${folder ? `"${folder}" has no screens to open. ` : ""}One of: ${Object.keys(APPS).join(", ")}`);
  app.exit(1);
} else {
  // Set before anything is saved, so each app keeps its own sign-in and settings,
  // and so two apps can be open at once (the one-window lock is per folder).
  app.setName(me.name);
  app.setPath("userData", join(app.getPath("appData"), "Bishnoi One development", folder));
  if (process.platform === "win32") app.setAppUserModelId(`ph.bishnoi.${folder.replace("bishnoi-", "")}.development`);

  if (!app.requestSingleInstanceLock({ open: flag("bishnoi-open") })) {
    app.quit();
  } else {
    // Started again, or a link from another app: bring the window forward, on that page.
    app.on("second-instance", (_e, _argv, _cwd, asked) => {
      if (!win) return;
      if (win.isMinimized()) win.restore();
      win.focus();
      if (asked?.open && ownerOf(asked.open) === folder) open(asked.open);
    });
    app.on("web-contents-created", (_e, contents) => guard(contents));
    app.on("browser-window-created", (_e, created) => {
      created.on("page-title-updated", (event, title) => {
        event.preventDefault();
        created.setTitle(titled(title));
      });
    });
    app.on("window-all-closed", () => app.quit());
    app.whenReady().then(boot);
  }
}
