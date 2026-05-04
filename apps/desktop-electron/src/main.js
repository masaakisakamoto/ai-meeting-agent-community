const { app, BrowserWindow, shell } = require('electron');
const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

const DEFAULT_PORT = Number(process.env.MEETING_AGENT_BRIDGE_PORT || 8765);
let bridgeProcess = null;

function projectRoot() {
  return path.resolve(__dirname, '..', '..', '..');
}

function workspaceDir() {
  return process.env.MEETING_AGENT_DESKTOP_WORKSPACE || path.join(projectRoot(), 'demo_out', 'desktop_alpha_bundle');
}

function startBridge() {
  const root = projectRoot();
  const workspace = workspaceDir();
  const python = process.env.MEETING_AGENT_PYTHON || 'python';
  const env = { ...process.env, PYTHONPATH: process.env.PYTHONPATH || path.join(root, 'src') };
  bridgeProcess = spawn(python, ['-m', 'meeting_agent', 'desktop-serve', '--workspace', workspace, '--port', String(DEFAULT_PORT)], {
    cwd: root,
    env,
    stdio: 'inherit'
  });
  bridgeProcess.on('exit', (code) => {
    if (code !== 0 && code !== null) console.warn(`Desktop bridge exited with code ${code}`);
    bridgeProcess = null;
  });
}

function createWindow() {
  const workspace = workspaceDir();
  const indexPath = path.join(workspace, 'desktop_lite', 'index.html');
  const win = new BrowserWindow({
    width: 1280,
    height: 900,
    title: 'AI Meeting Agent Desktop Alpha',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
  if (fs.existsSync(indexPath)) {
    win.loadFile(indexPath, { query: { bridge: `http://127.0.0.1:${DEFAULT_PORT}` } });
  } else {
    win.loadURL(`http://127.0.0.1:${DEFAULT_PORT}/`);
  }
}

app.whenReady().then(() => {
  startBridge();
  setTimeout(createWindow, 400);
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('before-quit', () => { if (bridgeProcess) bridgeProcess.kill(); });
