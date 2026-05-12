"""Costruzione della tab principale di gestione macro."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk


def build_macro_management_tab(
    *,
    tab_control,
    theme: dict,
    macro_manager_config: dict,
    create_new_macro_dialog,
    console_log,
    start_playback_thread,
    stop_current_operation,
    rerecord_selected_macro,
    edit_selected_macro,
    delete_selected_macro,
    duplicate_selected_macro,
    concat_macros_dialog,
    emergency_stop_all,
    update_button_states,
    setup_execution_visualizer,
):
    """Crea la tab UI per la gestione macro e restituisce i riferimenti utili."""
    macro_tab = ttk.Frame(tab_control)
    tab_control.add(macro_tab, text="Gestione Macro")

    macro_management_frame = ttk.LabelFrame(macro_tab, padding="10")
    macro_management_frame.pack(fill="x", pady=10)

    action_buttons_frame = ttk.Frame(macro_management_frame)
    action_buttons_frame.pack(fill="x", pady=5)

    new_macro_button = ttk.Button(
        action_buttons_frame,
        text="➕ Nuova Macro",
        command=create_new_macro_dialog,
        style="TButton",
    )
    new_macro_button.pack(side="left", padx=5)

    record_button = ttk.Button(
        action_buttons_frame,
        text="⏺️ Registra",
        command=lambda: console_log("Usa 'Nuova Macro' per avviare una registrazione.", level="INFO"),
        style="TButton",
    )
    record_button.pack(side="left", padx=5)
    record_button.config(state=tk.DISABLED)

    play_button = ttk.Button(action_buttons_frame, text="▶️ Riproduci", command=start_playback_thread, style="TButton")
    play_button.pack(side="left", padx=5)

    stop_button = ttk.Button(action_buttons_frame, text="⏹️ Ferma", command=stop_current_operation, style="TButton")
    stop_button.pack(side="left", padx=5)

    rerecord_button = ttk.Button(
        action_buttons_frame,
        text="🔄 Re-registra",
        command=rerecord_selected_macro,
        style="TButton",
    )
    rerecord_button.pack(side="left", padx=5)

    edit_button = ttk.Button(action_buttons_frame, text="✏️ Modifica", command=edit_selected_macro, style="TButton")
    edit_button.pack(side="left", padx=5)

    delete_button = ttk.Button(action_buttons_frame, text="🗑️ Elimina", command=delete_selected_macro, style="TButton")
    delete_button.pack(side="left", padx=5)

    duplicate_button = ttk.Button(
        action_buttons_frame,
        text="📋 Duplica",
        command=duplicate_selected_macro,
        style="TButton",
    )
    duplicate_button.pack(side="left", padx=5)

    concat_button = ttk.Button(
        action_buttons_frame,
        text="🔗 Concatena Macro",
        command=concat_macros_dialog,
        style="TButton",
    )
    concat_button.pack(side="left", padx=5)

    emergency_frame = ttk.Frame(macro_management_frame)
    emergency_frame.pack(fill="x", pady=5)

    emergency_label = ttk.Label(
        emergency_frame,
        text="🚨 CONTROLLO EMERGENZA:",
        font=("Segoe UI", 10, "bold"),
        foreground="red",
    )
    emergency_label.pack(side="left", padx=5)

    emergency_stop_button = ttk.Button(
        emergency_frame,
        text="STOP EMERGENZA",
        command=emergency_stop_all,
        style="Emergency.TButton",
    )
    emergency_stop_button.pack(side="left", padx=5)

    shortcuts_info_frame = ttk.Frame(macro_management_frame)
    shortcuts_info_frame.pack(fill="x", pady=5)

    shortcuts_text = (
        "⌨️ Scorciatoie: ESC = Stop Emergenza | Ctrl+Alt+S = Stop Normale | "
        "Ctrl+Alt+E = Stop Emergenza | 🚨 Pulsante STOP EMERGENZA nella sezione dedicata"
    )
    shortcuts_label = ttk.Label(
        shortcuts_info_frame,
        text=shortcuts_text,
        foreground="orange",
        font=("Segoe UI", 9),
    )
    shortcuts_label.pack(side="left", padx=5)

    loop_options_frame = ttk.Frame(macro_management_frame)
    loop_options_frame.pack(fill="x", pady=5)

    loop_var = tk.BooleanVar(value=False)
    loop_var_checkbox = ttk.Checkbutton(
        loop_options_frame,
        text="Loop Macro",
        variable=loop_var,
        command=update_button_states,
    )
    loop_var_checkbox.pack(side="left", padx=5)

    ttk.Label(loop_options_frame, text="Ritardo Loop (sec):").pack(side="left", padx=(15, 2))
    loop_delay_entry = ttk.Entry(loop_options_frame, width=10)
    loop_delay_entry.insert(0, str(macro_manager_config["loop_interval_sec_default"]))
    loop_delay_entry.pack(side="left", padx=2)

    ttk.Label(loop_options_frame, text="Max Ripetizioni:").pack(side="left", padx=(15, 2))
    max_repetitions_entry = ttk.Entry(loop_options_frame, width=10)
    max_repetitions_entry.insert(0, "0")
    max_repetitions_entry.pack(side="left", padx=2)

    macro_content_frame = ttk.Frame(macro_tab)
    macro_content_frame.pack(fill="both", expand=True, pady=10)
    macro_content_frame.columnconfigure(0, weight=2)
    macro_content_frame.columnconfigure(1, weight=1)

    macro_list_frame = ttk.LabelFrame(macro_content_frame, text="Macro Disponibili", padding="10")
    macro_list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

    columns = ("Nome", "Durata", "Eseguibile", "Creazione")
    macro_list_tree = ttk.Treeview(
        macro_list_frame,
        columns=columns,
        show="headings",
        height=macro_manager_config["listbox_height"],
    )
    macro_list_tree.heading("Nome", text="Nome")
    macro_list_tree.heading("Durata", text="Durata (s)")
    macro_list_tree.heading("Eseguibile", text="Eseguibile")
    macro_list_tree.heading("Creazione", text="Creazione")
    macro_list_tree.column("Nome", width=200)
    macro_list_tree.column("Durata", width=100, anchor="center")
    macro_list_tree.column("Eseguibile", width=150)
    macro_list_tree.column("Creazione", width=150)
    macro_list_tree.pack(side="left", fill="both", expand=True)

    scrollbar = ttk.Scrollbar(macro_list_frame, orient="vertical", command=macro_list_tree.yview)
    scrollbar.pack(side="right", fill="y")
    macro_list_tree.configure(yscrollcommand=scrollbar.set)

    macro_details_frame = ttk.LabelFrame(macro_content_frame, text="Dettagli Macro", padding="10")
    macro_details_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

    details_notebook = ttk.Notebook(macro_details_frame)
    details_notebook.pack(fill="both", expand=True)

    details_tab = ttk.Frame(details_notebook)
    details_notebook.add(details_tab, text="Dettagli")

    details_text = scrolledtext.ScrolledText(
        details_tab,
        wrap="word",
        height=15,
        font=(theme["font_family"], theme["font_size_small"]),
        bg=theme["border_color"],
        fg=theme["text_color"],
        insertbackground=theme["text_color"],
    )
    details_text.pack(fill="both", expand=True)
    details_text.config(state=tk.DISABLED)

    execution_visualizer_tab = ttk.Frame(details_notebook)
    details_notebook.add(execution_visualizer_tab, text="🎬 Esecuzione")
    setup_execution_visualizer(execution_visualizer_tab)

    return {
        "macro_tab": macro_tab,
        "new_macro_button": new_macro_button,
        "record_button": record_button,
        "play_button": play_button,
        "stop_button": stop_button,
        "rerecord_button": rerecord_button,
        "edit_button": edit_button,
        "delete_button": delete_button,
        "duplicate_button": duplicate_button,
        "concat_button": concat_button,
        "emergency_stop_button": emergency_stop_button,
        "loop_var": loop_var,
        "loop_var_checkbox": loop_var_checkbox,
        "loop_delay_entry": loop_delay_entry,
        "max_repetitions_entry": max_repetitions_entry,
        "macro_list_tree": macro_list_tree,
        "macro_details_text": details_text,
    }
