// Only Bishnoi One's own screens (the license and starting screens: file:// pages)
// get this bridge. The apps' screens, served from localhost, get nothing.
const { contextBridge, ipcRenderer } = require("electron");

if (location.protocol === "file:") {
  contextBridge.exposeInMainWorld("bishnoi", {
    activate: (form) => ipcRenderer.invoke("license:activate", form),
    renew: (fileText) => ipcRenderer.invoke("license:renew", fileText),
    retry: () => ipcRenderer.invoke("license:retry"),
    remove: () => ipcRenderer.invoke("license:remove"),
  });
}
