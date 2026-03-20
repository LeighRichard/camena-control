const { app, BrowserWindow, ipcMain, Menu } = require('electron');
const path = require('path');
// const Store = require('electron-store');

// const store = new Store();
let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 768,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
    // icon: path.join(__dirname, 'assets', 'icon.png')  // 暂时注释掉
  });

  // Load the app
  const startUrl = process.env.ELECTRON_START_URL || `file://${path.join(__dirname, 'build/index.html')}`;
  mainWindow.loadURL(startUrl);

  // Open DevTools in development
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }

  // Create application menu
  createMenu();

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Connect',
          accelerator: 'CmdOrCtrl+O',
          click: () => {
            mainWindow.webContents.send('menu-connect');
          }
        },
        {
          label: 'Disconnect',
          accelerator: 'CmdOrCtrl+D',
          click: () => {
            mainWindow.webContents.send('menu-disconnect');
          }
        },
        { type: 'separator' },
        {
          label: 'Exit',
          accelerator: 'CmdOrCtrl+Q',
          click: () => {
            app.quit();
          }
        }
      ]
    },
    {
      label: 'View',
      submenu: [
        {
          label: 'Fullscreen',
          accelerator: 'F11',
          click: () => {
            mainWindow.setFullScreen(!mainWindow.isFullScreen());
          }
        },
        { type: 'separator' },
        { role: 'reload' },
        { role: 'toggleDevTools' }
      ]
    },
    {
      label: 'Camera',
      submenu: [
        {
          label: 'Capture',
          accelerator: 'CmdOrCtrl+C',
          click: () => {
            mainWindow.webContents.send('menu-capture');
          }
        },
        {
          label: 'Start Auto Capture',
          accelerator: 'CmdOrCtrl+A',
          click: () => {
            mainWindow.webContents.send('menu-auto-capture');
          }
        },
        { type: 'separator' },
        {
          label: 'Home Position',
          accelerator: 'CmdOrCtrl+H',
          click: () => {
            mainWindow.webContents.send('menu-home');
          }
        }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'About',
          click: () => {
            mainWindow.webContents.send('menu-about');
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// IPC handlers
// ipcMain.handle('store-get', (event, key) => {
//   return store.get(key);
// });

// ipcMain.handle('store-set', (event, key, value) => {
//   store.set(key, value);
// });

// ipcMain.handle('store-delete', (event, key) => {
//   store.delete(key);
// });

ipcMain.handle('get-app-path', () => {
  return app.getPath('userData');
});

// App lifecycle
app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
