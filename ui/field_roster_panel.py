"""Pannello consultazione roster campo Doomsday."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from doomsday.services.field_roster_service import (
    format_bench_and_plan,
    format_pair_details,
    load_field_roster,
    pair_row,
)


PAIR_COLUMNS = ("slot", "front_hero", "back_hero", "front_beast", "support_beast", "role")
PAIR_HEADINGS = {
    "slot": "#",
    "front_hero": "Davanti",
    "back_hero": "Dietro",
    "front_beast": "Bestia",
    "support_beast": "Supporto",
    "role": "Uso",
}


def _configure_pair_tree(tree: ttk.Treeview) -> None:
    tree.heading("slot", text=PAIR_HEADINGS["slot"])
    tree.heading("front_hero", text=PAIR_HEADINGS["front_hero"])
    tree.heading("back_hero", text=PAIR_HEADINGS["back_hero"])
    tree.heading("front_beast", text=PAIR_HEADINGS["front_beast"])
    tree.heading("support_beast", text=PAIR_HEADINGS["support_beast"])
    tree.heading("role", text=PAIR_HEADINGS["role"])
    tree.column("slot", width=42, stretch=False, anchor="center")
    tree.column("front_hero", width=120, stretch=True)
    tree.column("back_hero", width=120, stretch=True)
    tree.column("front_beast", width=150, stretch=True)
    tree.column("support_beast", width=150, stretch=True)
    tree.column("role", width=230, stretch=True)


def _populate_pair_tree(tree: ttk.Treeview, pairs: list[dict]) -> None:
    for item in tree.get_children():
        tree.delete(item)
    for index, pair in enumerate(pairs):
        tree.insert("", "end", iid=str(index), values=pair_row(pair))


def _set_text(widget: tk.Text, text: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", tk.END)
    widget.insert(tk.END, text)
    widget.configure(state="disabled")


def build_field_roster_tab(parent, *, roster_path=None):
    """Costruisce una tab per confrontare roster attuale e proposta."""
    roster = load_field_roster(roster_path)
    current_pairs = roster["current_pairs"]
    recommended_pairs = roster["recommended_pairs"]

    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(1, weight=1)
    parent.rowconfigure(2, weight=1)

    header = ttk.Frame(parent, padding=(10, 10, 10, 4))
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(0, weight=1)

    title = ttk.Label(header, text="Roster Campo", font=("Segoe UI", 13, "bold"))
    title.grid(row=0, column=0, sticky="w")
    subtitle_text = roster.get("context") or "Confronto tra assetto corrente e proposta."
    subtitle = ttk.Label(header, text=subtitle_text, wraplength=1100, justify="left")
    subtitle.grid(row=1, column=0, sticky="ew", pady=(4, 0))
    updated_at = roster.get("updated_at")
    if updated_at:
        ttk.Label(header, text=f"Aggiornato: {updated_at}").grid(row=0, column=1, sticky="e", padx=(12, 0))

    comparison = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
    comparison.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 6))

    current_frame = ttk.LabelFrame(comparison, text="Assetto attuale", padding=6)
    proposed_frame = ttk.LabelFrame(comparison, text="Proposta Codex", padding=6)
    comparison.add(current_frame, weight=1)
    comparison.add(proposed_frame, weight=1)

    current_tree = ttk.Treeview(current_frame, columns=PAIR_COLUMNS, show="headings", height=8)
    proposed_tree = ttk.Treeview(proposed_frame, columns=PAIR_COLUMNS, show="headings", height=8)
    for frame, tree in ((current_frame, current_tree), (proposed_frame, proposed_tree)):
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        _configure_pair_tree(tree)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)

    _populate_pair_tree(current_tree, current_pairs)
    _populate_pair_tree(proposed_tree, recommended_pairs)

    details_area = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
    details_area.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

    details_frame = ttk.LabelFrame(details_area, text="Dettaglio selezione", padding=6)
    plan_frame = ttk.LabelFrame(details_area, text="Panchina e piano", padding=6)
    details_area.add(details_frame, weight=1)
    details_area.add(plan_frame, weight=1)

    details_frame.columnconfigure(0, weight=1)
    details_frame.rowconfigure(0, weight=1)
    plan_frame.columnconfigure(0, weight=1)
    plan_frame.rowconfigure(0, weight=1)

    details_text = tk.Text(details_frame, height=10, wrap="word", borderwidth=1, relief="solid")
    details_text.grid(row=0, column=0, sticky="nsew")
    details_scrollbar = ttk.Scrollbar(details_frame, orient="vertical", command=details_text.yview)
    details_scrollbar.grid(row=0, column=1, sticky="ns")
    details_text.configure(yscrollcommand=details_scrollbar.set)

    plan_text = tk.Text(plan_frame, height=10, wrap="word", borderwidth=1, relief="solid")
    plan_text.grid(row=0, column=0, sticky="nsew")
    plan_scrollbar = ttk.Scrollbar(plan_frame, orient="vertical", command=plan_text.yview)
    plan_scrollbar.grid(row=0, column=1, sticky="ns")
    plan_text.configure(yscrollcommand=plan_scrollbar.set)

    def show_pair(pair: dict) -> None:
        _set_text(details_text, format_pair_details(pair))

    def on_current_select(_event=None) -> None:
        selection = current_tree.selection()
        if not selection:
            return
        proposed_tree.selection_remove(proposed_tree.selection())
        show_pair(current_pairs[int(selection[0])])

    def on_proposed_select(_event=None) -> None:
        selection = proposed_tree.selection()
        if not selection:
            return
        current_tree.selection_remove(current_tree.selection())
        show_pair(recommended_pairs[int(selection[0])])

    current_tree.bind("<<TreeviewSelect>>", on_current_select)
    proposed_tree.bind("<<TreeviewSelect>>", on_proposed_select)

    _set_text(plan_text, format_bench_and_plan(roster))
    if current_pairs:
        current_tree.selection_set("0")
        show_pair(current_pairs[0])
    else:
        show_pair({})

    return {
        "current_tree": current_tree,
        "proposed_tree": proposed_tree,
        "details_text": details_text,
        "plan_text": plan_text,
    }
