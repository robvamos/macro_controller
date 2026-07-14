"""Costruzione della tab principale di gestione macro."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from ui.collapsible_panel import CollapsibleSection


def build_macro_management_tab(
    *,
    tab_control,
    theme: dict,
    macro_manager_config: dict,
    create_new_macro_dialog,
    console_log,
    start_playback_thread,
    stop_current_operation,
    edit_selected_macro,
    delete_selected_macro,
    duplicate_selected_macro,
    concat_macros_dialog,
    emergency_stop_all,
    update_button_states,
    setup_click_context_preview,
    setup_execution_visualizer,
    panel_state: dict,
    on_panel_state_change,
):
    """Crea la tab UI per la gestione macro e restituisce i riferimenti utili."""
    macro_tab = ttk.Frame(tab_control)
    tab_control.add(macro_tab, text="Gestione Macro")

    shell = ttk.Frame(macro_tab, padding=10)
    shell.pack(fill="both", expand=True)
    shell.columnconfigure(0, weight=0)
    shell.columnconfigure(1, weight=3)
    shell.columnconfigure(2, weight=4)
    shell.rowconfigure(1, weight=1)
    shell.rowconfigure(2, weight=1)
    shell.rowconfigure(3, weight=3)

    header = ttk.Frame(shell)
    header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
    header.columnconfigure(0, weight=1)
    header.columnconfigure(1, weight=0)

    shortcuts_text = "⌨️ ESC / Ctrl+Alt+E = Stop Emergenza"
    ttk.Label(
        header,
        text=shortcuts_text,
        foreground="orange",
        font=("Segoe UI", 9),
    ).grid(row=0, column=0, sticky="w")

    loop_frame = ttk.Frame(header)
    loop_frame.grid(row=0, column=1, sticky="e")

    loop_var = tk.BooleanVar(value=False)
    loop_var_checkbox = ttk.Checkbutton(
        loop_frame,
        text="Loop Macro",
        variable=loop_var,
        command=update_button_states,
    )
    loop_var_checkbox.pack(side="left", padx=(0, 10))

    ttk.Label(loop_frame, text="Ritardo Loop (sec):").pack(side="left", padx=(0, 4))
    loop_delay_entry = ttk.Entry(loop_frame, width=8)
    loop_delay_entry.insert(0, str(macro_manager_config["loop_interval_sec_default"]))
    loop_delay_entry.pack(side="left", padx=(0, 12))

    ttk.Label(loop_frame, text="Max Ripetizioni:").pack(side="left", padx=(0, 4))
    max_repetitions_entry = ttk.Entry(loop_frame, width=8)
    max_repetitions_entry.insert(0, "0")
    max_repetitions_entry.pack(side="left")

    actions_section = CollapsibleSection(
        shell,
        title="Comandi",
        expanded=panel_state.get("macro_actions", True),
    )
    actions_section.grid = actions_section.container.grid
    actions_section.grid(row=1, column=0, rowspan=2, sticky="nsw", padx=(0, 10))
    actions_section.toggle_button.config(command=lambda: on_panel_state_change("macro_actions", actions_section))

    actions_body = actions_section.body
    actions_body.columnconfigure(0, weight=1)

    new_macro_button = ttk.Button(
        actions_body,
        text="➕ Nuova Macro",
        command=create_new_macro_dialog,
        style="TButton",
    )
    new_macro_button.pack(fill="x", pady=3)

    record_button = ttk.Button(
        actions_body,
        text="● Registra",
        command=lambda: console_log("Usa 'Nuova Macro' per avviare una registrazione.", level="INFO"),
        style="TButton",
    )
    record_button.pack(fill="x", pady=3)
    record_button.config(state=tk.DISABLED)

    play_button = ttk.Button(actions_body, text="▶ Play", command=start_playback_thread, style="TButton")
    play_button.pack(fill="x", pady=3)

    stop_button = ttk.Button(actions_body, text="■ Stop", command=stop_current_operation, style="TButton")
    stop_button.pack(fill="x", pady=3)

    emergency_stop_button = ttk.Button(
        actions_body,
        text="■ Stop",
        command=emergency_stop_all,
        style="Emergency.TButton",
    )
    emergency_stop_button.pack(fill="x", pady=3)

    edit_button = ttk.Button(actions_body, text="✏️ Modifica", command=edit_selected_macro, style="TButton")
    edit_button.pack(fill="x", pady=3)

    delete_button = ttk.Button(actions_body, text="🗑️ Elimina", command=delete_selected_macro, style="TButton")
    delete_button.pack(fill="x", pady=3)

    duplicate_button = ttk.Button(
        actions_body,
        text="📋 Duplica",
        command=duplicate_selected_macro,
        style="TButton",
    )
    duplicate_button.pack(fill="x", pady=3)

    concat_button = ttk.Button(
        actions_body,
        text="🔗 Concatena",
        command=concat_macros_dialog,
        style="TButton",
    )
    concat_button.pack(fill="x", pady=3)

    details_section = CollapsibleSection(
        shell,
        title="Dettagli Macro",
        expanded=panel_state.get("macro_details", True),
    )
    details_section.grid = details_section.container.grid
    details_section.grid(row=1, column=1, sticky="nsew", padx=(0, 8), pady=(0, 8))
    details_section.toggle_button.config(command=lambda: on_panel_state_change("macro_details", details_section))

    details_text = scrolledtext.ScrolledText(
        details_section.body,
        wrap="word",
        height=8,
        font=(theme["font_family"], theme["font_size_small"]),
        bg=theme["border_color"],
        fg=theme["text_color"],
        insertbackground=theme["text_color"],
    )
    details_text.pack(fill="both", expand=True)
    details_text.config(state=tk.DISABLED)

    execution_section = CollapsibleSection(
        shell,
        title="Esecuzione",
        expanded=panel_state.get("macro_execution", True),
    )
    execution_section.grid = execution_section.container.grid
    execution_section.grid(row=1, column=2, rowspan=3, sticky="nsew")
    execution_section.toggle_button.config(command=lambda: on_panel_state_change("macro_execution", execution_section))
    setup_execution_visualizer(execution_section.body)

    console_section = CollapsibleSection(
        shell,
        title="Console Log",
        expanded=panel_state.get("console", True),
    )
    console_section.grid = console_section.container.grid
    console_section.grid(row=2, column=1, sticky="nsew", padx=(0, 8), pady=(0, 8))
    console_section.toggle_button.config(command=lambda: on_panel_state_change("console", console_section))

    list_section = CollapsibleSection(
        shell,
        title="Macro Disponibili",
        expanded=panel_state.get("macro_list", True),
    )
    list_section.grid = list_section.container.grid
    list_section.grid(row=3, column=1, sticky="nsew", padx=(0, 8))
    list_section.toggle_button.config(command=lambda: on_panel_state_change("macro_list", list_section))
    list_section.body.columnconfigure(0, weight=1)
    list_section.body.rowconfigure(0, weight=1)

    columns = ("Nome", "Durata", "Eseguibile", "Creazione")
    macro_list_tree = ttk.Treeview(
        list_section.body,
        columns=columns,
        show="headings",
        height=macro_manager_config["listbox_height"],
    )
    macro_list_tree.heading("Nome", text="Nome")
    macro_list_tree.heading("Durata", text="Durata (s)")
    macro_list_tree.heading("Eseguibile", text="Eseguibile")
    macro_list_tree.heading("Creazione", text="Creazione")
    macro_list_tree.column("Nome", width=220)
    macro_list_tree.column("Durata", width=100, anchor="center")
    macro_list_tree.column("Eseguibile", width=150)
    macro_list_tree.column("Creazione", width=150)
    macro_list_tree.grid(row=0, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(list_section.body, orient="vertical", command=macro_list_tree.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    macro_list_tree.configure(yscrollcommand=scrollbar.set)

    return {
        "macro_tab": macro_tab,
        "new_macro_button": new_macro_button,
        "record_button": record_button,
        "play_button": play_button,
        "stop_button": stop_button,
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
        "console_parent": console_section.body,
    }
