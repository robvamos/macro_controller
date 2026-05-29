"""Tab UI per la gestione dei campioni audio di calibrazione."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from ui.tooltips import attach_tooltip


def build_audio_samples_tab(
    *,
    parent,
    theme: dict,
    browse_audio_source,
    import_audio_selection,
    split_selected_audio_sample,
    compose_selected_audio_samples,
    refresh_audio_samples_list,
    on_audio_sample_select,
):
    """Crea la tab per importare e gestire campioni audio."""
    audio_tab = parent

    controls_frame = ttk.LabelFrame(audio_tab, text="Importa Da Audio", padding="10")
    controls_frame.pack(fill="x", pady=10)

    source_path_var = tk.StringVar(value="Nessun file selezionato")
    source_duration_var = tk.StringVar(value="Durata sorgente: -")

    source_row = ttk.Frame(controls_frame)
    source_row.pack(fill="x", pady=5)
    browse_button = ttk.Button(source_row, text="Carica Audio", command=browse_audio_source, style="TButton")
    browse_button.pack(side="left", padx=(0, 8))
    attach_tooltip(browse_button, "Importa un file audio esterno da cui ritagliare un campione.")
    ttk.Label(source_row, textvariable=source_path_var).pack(side="left", fill="x", expand=True)

    duration_row = ttk.Frame(controls_frame)
    duration_row.pack(fill="x", pady=(0, 8))
    ttk.Label(duration_row, textvariable=source_duration_var).pack(side="left")

    selection_row = ttk.Frame(controls_frame)
    selection_row.pack(fill="x", pady=5)

    ttk.Label(selection_row, text="Nome campione:").pack(side="left", padx=(0, 4))
    sample_name_entry = ttk.Entry(selection_row, width=24)
    sample_name_entry.insert(0, "uploaded_sample")
    sample_name_entry.pack(side="left", padx=(0, 10))
    attach_tooltip(sample_name_entry, "Nome del nuovo campione che verrà salvato in libreria.")

    ttk.Label(selection_row, text="Inizio (s):").pack(side="left", padx=(0, 4))
    start_entry = ttk.Entry(selection_row, width=10)
    start_entry.insert(0, "0")
    start_entry.pack(side="left", padx=(0, 10))
    attach_tooltip(start_entry, "Secondo iniziale della porzione da estrarre.")

    ttk.Label(selection_row, text="Fine (s):").pack(side="left", padx=(0, 4))
    end_entry = ttk.Entry(selection_row, width=10)
    end_entry.insert(0, "30")
    end_entry.pack(side="left", padx=(0, 10))
    attach_tooltip(end_entry, "Secondo finale della porzione da estrarre.")

    save_selection_button = ttk.Button(
        selection_row,
        text="Salva Selezione",
        command=import_audio_selection,
        style="TButton",
    )
    save_selection_button.pack(side="left")
    attach_tooltip(save_selection_button, "Salva il ritaglio come nuovo campione MP3/WAV con metadata.")

    composition_frame = ttk.LabelFrame(audio_tab, text="Composizione E Scomposizione", padding="10")
    composition_frame.pack(fill="x", pady=(0, 10))

    compose_row = ttk.Frame(composition_frame)
    compose_row.pack(fill="x", pady=5)

    ttk.Label(compose_row, text="Song di test:").pack(side="left", padx=(0, 4))
    composed_name_entry = ttk.Entry(compose_row, width=24)
    composed_name_entry.insert(0, "test_song_learning")
    composed_name_entry.pack(side="left", padx=(0, 10))
    attach_tooltip(composed_name_entry, "Nome della song di test composta da più campioni.")

    ttk.Label(compose_row, text="Gap (s):").pack(side="left", padx=(0, 4))
    compose_gap_entry = ttk.Entry(compose_row, width=8)
    compose_gap_entry.insert(0, "0")
    compose_gap_entry.pack(side="left", padx=(0, 10))
    attach_tooltip(compose_gap_entry, "Pausa in secondi tra un campione e il successivo.")

    compose_button = ttk.Button(
        compose_row,
        text="Componi Da Selezione",
        command=compose_selected_audio_samples,
        style="TButton",
    )
    compose_button.pack(side="left", padx=(0, 8))
    attach_tooltip(compose_button, "Unisce i campioni selezionati nell'ordine mostrato in lista.")

    split_button = ttk.Button(
        compose_row,
        text="Scomponi Campione",
        command=split_selected_audio_sample,
        style="TButton",
    )
    split_button.pack(side="left")
    attach_tooltip(split_button, "Divide il campione selezionato in più blocchi usando i segmenti noti del ground truth.")

    objective_row = ttk.Frame(composition_frame)
    objective_row.pack(fill="x", pady=(5, 0))
    ttk.Label(objective_row, text="Focus learning:").pack(side="left", padx=(0, 4))
    learning_objective_entry = ttk.Entry(objective_row, width=80)
    learning_objective_entry.insert(
        0,
        "Riconoscere tempo, fase della battuta, ordine dei quarti e identificare il beat 1.",
    )
    learning_objective_entry.pack(side="left", fill="x", expand=True)
    attach_tooltip(learning_objective_entry, "Descrive l'obiettivo di learning associato alla song di test composta.")

    library_frame = ttk.Frame(audio_tab)
    library_frame.pack(fill="both", expand=True, pady=10)
    library_frame.columnconfigure(0, weight=3)
    library_frame.columnconfigure(1, weight=2)

    list_frame = ttk.LabelFrame(library_frame, text="Campioni Disponibili", padding="10")
    list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

    list_toolbar = ttk.Frame(list_frame)
    list_toolbar.pack(fill="x", pady=(0, 8))
    refresh_button = ttk.Button(list_toolbar, text="Aggiorna Lista", command=refresh_audio_samples_list, style="TButton")
    refresh_button.pack(side="left")
    attach_tooltip(refresh_button, "Rilegge l'indice dei campioni disponibili.")

    columns = ("Nome", "Tipo", "Durata", "Origine")
    audio_samples_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10, selectmode="extended")
    for column_name, heading_text, width in (
        ("Nome", "Nome", 180),
        ("Tipo", "Tipo", 140),
        ("Durata", "Durata (s)", 90),
        ("Origine", "Origine", 220),
    ):
        audio_samples_tree.heading(column_name, text=heading_text)
        audio_samples_tree.column(column_name, width=width, anchor="center" if column_name == "Durata" else "w")
    audio_samples_tree.pack(side="left", fill="both", expand=True)
    audio_samples_tree.bind("<<TreeviewSelect>>", lambda event: on_audio_sample_select())

    scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=audio_samples_tree.yview)
    scrollbar.pack(side="right", fill="y")
    audio_samples_tree.configure(yscrollcommand=scrollbar.set)

    details_frame = ttk.LabelFrame(library_frame, text="Dettagli Campione", padding="10")
    details_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

    details_text = scrolledtext.ScrolledText(
        details_frame,
        wrap="word",
        height=16,
        font=(theme["font_family"], theme["font_size_small"]),
        bg=theme["border_color"],
        fg=theme["text_color"],
        insertbackground=theme["text_color"],
    )
    details_text.pack(fill="both", expand=True)
    details_text.config(state=tk.DISABLED)

    return {
        "source_path_var": source_path_var,
        "source_duration_var": source_duration_var,
        "sample_name_entry": sample_name_entry,
        "start_entry": start_entry,
        "end_entry": end_entry,
        "composed_name_entry": composed_name_entry,
        "compose_gap_entry": compose_gap_entry,
        "learning_objective_entry": learning_objective_entry,
        "audio_samples_tree": audio_samples_tree,
        "audio_sample_details_text": details_text,
    }
