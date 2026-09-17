// TopWallet Launcher — native WinForms (compiled with the Windows built-in
// csc.exe; zero install). Replaces the laggy Tauri app per user request.
// All probes are async on worker threads — the UI can never "not respond".
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows.Forms;

static class Program
{
    const int PORT = 8787;
    static Process serverProc;
    static TextBox logBox;
    static Label dot, stxt, ssub;
    static Button bStart, bStop, bForce;

    static string Repo = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, ".."));

    [STAThread]
    static void Main()
    {
        Application.EnableVisualStyles();
        var f = new Form
        {
            Text = "TopWallet Launcher",
            Width = 740, Height = 520,
            BackColor = Color.FromArgb(11, 14, 24),
            FormBorderStyle = FormBorderStyle.FixedSingle,
            MaximizeBox = false,
        };

        var logo = new Label { Text = "★ TOPWALLET LAUNCHER", Left = 18, Top = 14, AutoSize = true,
            ForeColor = Color.FromArgb(232, 235, 247), Font = new Font("Segoe UI", 12, FontStyle.Bold) };
        var chain = new Label { Text = "Robinhood Chain · 4663", Left = 560, Top = 18, AutoSize = true,
            ForeColor = Color.FromArgb(125, 135, 173), Font = new Font("Consolas", 9) };

        dot = new Label { Left = 20, Top = 60, Width = 14, Height = 14, BackColor = Color.FromArgb(90, 98, 132) };
        stxt = new Label { Text = "Memeriksa…", Left = 44, Top = 54, AutoSize = true,
            ForeColor = Color.FromArgb(232, 235, 247), Font = new Font("Segoe UI", 11, FontStyle.Bold) };
        ssub = new Label { Text = "127.0.0.1:8787", Left = 44, Top = 80, AutoSize = true,
            ForeColor = Color.FromArgb(125, 135, 173), Font = new Font("Consolas", 9) };

        bStart = Btn("▶  Mulai Server", 20, 112, Color.FromArgb(40, 127, 240), Color.White);
        bStop = Btn("■  Stop", 165, 112, Color.FromArgb(13, 18, 36), Color.FromArgb(198, 207, 235));
        bForce = Btn("⛔  Stop-paksa", 260, 112, Color.FromArgb(13, 18, 36), Color.FromArgb(255, 139, 154));
        var bOpen = Btn("↗  Buka Website", 385, 112, Color.FromArgb(13, 18, 36), Color.FromArgb(198, 207, 235));

        bStart.Click += (s, e) => Run(() => StartServer());
        bStop.Click += (s, e) => Run(() => StopServer(false));
        bForce.Click += (s, e) => Run(() => StopServer(true));
        bOpen.Click += (s, e) => Process.Start("http://127.0.0.1:" + PORT);

        logBox = new TextBox
        {
            Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical,
            Left = 18, Top = 160, Width = 690, Height = 270,
            BackColor = Color.FromArgb(13, 17, 32), ForeColor = Color.FromArgb(139, 149, 186),
            BorderStyle = BorderStyle.FixedSingle,
            Font = new Font("Consolas", 9),
            Text = "log server muncul di sini…\r\n",
        };

        var foot = new Label { Text = "Explorer: http://127.0.0.1:8787 · Stop-paksa mematikan proses APAPUN pemegang port 8787",
            Left = 18, Top = 440, AutoSize = true, ForeColor = Color.FromArgb(82, 91, 125), Font = new Font("Consolas", 8) };

        f.Controls.AddRange(new Control[] { logo, chain, dot, stxt, ssub,
            bStart, bStop, bForce, bOpen, logBox, foot });

        var timer = new System.Windows.Forms.Timer { Interval = 2000 };
        timer.Tick += (s, e) => Run(RefreshStatus);
        timer.Start();
        Run(RefreshStatus);

        Application.Run(f);
    }

    static Button Btn(string text, int x, int y, Color bg, Color fg)
    {
        return new Button
        {
            Text = text, Left = x, Top = y, Width = 138, Height = 34,
            FlatStyle = FlatStyle.Flat, BackColor = bg, ForeColor = fg,
            Font = new Font("Segoe UI", 9, FontStyle.Bold),
        };
    }

    static void Run(Func<string> work)
    {
        Task.Run(() =>
        {
            try { var msg = work(); SafeUi(msg); }
            catch (Exception ex) { SafeUi("ERR " + ex.Message); }
        });
    }

    static void SafeUi(string msg)
    {
        if (logBox.InvokeRequired)
            logBox.BeginInvoke((Action)(() => { logBox.AppendText(msg + "\r\n"); }));
        else { logBox.AppendText(msg + "\r\n"); }
    }

    static string ServerDir()
    {
        var cfg = Path.Combine(Repo, "data", "launcher.json");
        try
        {
            var j = File.ReadAllText(cfg);
            var m = System.Text.RegularExpressions.Regex.Match(j, "\"server_dir\"\\s*:\\s*\"([^\"]+)\"");
            if (m.Success && Directory.Exists(m.Groups[1].Value.Replace("\\\\", "\\"))) return m.Groups[1].Value.Replace("\\\\", "\\");
        }
        catch { }
        return Path.Combine(Repo, "Database Local only", "html");
    }

    static int? PortOwnerPid()
    {
        try
        {
            var psi = new ProcessStartInfo("netstat", "-ano")
            {
                UseShellExecute = false, RedirectStandardOutput = true,
                CreateNoWindow = true,
            };
            using (var p = Process.Start(psi))
            {
                string line;
                while ((line = p.StandardOutput.ReadLine()) != null)
                {
                    if (line.Contains(":" + PORT + " ") && line.Contains("LISTENING"))
                    {
                        var parts = line.Trim().Split();
                        int pid;
                        if (int.TryParse(parts[parts.Length - 1], out pid) && pid > 0) return pid;
                    }
                }
            }
        }
        catch { }
        return null;
    }

    static string FindPython()
    {
        try
        {
            var j = File.ReadAllText(Path.Combine(Repo, "data", "launcher.json"));
            var m = System.Text.RegularExpressions.Regex.Match(j, "\"python\"\\s*:\\s*\"([^\"]+)\"");
            if (m.Success && File.Exists(m.Groups[1].Value.Replace("\\\\", "\\"))) return m.Groups[1].Value.Replace("\\\\", "\\");
        }
        catch { }
        string[] cands = { "python", "py" };
        foreach (var c in cands)
        {
            try
            {
                var psi = new ProcessStartInfo(c, "--version")
                {
                    UseShellExecute = false, RedirectStandardOutput = true,
                    RedirectStandardError = true, CreateNoWindow = true,
                };
                using (var p = Process.Start(psi))
                {
                    p.WaitForExit(4000);
                    if (p.HasExited && p.ExitCode == 0) return c;
                }
            }
            catch { }
        }
        try
        {
            var root = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Programs", "Python");
            if (Directory.Exists(root))
                foreach (var d in Directory.GetDirectories(root))
                {
                    var exe = Path.Combine(d, "python.exe");
                    if (File.Exists(exe)) return exe;
                }
        }
        catch { }
        return null;
    }

    static string StartServer()
    {
        int? owner = PortOwnerPid();
        if (owner != null) return "Port " + PORT + " sudah dipakai (PID " + owner + ") — Stop-paksa dulu";
        if (serverProc != null && !serverProc.HasExited) return "Server sudah jalan (PID " + serverProc.Id + ")";
        var py = FindPython();
        if (py == null) return "Python tidak ketemu — set \"python\" di data/launcher.json";
        var dir = ServerDir();
        var psi = new ProcessStartInfo(py, "server.py --port " + PORT)
        {
            WorkingDirectory = dir,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        serverProc = Process.Start(psi);
        serverProc.OutputDataReceived += (s, e) => { if (!string.IsNullOrEmpty(e.Data)) SafeUi(e.Data); };
        serverProc.ErrorDataReceived += (s, e) => { if (!string.IsNullOrEmpty(e.Data)) SafeUi(e.Data); };
        serverProc.BeginOutputReadLine();
        serverProc.BeginErrorReadLine();
        return "Server start (PID " + serverProc.Id + ") · cwd " + dir;
    }

    static string StopServer(bool force)
    {
        if (serverProc != null && !serverProc.HasExited)
        {
            try { serverProc.Kill(); } catch { }
            SafeUi("server stop (PID " + serverProc.Id + ")");
        }
        int? owner = PortOwnerPid();
        if (owner != null)
        {
            try
            {
                var psi = new ProcessStartInfo("taskkill", "/F /PID " + owner)
                { UseShellExecute = false, CreateNoWindow = true };
                Process.Start(psi).WaitForExit(5000);
            }
            catch { }
            return "Paksa-matikan PID " + owner;
        }
        return force ? "Tidak ada proses di port " + PORT : "Server stop";
    }

    static string RefreshStatus()
    {
        int? owner = PortOwnerPid();
        bool mine = serverProc != null && !serverProc.HasExited;
        Action upd = () =>
        {
            if (owner == null)
            {
                dot.BackColor = Color.FromArgb(90, 98, 132);
                stxt.Text = "Server mati";
                ssub.Text = "127.0.0.1:8787 · bebas";
            }
            else if (mine)
            {
                dot.BackColor = Color.FromArgb(47, 211, 138);
                stxt.Text = "Server jalan (milik launcher)";
                ssub.Text = "127.0.0.1:8787 · PID " + owner;
            }
            else
            {
                dot.BackColor = Color.FromArgb(242, 183, 74);
                stxt.Text = "Port dipakai proses eksternal";
                ssub.Text = "127.0.0.1:8787 · PID " + owner + " — Stop-paksa untuk mematikan";
            }
        };
        if (dot.InvokeRequired) dot.BeginInvoke(upd); else upd();
        return null;
    }
}
