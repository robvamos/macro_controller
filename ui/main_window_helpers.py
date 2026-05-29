"""Helper per console, status bar e binding della finestra principale."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk


def build_log_console(parent, *, font_family: str, font_size_small: int, border_color: str, text_color: str):
    """Crea il riquadro console e restituisce il widget testuale."""
    console_frame = ttk.LabelFrame(parent, text="Log Console", padding="10")
    console_frame.pack(fill="both", expand=True, pady=10)

    console_text = scrolledtext.ScrolledText(
        console_frame,
        wrap="word",
        height=10,
        font=(font_family, font_size_small),
        bg=border_color,
        fg=text_color,
        insertbackground=text_color,
    )
    console_text.pack(fill="both", expand=True)
    console_text.config(state=tk.DISABLED)
    return console_text


def build_status_bar(root_window, *, bg_color: str, text_color: str):
    """Crea la status bar e i relativi indicatori."""
    status_bar_frame = ttk.Frame(root_window)
    status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)

    status_bar = ttk.Label(status_bar_frame, text="Pronto", anchor="w", background=bg_color, foreground=text_color)
    status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

    recording_indicator_button = tk.Button(
        status_bar_frame,
        text="🔴 REGISTRAZIONE",
        bg="red",
        fg="white",
        font=("Arial", 10, "bold"),
        relief="solid",
        bd=1,
        width=15,
    )
    playing_indicator_button = tk.Button(
        status_bar_frame,
        text="🟢 RIPRODUZIONE",
        bg="green",
        fg="white",
        font=("Arial", 10, "bold"),
        relief="solid",
        bd=1,
        width=15,
    )
    focus_monitor_indicator = tk.Button(
        status_bar_frame,
        text="🔍 MONITORAGGIO",
        bg="blue",
        fg="white",
        font=("Arial", 10, "bold"),
        relief="solid",
        bd=1,
        width=15,
    )
    recording_timer_label = tk.Label(
        status_bar_frame,
        text="⏱️ 00:00",
        bg="red",
        fg="white",
        font=("Segoe UI", 16, "bold"),
        relief="solid",
        bd=2,
        padx=10,
        pady=5,
    )

    return {
        "status_bar": status_bar,
        "recording_indicator_button": recording_indicator_button,
        "playing_indicator_button": playing_indicator_button,
        "focus_monitor_indicator": focus_monitor_indicator,
        "recording_timer_label": recording_timer_label,
    }


def bind_main_window_events(
    root_window,
    *,
    macro_list_tree,
    update_button_states,
    update_macro_details,
    open_selected_macro_action,
    on_window_focus_in,
    on_window_focus_out,
    on_window_destroy,
    stop_current_operation,
    emergency_stop_all,
):
    """Registra i binding principali della finestra."""
    macro_list_tree.bind("<<TreeviewSelect>>", lambda event: (update_button_states(), update_macro_details()))
    macro_list_tree.bind("<Double-Button-1>", lambda event: open_selected_macro_action())

    root_window.bind("<FocusIn>", lambda event: on_window_focus_in())
    root_window.bind("<FocusOut>", lambda event: on_window_focus_out())
    root_window.bind("<Destroy>", on_window_destroy)

    root_window.bind("<Control-Alt-s>", lambda event: emergency_stop_all())
    root_window.bind("<Control-Alt-e>", lambda event: emergency_stop_all())
    root_window.bind("<Escape>", lambda event: emergency_stop_all())
