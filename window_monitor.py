import tkinter as tk
from tkinter import ttk
import threading
import time
import win32gui
import win32process
import psutil
from datetime import datetime

class WindowMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Window Monitor")
        self.root.geometry("900x400")
        
        self.monitoring = False
        self.monitor_thread = None

        # UI
        self.status_label = ttk.Label(root, text="Premi Start per monitorare la finestra attiva", font=("Segoe UI", 12))
        self.status_label.pack(pady=10)

        button_frame = ttk.Frame(root)
        button_frame.pack(pady=5)

        self.start_button = ttk.Button(button_frame, text="Start", command=self.start_monitoring)
        self.start_button.grid(row=0, column=0, padx=10)
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=10)

        # Area di testo scrollabile
        text_frame = ttk.Frame(root)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.info_text = tk.Text(text_frame, height=16, width=130, state=tk.DISABLED, font=("Consolas", 10), wrap=tk.NONE)
        self.info_text.pack(side=tk.LEFT, fill="both", expand=True)
        self.scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.info_text.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill="y")
        self.info_text.config(yscrollcommand=self.scrollbar.set)

    def start_monitoring(self):
        if not self.monitoring:
            self.monitoring = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_label.config(text="Monitoraggio in corso...")
            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete(1.0, tk.END)
            self.info_text.config(state=tk.DISABLED)
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()

    def stop_monitoring(self):
        self.monitoring = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Monitoraggio fermato.")

    def monitor_loop(self):
        last_hwnd = None
        while self.monitoring:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd != last_hwnd:
                last_hwnd = hwnd
                window_title = win32gui.GetWindowText(hwnd)
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc = psutil.Process(pid)
                    exe_name = proc.name()
                    exe_path = proc.exe()
                except Exception as e:
                    exe_name = f"Errore: {e}"
                    exe_path = "-"
                now = datetime.now().strftime("%H:%M:%S")
                # Formato compatto: [HH:MM:SS] Titolo | Eseguibile | HWND | Percorso
                info = f"[{now}] {window_title} | {exe_name} | HWND: {hwnd} | {exe_path}\n"
                self.append_info(info)
            time.sleep(0.2)

    def append_info(self, info):
        def update():
            self.info_text.config(state=tk.NORMAL)
            self.info_text.insert(tk.END, info)
            self.info_text.see(tk.END)
            self.info_text.config(state=tk.DISABLED)
        self.root.after(0, update)

if __name__ == "__main__":
    root = tk.Tk()
    app = WindowMonitorApp(root)
    root.mainloop() 