"""Vista dedicata a preprocessing, BPM detection e griglia di learning."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from ui.collapsible_panel import CollapsibleSection
from ui.tooltips import attach_tooltip


def build_learning_lab_tab(
    *,
    parent,
    theme: dict,
    run_preprocessing_analysis,
    create_learning_grid,
    record_learning_observation,
    reset_learning_sync,
    apply_learning_feedback,
    save_configuration_evaluation,
):
    learning_tab = parent

    sample_name_var = tk.StringVar()
    dominant_bpm_var = tk.StringVar(value="BPM: -")
    stability_var = tk.StringVar(value="Stabilità: -")
    pattern_var = tk.StringVar(value="Pattern: -")
    readiness_var = tk.StringVar(value="Readiness: -")
    status_var = tk.StringVar(value="Stato learning: idle")
    target_lock_var = tk.StringVar(value="Lock: 0%")
    beat_one_var = tk.StringVar(value="Beat 1: 0%")
    resync_var = tk.StringVar(value="Resync: 0")

    pipeline_section = CollapsibleSection(learning_tab, title="Pipeline Preprocessing / BPM", expanded=True)
    pipeline_section.pack(fill="x", pady=10)

    sample_row = ttk.Frame(pipeline_section.body)
    sample_row.pack(fill="x", pady=5)
    ttk.Label(sample_row, text="Campione:").pack(side="left", padx=(0, 4))
    sample_combo = ttk.Combobox(sample_row, textvariable=sample_name_var, state="readonly", width=40)
    sample_combo.pack(side="left", padx=(0, 10))
    attach_tooltip(sample_combo, "Scegli il campione da analizzare per preprocessing e BPM detection.")

    analyze_button = ttk.Button(sample_row, text="Analizza BPM", command=run_preprocessing_analysis, style="TButton")
    analyze_button.pack(side="left", padx=(0, 8))
    attach_tooltip(analyze_button, "Esegue preprocessing, estrae envelope e stima il BPM per finestre temporali.")

    create_grid_button = ttk.Button(sample_row, text="Crea Griglia", command=create_learning_grid, style="TButton")
    create_grid_button.pack(side="left")
    attach_tooltip(create_grid_button, "Crea la griglia di learning dai segmenti rilevati o dal ground truth disponibile.")

    metrics_row = ttk.Frame(pipeline_section.body)
    metrics_row.pack(fill="x", pady=(8, 0))
    for value_var in (dominant_bpm_var, stability_var, pattern_var, readiness_var, status_var, target_lock_var, beat_one_var, resync_var):
        ttk.Label(metrics_row, textvariable=value_var).pack(side="left", padx=(0, 12))

    evaluation_section = CollapsibleSection(learning_tab, title="Valutazione Configurazione", expanded=True)
    evaluation_section.pack(fill="x", pady=(0, 10))

    evaluation_prompt_var = tk.StringVar(value="Dopo ogni analisi significativa, salva una valutazione della configurazione.")
    evaluation_recommendation_var = tk.StringVar(value="Storico: nessuna valutazione.")
    rating_var = tk.StringVar(value="buono")

    ttk.Label(evaluation_section.body, textvariable=evaluation_prompt_var).pack(fill="x", pady=(0, 6))

    evaluation_row = ttk.Frame(evaluation_section.body)
    evaluation_row.pack(fill="x", pady=4)
    ttk.Label(evaluation_row, text="Valutazione:").pack(side="left", padx=(0, 4))
    rating_combo = ttk.Combobox(
        evaluation_row,
        textvariable=rating_var,
        values=["scarso", "debole", "buono", "ottimo"],
        state="readonly",
        width=12,
    )
    rating_combo.pack(side="left", padx=(0, 10))
    attach_tooltip(rating_combo, "Valuta la bontà della configurazione corrente dopo una prova significativa.")

    evaluation_note_entry = ttk.Entry(evaluation_row, width=80)
    evaluation_note_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
    attach_tooltip(evaluation_note_entry, "Nota breve: cosa ha funzionato bene o male in questa configurazione.")

    save_evaluation_button = ttk.Button(
        evaluation_row,
        text="Salva Valutazione",
        command=save_configuration_evaluation,
        style="TButton",
    )
    save_evaluation_button.pack(side="left")
    attach_tooltip(save_evaluation_button, "Salva la valutazione della configurazione per far imparare il sistema.")

    ttk.Label(evaluation_section.body, textvariable=evaluation_recommendation_var).pack(fill="x", pady=(6, 0))

    details_section = CollapsibleSection(learning_tab, title="Vista Intelligente", expanded=True)
    details_section.pack(fill="both", expand=True, pady=(0, 10))

    details_text = scrolledtext.ScrolledText(
        details_section.body,
        wrap="word",
        height=16,
        font=(theme["font_family"], theme["font_size_small"]),
        bg=theme["border_color"],
        fg=theme["text_color"],
        insertbackground=theme["text_color"],
    )
    details_text.pack(fill="both", expand=True)
    details_text.config(state=tk.DISABLED)

    advanced_section = CollapsibleSection(learning_tab, title="Controlli Manuali Avanzati", expanded=False)
    advanced_section.pack(fill="x", pady=(0, 10))

    hint_label = ttk.Label(
        advanced_section.body,
        text="Questa sezione resta compressa di default: il focus ora è su preprocessing e BPM detection.",
    )
    hint_label.pack(fill="x", pady=(0, 8))

    observation_frame = ttk.Frame(advanced_section.body)
    observation_frame.pack(fill="x", pady=5)

    offset_var = tk.StringVar(value="0")
    confidence_var = tk.StringVar(value="0.8")
    beat_var = tk.StringVar(value="1")

    ttk.Label(observation_frame, text="Offset (ms):").pack(side="left", padx=(0, 4))
    offset_entry = ttk.Entry(observation_frame, textvariable=offset_var, width=10)
    offset_entry.pack(side="left", padx=(0, 10))
    attach_tooltip(offset_entry, "Negativo se l'aggancio arriva in anticipo, positivo se arriva in ritardo.")

    ttk.Label(observation_frame, text="Confidenza:").pack(side="left", padx=(0, 4))
    confidence_entry = ttk.Entry(observation_frame, textvariable=confidence_var, width=10)
    confidence_entry.pack(side="left", padx=(0, 10))

    ttk.Label(observation_frame, text="Quarto rilevato:").pack(side="left", padx=(0, 4))
    beat_combo = ttk.Combobox(observation_frame, textvariable=beat_var, values=["1", "2", "3", "4"], state="readonly", width=5)
    beat_combo.pack(side="left", padx=(0, 10))

    register_button = ttk.Button(observation_frame, text="Registra Battuta", command=record_learning_observation, style="TButton")
    register_button.pack(side="left", padx=(0, 8))

    reset_button = ttk.Button(observation_frame, text="Reset Sync", command=reset_learning_sync, style="TButton")
    reset_button.pack(side="left")

    feedback_frame = ttk.Frame(advanced_section.body)
    feedback_frame.pack(fill="x", pady=(8, 0))

    for text, key, tip in (
        ("Buon Lock", "good_lock", "Il sistema si è accordato in fretta senza sbilanciarsi."),
        ("Troppo Lento", "too_slow", "La correzione è arrivata tardi."),
        ("Troppo Veloce", "too_fast", "La correzione è scattata troppo presto."),
        ("Errore Sul Beat 1", "late_bar_start", "L'inizio battuta non è stato riconosciuto bene."),
    ):
        button = ttk.Button(
            feedback_frame,
            text=text,
            command=lambda feedback_key=key: apply_learning_feedback(feedback_key),
            style="TButton",
        )
        button.pack(side="left", padx=(0, 8))
        attach_tooltip(button, tip)

    return {
        "sample_name_var": sample_name_var,
        "sample_combo": sample_combo,
        "dominant_bpm_var": dominant_bpm_var,
        "stability_var": stability_var,
        "pattern_var": pattern_var,
        "readiness_var": readiness_var,
        "status_var": status_var,
        "target_lock_var": target_lock_var,
        "beat_one_var": beat_one_var,
        "resync_var": resync_var,
        "evaluation_prompt_var": evaluation_prompt_var,
        "evaluation_recommendation_var": evaluation_recommendation_var,
        "rating_var": rating_var,
        "evaluation_note_entry": evaluation_note_entry,
        "offset_var": offset_var,
        "confidence_var": confidence_var,
        "beat_var": beat_var,
        "details_text": details_text,
    }
