"""UI builder for the shared knowledge graph navigation tab."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def build_knowledge_graph_tab(
    *,
    parent,
    theme,
    refresh_knowledge_graph,
    on_knowledge_graph_select,
):
    """Create a multi-level knowledge graph browser."""
    background_color = theme.get("bg_color") or theme.get("background_color") or "#282c34"
    text_color = theme.get("text_color") or theme.get("fg_color") or "#abb2bf"

    main_frame = ttk.Frame(parent)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)

    toolbar = ttk.Frame(main_frame)
    toolbar.pack(fill="x", pady=(0, 8))
    ttk.Button(toolbar, text="Aggiorna", command=refresh_knowledge_graph).pack(side="left")

    paned = ttk.PanedWindow(main_frame, orient="horizontal")
    paned.pack(fill="both", expand=True)

    tree_frame = ttk.LabelFrame(paned, text="Grafo conoscenza", padding="8")
    details_frame = ttk.LabelFrame(paned, text="Dettaglio", padding="8")
    paned.add(tree_frame, weight=3)
    paned.add(details_frame, weight=2)

    columns = ("tipo", "agganci")
    knowledge_tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", height=24)
    knowledge_tree.heading("#0", text="Nodo")
    knowledge_tree.heading("tipo", text="Tipo")
    knowledge_tree.heading("agganci", text="Agganci")
    knowledge_tree.column("#0", width=360, minwidth=220)
    knowledge_tree.column("tipo", width=110, minwidth=80)
    knowledge_tree.column("agganci", width=90, minwidth=70, anchor="center")
    knowledge_tree.pack(side="left", fill="both", expand=True)

    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=knowledge_tree.yview)
    scrollbar.pack(side="right", fill="y")
    knowledge_tree.configure(yscrollcommand=scrollbar.set)
    knowledge_tree.bind("<<TreeviewSelect>>", lambda event: on_knowledge_graph_select())

    details_text = tk.Text(
        details_frame,
        height=16,
        wrap="word",
        bg=background_color,
        fg=text_color,
        insertbackground=text_color,
        relief="flat",
        padx=8,
        pady=8,
    )
    details_text.pack(fill="both", expand=True)
    details_text.configure(state="disabled")

    linked_frame = ttk.LabelFrame(details_frame, text="Elementi e osservazioni collegate", padding="6")
    linked_frame.pack(fill="both", expand=False, pady=(8, 0))
    linked_columns = ("id", "tipo", "nome")
    linked_tree = ttk.Treeview(linked_frame, columns=linked_columns, show="headings", height=7)
    linked_tree.heading("id", text="ID")
    linked_tree.heading("tipo", text="Tipo")
    linked_tree.heading("nome", text="Nome")
    linked_tree.column("id", width=70, anchor="center")
    linked_tree.column("tipo", width=90, anchor="center")
    linked_tree.column("nome", width=280)
    linked_tree.pack(fill="both", expand=True)

    return {
        "knowledge_tree": knowledge_tree,
        "details_text": details_text,
        "linked_tree": linked_tree,
    }
