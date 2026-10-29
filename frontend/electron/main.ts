import { app, BrowserWindow, ipcMain, nativeImage, screen, session, Tray, Menu } from 'electron';
import { spawn, ChildProcess } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import http from 'node:http';

let mainWindow: BrowserWindow | null = null;
let bubbleWindow: BrowserWindow | null = null;
let backend: ChildProcess | null = null;
let bubbleDragOffset = { x: 0, y: 0 };
const backendUrl = process.env.AIRI_BACKEND_URL ?? 'http://127.0.0.1:8000';
function bubblePositionPath() { return path.join(app.getPath('userData'), 'bubble-position.json'); }
function checkHealth(): Promise<boolean> { return new Promise((resolve) => { const request = http.get(`${backendUrl}/health`, (res) => resolve(res.statusCode === 200)); request.on('error', () => resolve(false)); request.setTimeout(800, () => { request.destroy(); resolve(false); }); }); }
async function startBackend() {
  if (await checkHealth()) return;
  const projectRoot = path.resolve(app.getAppPath(), '..');
  const python312 = path.join(app.getPath('home'), 'AppData', 'Local', 'Programs', 'Python', 'Python312', 'python.exe');
  const python = process.env.AIRI_PYTHON ?? (existsSync(python312) ? python312 : 'py');
  const pythonArgs = python === 'py'
    ? ['-3.12', '-m', 'uvicorn', 'windows_agent.main:app', '--host', '127.0.0.1', '--port', '8000']
    : ['-m', 'uvicorn', 'windows_agent.main:app', '--host', '127.0.0.1', '--port', '8000'];
  backend = spawn(python, pythonArgs, { cwd: projectRoot, windowsHide: true, stdio: 'ignore' });
}
function enableStartAtLogin() { app.setLoginItemSettings({ openAtLogin: true, path: process.execPath, args: app.isPackaged ? [] : [app.getAppPath()] }); }
function createWindows() {
  mainWindow = new BrowserWindow({ width: 1160, height: 780, minWidth: 760, minHeight: 560, titleBarStyle: 'hidden', backgroundColor: '#101316', webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true } });
  bubbleWindow = new BrowserWindow({ width: 128, height: 128, frame: false, transparent: true, hasShadow: false, backgroundColor: '#00000000', movable: true, alwaysOnTop: true, resizable: false, skipTaskbar: true, webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true } });
  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) {
    void mainWindow.loadURL(devUrl);
    void bubbleWindow.loadURL(`${devUrl}#/bubble`);
  } else {
    const indexFile = path.join(__dirname, '../dist/index.html');
    void mainWindow.loadFile(indexFile);
    void bubbleWindow.loadFile(indexFile, { hash: '/bubble' });
  }
  mainWindow.on('closed', () => { mainWindow = null; }); bubbleWindow.on('closed', () => { bubbleWindow = null; });
  bubbleWindow.setAlwaysOnTop(true, 'floating');
  const display = screen.getPrimaryDisplay().workArea;
  let position = { x: display.x + display.width - 148, y: display.y + display.height - 148 };
  try {
    const saved = JSON.parse(readFileSync(bubblePositionPath(), 'utf8')) as { x?: number; y?: number };
    if (Number.isFinite(saved.x) && Number.isFinite(saved.y)) position = { x: saved.x!, y: saved.y! };
  } catch { }
  bubbleWindow.setPosition(position.x, position.y);
  bubbleWindow.on('moved', () => {
    if (!bubbleWindow) return;
    const [x, y] = bubbleWindow.getPosition();
    try { writeFileSync(bubblePositionPath(), JSON.stringify({ x, y }), 'utf8'); } catch { }
  });
}
app.whenReady().then(async () => { enableStartAtLogin(); session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => callback(permission === 'media')); session.defaultSession.setPermissionCheckHandler((_webContents, permission) => permission === 'media'); await startBackend(); createWindows(); const tray = new Tray(nativeImage.createEmpty()); tray.setToolTip('Jerrid AI'); tray.setContextMenu(Menu.buildFromTemplate([{ label: 'Open Assistant', click: () => mainWindow?.show() }, { label: 'Exit', click: () => app.quit() }])); });
app.on('before-quit', () => { if (backend && !backend.killed) backend.kill(); });
ipcMain.handle('backend-url', () => backendUrl);
ipcMain.on('window-control', (event, action: 'minimize' | 'maximize' | 'close') => {
  const window = BrowserWindow.fromWebContents(event.sender);
  if (!window) return;
  if (action === 'minimize') window.minimize();
  if (action === 'maximize') window.isMaximized() ? window.unmaximize() : window.maximize();
  if (action === 'close') window.close();
});
ipcMain.on('show-main', () => { mainWindow?.show(); mainWindow?.focus(); });
ipcMain.on('bubble-drag-start', (_event, point: { x: number; y: number }) => {
  if (!bubbleWindow) return;
  const [windowX, windowY] = bubbleWindow.getPosition();
  bubbleDragOffset = { x: point.x - windowX, y: point.y - windowY };
});
ipcMain.on('bubble-drag-move', (_event, point: { x: number; y: number }) => {
  bubbleWindow?.setPosition(Math.round(point.x - bubbleDragOffset.x), Math.round(point.y - bubbleDragOffset.y));
});