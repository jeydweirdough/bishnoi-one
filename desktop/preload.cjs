// Only Bishnoi One's own screen (the starting screen: a file:// page)
// get this bridge. The apps' screens, served from localhost, get nothing.
const { contextBridge, ipcRenderer } = require("electron");

if (location.protocol === "file:") {
  contextBridge.exposeInMainWorld("bishnoi", {
    // The starting screen: which step the app is on (main.mjs, open).
    onStep: (show) => ipcRenderer.on("start:step", (_event, n) => show(n)),
  });
}
