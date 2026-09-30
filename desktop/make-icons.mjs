// Draws each app's icon into icons/<folder>.png: `npm run icons` in this folder.
//
// A plain mark in the app's colour, to tell the windows apart on the taskbar
// until each app has its own artwork. Change the mark or colour in apps.mjs,
// then run this again.

import { app, BrowserWindow } from "electron";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { APPS } from "./apps.mjs";

const SIZE = 256;
const out = join(dirname(fileURLToPath(import.meta.url)), "icons");

const page = ({ mark, color }) => `<!doctype html><meta charset="utf-8">
<style>
  html, body { margin: 0; width: ${SIZE}px; height: ${SIZE}px; background: transparent; overflow: hidden; }
  div { width: ${SIZE}px; height: ${SIZE}px; border-radius: 48px; background: ${color}; color: #fff; display: grid; place-items: center;
        font: 600 ${mark.length > 1 ? 124 : 156}px/1 Poppins, "Segoe UI", system-ui, sans-serif; letter-spacing: -.02em; }
</style><div>${mark}</div>`;

// Each icon's window is closed when it's drawn: that alone must not end the run.
app.on("window-all-closed", () => {});

app.whenReady().then(async () => {
  mkdirSync(out, { recursive: true });
  for (const [folder, one] of Object.entries(APPS)) {
    const win = new BrowserWindow({ width: SIZE, height: SIZE, show: false, frame: false, transparent: true, webPreferences: { offscreen: true } });
    await win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(page(one))}`);
    // A window drawn off screen hands over its picture each time it paints: ask for one now the page is in.
    const image = await new Promise((done) => {
      win.webContents.on("paint", (_e, _dirty, painted) => !painted.isEmpty() && done(painted));
      win.webContents.invalidate();
    });
    writeFileSync(join(out, `${folder}.png`), image.resize({ width: SIZE, height: SIZE }).toPNG());
    win.destroy();
    console.log(`icons/${folder}.png`);
  }
  app.quit();
});
