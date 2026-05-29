"""Helper UI per console e barra di stato."""

import time
import tkinter as tk

from macro_config import normalize_log_level


SEARCHING_COLOR = "#f7d358"
FOUND_COLOR = "#50fa7b"


def append_console_message(console_widget, message, level="INFO", fallback_print=print):
    """Scrive un messaggio nella console testuale o usa il fallback."""
    normalized_level = normalize_log_level(level)
    if console_widget and console_widget.winfo_exists():
        try:
            timestamp = time.strftime("[%H:%M:%S]")
            console_widget.config(state=tk.NORMAL)
            console_widget.insert(tk.END, f"{timestamp} [{normalized_level}] {message}\n")
            console_widget.see(tk.END)
            console_widget.config(state=tk.DISABLED)
            return
        except tk.TclError:
            pass

    fallback_print(f"[{normalized_level}] {message}")


def apply_status_indicator_state(
    *,
    status_bar,
    recording_indicator_button,
    playing_indicator_button,
    focus_monitor_indicator,
    message,
    indicator,
    theme,
    focus_monitor_active,
    recording_timer_active,
    recording_duration,
    start_recording_timer,
):
    """Applica lo stato visivo della barra di stato e degli indicatori."""
    status_bar.config(text=message)
    idle_color = theme["status_idle_color"]
    recording_color = theme["status_recording_color"]
    playing_color = theme["status_running_color"]

    recording_indicator_button.pack_forget()
    playing_indicator_button.pack_forget()
    focus_monitor_indicator.pack_forget()

    if indicator == "recording":
        recording_indicator_button.config(text="🔴 REGISTRAZIONE", bg="red")
        recording_indicator_button.pack(side="left", padx=(0, 5))
        status_bar.config(background=recording_color)
        if not recording_timer_active and recording_duration > 0:
            start_recording_timer(recording_duration)
    elif indicator == "playing":
        playing_indicator_button.config(text="🟢 RIPRODUZIONE", bg="green")
        playing_indicator_button.pack(side="left", padx=(0, 5))
        status_bar.config(background=playing_color)
    elif indicator == "searching":
        playing_indicator_button.config(text="🟡 CERCA FINESTRA", bg=SEARCHING_COLOR)
        playing_indicator_button.pack(side="left", padx=(0, 5))
        status_bar.config(background=SEARCHING_COLOR)
    elif indicator == "found":
        playing_indicator_button.config(text="✅ FINESTRA TROVATA", bg=FOUND_COLOR)
        playing_indicator_button.pack(side="left", padx=(0, 5))
        status_bar.config(background=FOUND_COLOR)
    else:
        status_bar.config(background=idle_color)

    if focus_monitor_active:
        focus_monitor_indicator.config(text="🔍 MONITORAGGIO", bg="blue")
        focus_monitor_indicator.pack(side="left", padx=(0, 5))
