const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electron', {
  // Store operations
  store: {
    get: (key) => ipcRenderer.invoke('store-get', key),
    set: (key, value) => ipcRenderer.invoke('store-set', key, value),
    delete: (key) => ipcRenderer.invoke('store-delete', key)
  },
  
  // App operations
  getAppPath: () => ipcRenderer.invoke('get-app-path'),
  
  // Menu event listeners
  onMenuConnect: (callback) => ipcRenderer.on('menu-connect', callback),
  onMenuDisconnect: (callback) => ipcRenderer.on('menu-disconnect', callback),
  onMenuCapture: (callback) => ipcRenderer.on('menu-capture', callback),
  onMenuAutoCapture: (callback) => ipcRenderer.on('menu-auto-capture', callback),
  onMenuHome: (callback) => ipcRenderer.on('menu-home', callback),
  onMenuAbout: (callback) => ipcRenderer.on('menu-about', callback),
  
  // Remove listeners
  removeListener: (channel, callback) => ipcRenderer.removeListener(channel, callback)
});
