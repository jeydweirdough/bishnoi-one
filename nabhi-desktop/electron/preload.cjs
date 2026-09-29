// Only Nabhi's own screens (activation, starting, problems: file:// pages) get
// this bridge. The apps' screens, served from 127.0.0.1, get nothing.
const { contextBridge, ipcRenderer } = require("electron");

if (location.protocol === "file:") {
  contextBridge.exposeInMainWorld("nabhi", {
    activate: (form) => ipcRenderer.invoke("nabhi:activate", form),
    replace: (fileText) => ipcRenderer.invoke("nabhi:replace", fileText),
    retry: () => ipcRenderer.invoke("nabhi:retry"),
    forget: () => ipcRenderer.invoke("nabhi:forget"),
    onState: (fn) => ipcRenderer.on("nabhi:state", (_e, state) => fn(state)),
  });
}
