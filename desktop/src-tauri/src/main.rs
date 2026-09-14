#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! TopWallet Launcher — desktop wrapper yang bertugas SATU hal:
//! start/stop server explorer lokal (python server.py, 127.0.0.1:8787)
//! dengan tombol, plus log kecil. Tidak ada logika dompet/kripto di sini.

use std::io::{BufRead, BufReader};
use std::net::TcpStream;
use std::os::windows::process::CommandExt;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use tauri::{AppHandle, Emitter, Manager, State};

const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const PORT: &str = "8787";
const URL: &str = "http://127.0.0.1:8787";

struct ServerState {
    child: Mutex<Option<Child>>,
}

// ---------------- discovery helpers ----------------

fn find_python() -> Option<(String, Vec<String>)> {
    // (exe, prefix args) — `py` launcher butuh `-3`
    for (exe, args) in [("python", vec![]), ("py", vec!["-3".into()])] {
        if Command::new(exe)
            .args(&args)
            .arg("--version")
            .creation_flags(CREATE_NO_WINDOW)
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
        {
            return Some((exe.into(), args));
        }
    }
    // fallback: instalasi default Python.org
    if let Some(appdata) = std::env::var_os("LOCALAPPDATA") {
        let root = PathBuf::from(appdata).join("Programs").join("Python");
        if let Ok(entries) = std::fs::read_dir(&root) {
            let mut dirs: Vec<_> = entries.filter_map(|e| e.ok()).collect();
            dirs.sort_by_key(|e| e.file_name()); // ambil versi tertua yang stabil
            for d in dirs {
                let candidate = d.path().join("python.exe");
                if candidate.exists() {
                    return Some((candidate.to_string_lossy().to_string(), vec![]));
                }
            }
        }
    }
    None
}

fn exe_dir() -> Option<PathBuf> {
    std::env::current_exe().ok()?.parent().map(|p| p.to_path_buf())
}

fn read_config_dir() -> Option<String> {
    let cfg = exe_dir()?.join("topwallet-launcher.ini");
    let text = std::fs::read_to_string(cfg).ok()?;
    for line in text.lines() {
        if let Some(v) = line.strip_prefix("html_dir=") {
            let v = v.trim().trim_matches('"');
            if !v.is_empty() {
                return Some(v.to_string());
            }
        }
    }
    None
}

fn write_config_dir(dir: &str) {
    if let Some(d) = exe_dir() {
        let _ = std::fs::write(
            d.join("topwallet-launcher.ini"),
            format!("html_dir={dir}\n"),
        );
    }
}

fn find_html_dir() -> Option<String> {
    // 1. env override  2. config next to exe  3. walk up from exe
    // 4. lokasi repo default (single-user tool)
    if let Some(v) = std::env::var_os("TOPWALLET_HTML_DIR") {
        let p = PathBuf::from(v);
        if p.join("server.py").exists() {
            return Some(p.to_string_lossy().to_string());
        }
    }
    if let Some(v) = read_config_dir() {
        if PathBuf::from(&v).join("server.py").exists() {
            return Some(v);
        }
    }
    if let Some(mut dir) = exe_dir() {
        for _ in 0..6 {
            let candidate = dir.join("Database Local only").join("html");
            if candidate.join("server.py").exists() {
                let s = candidate.to_string_lossy().to_string();
                write_config_dir(&s);
                return Some(s);
            }
            dir = dir.parent()?.to_path_buf();
        }
    }
    let default = r"C:\Users\ROG\Documents\ClaudeCode\SniperToken\TopWalllet\Database Local only\html";
    if PathBuf::from(default).join("server.py").exists() {
        write_config_dir(default);
        return Some(default.into());
    }
    None
}

fn port_open() -> bool {
    TcpStream::connect(("127.0.0.1", 8787)).is_ok()
}

// ---------------- commands ----------------

#[tauri::command]
fn get_config() -> serde_json::Value {
    let (python, args) = find_python()
        .map(|(e, a)| (Some(e), Some(a)))
        .unwrap_or((None, None));
    serde_json::json!({
        "python": python,
        "python_args": args.unwrap_or_default(),
        "html_dir": find_html_dir(),
        "port_open": port_open(),
        "url": URL,
    })
}

#[tauri::command]
fn start_server(state: State<ServerState>, app: AppHandle) -> Result<String, String> {
    if port_open() {
        return Err(format!("Port {PORT} sudah dipakai — server mungkin sudah jalan"));
    }
    let html = find_html_dir().ok_or_else(|| {
        "server.py tidak ditemukan. Isi html_dir= di topwallet-launcher.ini \
         (sebelah exe) dengan path folder 'Database Local only/html'"
            .to_string()
    })?;
    let (py, pyargs) = find_python().ok_or("Python tidak ditemukan di sistem")?;

    let mut cmd = Command::new(&py);
    cmd.args(&pyargs)
        .current_dir(&html)
        .arg("server.py")
        .arg("--port")
        .arg(PORT)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .creation_flags(CREATE_NO_WINDOW);
    let mut child = cmd.spawn().map_err(|e| format!("Gagal menjalankan Python: {e}"))?;

    if let Some(out) = child.stdout.take() {
        spawn_reader(app.clone(), out);
    }
    if let Some(err) = child.stderr.take() {
        spawn_reader(app.clone(), err);
    }
    let pid = child.id();
    *state.child.lock().unwrap() = Some(child);
    let _ = app.emit("server-log", format!("[launcher] server start (pid {pid})"));
    Ok(html)
}

fn spawn_reader(app: AppHandle, stream: impl std::io::Read + Send + 'static) {
    thread::spawn(move || {
        for line in BufReader::new(stream).lines().map_while(Result::ok) {
            let _ = app.emit("server-log", line);
        }
    });
}

#[tauri::command]
fn stop_server(state: State<ServerState>, app: AppHandle) -> Result<(), String> {
    let mut guard = state.child.lock().unwrap();
    if let Some(mut c) = guard.take() {
        let _ = c.kill();
        let _ = c.wait();
        let _ = app.emit("server-log", "[launcher] server dihentikan");
    }
    Ok(())
}

#[tauri::command]
fn server_status(state: State<ServerState>) -> serde_json::Value {
    let mut ours = false;
    {
        let mut guard = state.child.lock().unwrap();
        if let Some(c) = guard.as_mut() {
            match c.try_wait() {
                Ok(None) => ours = true,
                Ok(Some(_)) => { *guard = None; } // sudah exit
                Err(_) => {}
            }
        }
    }
    serde_json::json!({ "ours": ours, "port_open": port_open() })
}

#[tauri::command]
fn open_website() {
    let _ = Command::new("cmd")
        .args(["/C", "start", "", URL])
        .creation_flags(CREATE_NO_WINDOW)
        .spawn();
}

fn main() {
    tauri::Builder::default()
        .manage(ServerState { child: Mutex::new(None) })
        .invoke_handler(tauri::generate_handler![
            get_config,
            start_server,
            stop_server,
            server_status,
            open_website
        ])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(mut c) = window
                    .state::<ServerState>()
                    .child
                    .lock()
                    .unwrap()
                    .take()
                {
                    let _ = c.kill();
                    let _ = c.wait();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("gagal menjalankan aplikasi");
}
