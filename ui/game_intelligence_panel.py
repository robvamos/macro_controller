"""Tab consultiva per l'intelligence semantica di Doomsday."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from services.game_intelligence_preview_service import (
    build_game_plan_preview,
    format_game_plan_summary,
    format_plan_step_details,
    plan_step_rows,
)


def _set_text(widget: tk.Text, value: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", tk.END)
    widget.insert(tk.END, value)
    widget.configure(state="disabled")


def build_game_intelligence_tab(parent, *, console_log=None):
    """Costruisce una preview read-only: nessun passo viene eseguito dalla tab."""
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(2, weight=1)
    parent.rowconfigure(3, weight=1)

    header = ttk.Frame(parent, padding=(10, 10, 10, 4))
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(1, weight=1)
    ttk.Label(header, text="Piano di Gioco", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(header, text="Analisi consultiva", anchor="e").grid(row=0, column=1, sticky="e")

    input_frame = ttk.LabelFrame(parent, text="Obiettivo", padding=8)
    input_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 6))
    input_frame.columnconfigure(1, weight=1)
    ttk.Label(input_frame, text="Obiettivo").grid(row=0, column=0, sticky="w", padx=(0, 6))
    goal_var = tk.StringVar()
    goal_entry = ttk.Entry(input_frame, textvariable=goal_var)
    goal_entry.grid(row=0, column=1, sticky="ew")
    ttk.Label(input_frame, text="Versione").grid(row=0, column=2, sticky="w", padx=(10, 6))
    version_var = tk.StringVar()
    ttk.Entry(input_frame, textvariable=version_var, width=12).grid(row=0, column=3, sticky="ew")

    facts_label = ttk.Label(input_frame, text="Fatti JSON")
    facts_label.grid(row=1, column=0, sticky="nw", pady=(8, 0), padx=(0, 6))
    facts_text = tk.Text(input_frame, height=3, wrap="word", borderwidth=1, relief="solid")
    facts_text.grid(row=1, column=1, columnspan=3, sticky="ew", pady=(8, 0))

    content = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
    content.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 6))
    steps_frame = ttk.LabelFrame(content, text="Passi", padding=6)
    summary_frame = ttk.LabelFrame(content, text="Lettura", padding=6)
    content.add(steps_frame, weight=3)
    content.add(summary_frame, weight=2)
    steps_frame.columnconfigure(0, weight=1)
    steps_frame.rowconfigure(0, weight=1)
    summary_frame.columnconfigure(0, weight=1)
    summary_frame.rowconfigure(0, weight=1)

    columns = ("index", "label", "status", "risk", "policy")
    tree = ttk.Treeview(steps_frame, columns=columns, show="headings", height=9)
    for key, title, width in (
        ("index", "#", 42),
        ("label", "Passo", 220),
        ("status", "Stato", 96),
        ("risk", "Rischio", 80),
        ("policy", "Policy", 110),
    ):
        tree.heading(key, text=title)
        tree.column(key, width=width, stretch=key == "label")
    tree.grid(row=0, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(steps_frame, orient="vertical", command=tree.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=scrollbar.set)

    summary_text = tk.Text(summary_frame, wrap="word", borderwidth=1, relief="solid")
    summary_text.grid(row=0, column=0, sticky="nsew")
    detail_frame = ttk.LabelFrame(parent, text="Dettaglio passo", padding=6)
    detail_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
    detail_frame.columnconfigure(0, weight=1)
    detail_frame.rowconfigure(0, weight=1)
    detail_text = tk.Text(detail_frame, height=7, wrap="word", borderwidth=1, relief="solid")
    detail_text.grid(row=0, column=0, sticky="nsew")

    preview: dict = {}

    def show_selection(_event=None) -> None:
        selection = tree.selection()
        if selection:
            _set_text(detail_text, format_plan_step_details(preview, int(selection[0])))

    def analyze() -> None:
        nonlocal preview
        try:
            preview = build_game_plan_preview(
                goal_var.get(),
                game_version=version_var.get(),
                raw_facts=facts_text.get("1.0", tk.END),
            )
        except (ValueError, TypeError) as exc:
            _set_text(summary_text, f"Analisi non disponibile: {exc}")
            _set_text(detail_text, "")
            for item in tree.get_children():
                tree.delete(item)
            if console_log:
                console_log(f"Piano gioco non valido: {exc}", level="WARNING")
            return

        for item in tree.get_children():
            tree.delete(item)
        for index, row in enumerate(plan_step_rows(preview)):
            tree.insert("", "end", iid=str(index), values=row)
        _set_text(summary_text, format_game_plan_summary(preview))
        if tree.get_children():
            tree.selection_set("0")
            show_selection()
        else:
            _set_text(detail_text, "Nessun passo disponibile per il contesto attuale.")
        if console_log:
            console_log("Piano semantico aggiornato in modalita consultiva.")

    ttk.Button(input_frame, text="Analizza", command=analyze).grid(row=2, column=3, sticky="e", pady=(8, 0))
    goal_entry.bind("<Return>", analyze)
    tree.bind("<<TreeviewSelect>>", show_selection)
    _set_text(summary_text, "")
    _set_text(detail_text, "")
    goal_entry.focus_set()
    return {"goal_entry": goal_entry, "facts_text": facts_text, "steps_tree": tree, "summary_text": summary_text}
