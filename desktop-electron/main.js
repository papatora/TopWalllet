// TopWallet Launcher — Electron main process.
// Prinsip: TIDAK ADA operasi blocking di main thread (pembeda dari Tauri
// yang not-responding) — semua probe (netstat/python detect) async via exec.
const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { spawn, execFile } = require('child_process');
const fs = require('fs');
const path = require('path');

const PORT = 8787;
const REPO = path.resolve(__dirname, '..');
const DEFAULT_SERVER_DIR = path.join(REPO, 'Database Local only', 'html');
const CFG_FILE = path.join(REPO, 'data', 'launcher.json');

let win = null;
let serverProc = null;

function readCfg() {
  try { return JSON.parse(fs.readFileSync(CFG_FILE, 'utf8')); }
  catch { return {}; }
}

function serverDir() {
  const cfg = readCfg();
  if (cfg.server_dir && fs.existsSync(cfg.server_dir)) return cfg.server_dir;
  if (fs.existsSync(path.join(DEFAULT_SERVER_DIR, 'server.py'))) {
    return DEFAULT_SERVER_DIR;
  }
  return DEFAULT_SERVER_DIR;
}

function findPython() {
  return new Promise((resolve) => {
    const cfg = readCfg();
    const candidates = [];
    if (cfg.python) candidates.push(cfg.python);
    candidates.push('python', 'py');
    const localRoot = path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python');
    try {
      for (const d of fs.readdirSync(localRoot)) {
        candidates.push(path.join(localRoot, d, 'python.exe'));
      }
    } catch { /* tanpa LOCALAPPDATA python */ }
    let i = 0;
    const next = () => {
      if (i >= candidates.length) return resolve(null);
      const exe = candidates[i++];
      execFile(exe, ['--version'], { timeout: 5000 }, (err) => {
        if (!err) return resolve(exe);
        next();
      });
    };
    next();
  });
}

function netstatPid(port) {
  return new Promise((resolve) => {
    execFile('netstat', ['-ano'], { timeout: 10000, maxBuffer: 4e6 }, (err, stdout) => {
      if (err || !stdout) return resolve(null);
      const lines = stdout.split('\n');
      for (const ln of lines) {
        if (ln.includes(`:${port} `) && ln.includes('LISTENING')) {
          const pid = parseInt(ln.trim().split(/\s+/).pop(), 10);
          if (pid > 0) return resolve(pid);
        }
      }
      resolve(null);
    });
  });
}

function taskkill(pid) {
  return new Promise((resolve) => {
    execFile('taskkill', ['/F', '/PID', String(pid)], { timeout: 10000 }, () => resolve());
  });
}

function log(line) {
  if (win && !win.isDestroyed()) {
    win.webContents.send('log', `[${new Date().toLocaleTimeString()}] ${line}`);
  }
}

async function startServer() {
  const owned = await netstatPid(PORT);
  if (serverProc && serverProc.exitCode === null) {
    return { ok: false, msg: `Server sudah jalan (PID ${serverProc.pid})` };
  }
  if (owned) {
    return { ok: false, msg: `Port ${PORT} dipakai proses lain (PID ${owned}) — Stop-paksa dulu`, externalPid: owned };
  }
  const py = await findPython();
  if (!py) return { ok: false, msg: 'Python tidak ketemu — set "python" di data/launcher.json' };
  const dir = serverDir();
  serverProc = spawn(py, ['server.py', '--port', String(PORT)], {
    cwd: dir, windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  log(`server start: ${py} server.py --port ${PORT} (cwd ${dir})`);
  serverProc.stdout.on('data', (d) => String(d).split('\n').filter(Boolean).forEach(log));
  serverProc.stderr.on('data', (d) => String(d).split('\n').filter(Boolean).forEach(log));
  serverProc.on('exit', (code) => { log(`server exit (${code})`); });
  return { ok: true, msg: `Server start (PID ${serverProc.pid})` };
}

async function stopServer(force) {
  if (serverProc && serverProc.exitCode === null) {
    const pid = serverProc.pid;
    serverProc.removeAllListeners('exit');
    serverProc.kill();
    log(`server stop (PID ${pid})`);
  }
  const owned = await netstatPid(PORT);
  if (owned) {
    await taskkill(owned);
    log(`force-kill pemilik port ${PORT}: PID ${owned}`);
    return { ok: true, msg: `Paksa-matikan PID ${owned}` };
  }
  return { ok: true, msg: force ? 'Tidak ada proses di port' : 'Server stop' };
}

async function status() {
  const owned = await netstatPid(PORT);
  const mine = serverProc && serverProc.exitCode === null;
  return {
    running: !!owned,
    mine: !!mine,
    external: !!owned && !mine,
    pid: owned || null,
    serverDir: serverDir(),
  };
}

function createWindow() {
  win = new BrowserWindow({
    width: 760, height: 560,
    backgroundColor: '#0b0e18',
    autoHideMenuBar: true,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true },
  });
  win.loadFile('index.html');
}

ipcMain.handle('status', () => status());
ipcMain.handle('start', () => startServer());
ipcMain.handle('stop', (_e, force) => stopServer(!!force));
ipcMain.handle('open', () => shell.openExternal(`http://127.0.0.1:${PORT}`));

app.whenReady().then(createWindow);
app.on('window-all-closed', () => {
  if (serverProc && serverProc.exitCode === null) serverProc.kill();
  app.quit();
});
