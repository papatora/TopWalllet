const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('launcher', {
  status: () => ipcRenderer.invoke('status'),
  start: () => ipcRenderer.invoke('start'),
  stop: (force) => ipcRenderer.invoke('stop', !!force),
  open: () => ipcRenderer.invoke('open'),
  onLog: (cb) => ipcRenderer.on('log', (_e, line) => cb(line)),
});
