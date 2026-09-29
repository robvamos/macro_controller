"""Navigable read-only browser for reconstructed game tasks and call shapes."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from services.task_call_map_service import (
    MATURITY_LABELS,
    format_task_call_details,
    load_task_call_map,
)


def build_task_call_map_tab(*, parent, theme):
    """Build the task → UI function → metadata-only call map tab."""

    background_color = theme.get("bg_color") or theme.get("background_color") or "#282c34"
    text_color = theme.get("text_color") or theme.get("fg_color") or "#abb2bf"
    state = {"model": None, "items": {}}

    main = ttk.Frame(parent)
    main.pack(fill="both", expand=True, padx=10, pady=10)

    toolbar = ttk.Frame(main)
    toolbar.pack(fill="x", pady=(0, 8))
    search_var = tk.StringVar()
    domain_var = tk.StringVar(value="Tutti i domini")
    maturity_var = tk.StringVar(value="Tutte le maturità")

    ttk.Label(toolbar, text="Cerca:").pack(side="left")
    search_entry = ttk.Entry(toolbar, textvariable=search_var, width=28)
    search_entry.pack(side="left", padx=(5, 10))
    ttk.Label(toolbar, text="Dominio:").pack(side="left")
    domain_combo = ttk.Combobox(
        toolbar,
        textvariable=domain_var,
        state="readonly",
        width=25,
        values=("Tutti i domini",),
    )
    domain_combo.pack(side="left", padx=(5, 10))
    ttk.Label(toolbar, text="Maturità:").pack(side="left")
    maturity_combo = ttk.Combobox(
        toolbar,
        textvariable=maturity_var,
        state="readonly",
        width=22,
        values=("Tutte le maturità", *MATURITY_LABELS.values()),
    )
    maturity_combo.pack(side="left", padx=(5, 10))

    summary_var = tk.StringVar(value="Caricamento schema…")
    ttk.Label(main, textvariable=summary_var).pack(fill="x", pady=(0, 6))

    paned = ttk.PanedWindow(main, orient="horizontal")
    paned.pack(fill="both", expand=True)
    tree_frame = ttk.LabelFrame(paned, text="Task, funzioni UI e chiamate", padding="8")
    detail_frame = ttk.LabelFrame(paned, text="Evidenze e significato", padding="8")
    paned.add(tree_frame, weight=3)
    paned.add(detail_frame, weight=2)

    columns = ("classe", "maturita", "forme")
    tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", height=25)
    tree.heading("#0", text="Schema navigabile")
    tree.heading("classe", text="Classe")
    tree.heading("maturita", text="Maturità")
    tree.heading("forme", text="Forme")
    tree.column("#0", width=360, minwidth=230)
    tree.column("classe", width=185, minwidth=130)
    tree.column("maturita", width=135, minwidth=105)
    tree.column("forme", width=65, minwidth=55, anchor="center")
    tree.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    scrollbar.pack(side="right", fill="y")
    tree.configure(yscrollcommand=scrollbar.set)

    details = tk.Text(
        detail_frame,
        wrap="word",
        bg=background_color,
        fg=text_color,
        insertbackground=text_color,
        relief="flat",
        padx=8,
        pady=8,
    )
    details.pack(fill="both", expand=True)
    details.configure(state="disabled")

    legend = ttk.LabelFrame(detail_frame, text="Regola di lettura", padding="6")
    legend.pack(fill="x", pady=(8, 0))
    ttk.Label(
        legend,
        text=(
            "Osservato ≠ validato. Porta, byte e latenza descrivono solo la forma; "
            "nessun payload viene letto e nessuna chiamata può essere riprodotta."
        ),
        wraplength=430,
        justify="left",
    ).pack(fill="x")

    def show_details(kind, item):
        model = state["model"]
        if model is None:
            return
        value = format_task_call_details(kind, item, model)
        details.configure(state="normal")
        details.delete("1.0", "end")
        details.insert("1.0", value)
        details.configure(state="disabled")

    def on_select(_event=None):
        selected = tree.selection()
        if not selected:
            return
        kind, item = state["items"].get(selected[0], ("unknown", {}))
        show_details(kind, item)

    def rebuild_tree(*_args):
        model = state["model"]
        if model is None:
            return
        for iid in tree.get_children():
            tree.delete(iid)
        state["items"] = {}
        query = search_var.get().strip().casefold()
        selected_domain = domain_var.get()
        selected_maturity = maturity_var.get()

        root_iid = tree.insert(
            "",
            "end",
            text="Schema ricostruito dai log",
            values=("sola lettura", "evidence-gated", model["call_count"]),
            open=True,
        )
        state["items"][root_iid] = ("summary", {})
        visible_tasks = 0
        for domain_index, domain in enumerate(model["domains"]):
            if (
                selected_domain != "Tutti i domini"
                and selected_domain != domain.get("label")
            ):
                continue
            matching_tasks = []
            for task in domain.get("tasks", []):
                if (
                    selected_maturity != "Tutte le maturità"
                    and selected_maturity != task.get("maturity_label")
                ):
                    continue
                searchable = " ".join(
                    (
                        task.get("label", ""),
                        task.get("operation_class", ""),
                        task.get("fingerprint", ""),
                        " ".join(task.get("visual_node_ids", [])),
                    )
                ).casefold()
                if query and query not in searchable:
                    continue
                matching_tasks.append(task)
            if not matching_tasks and (query or selected_maturity != "Tutte le maturità"):
                continue

            domain_iid = tree.insert(
                root_iid,
                "end",
                text=domain.get("label", domain.get("domain_id", "")),
                values=("dominio", domain.get("status", ""), len(matching_tasks)),
                open=bool(matching_tasks),
            )
            state["items"][domain_iid] = (
                "domain",
                {**domain, "task_count": len(matching_tasks)},
            )
            for task_index, task in enumerate(matching_tasks):
                visible_tasks += 1
                task_iid = tree.insert(
                    domain_iid,
                    "end",
                    text=task.get("label", ""),
                    values=(
                        task.get("operation_class", ""),
                        task.get("maturity_label", ""),
                        len(task.get("calls", [])),
                    ),
                )
                state["items"][task_iid] = ("task", task)

                if task.get("visual_nodes"):
                    ui_group = tree.insert(
                        task_iid,
                        "end",
                        text="Funzioni / nodi UI collegati",
                        values=("UI", "collegamento semantico", len(task["visual_nodes"])),
                    )
                    for node in task["visual_nodes"]:
                        node_iid = tree.insert(
                            ui_group,
                            "end",
                            text=node.get("label", node.get("node_id", "")),
                            values=(node.get("kind", ""), "grafo UI", ""),
                        )
                        state["items"][node_iid] = ("ui_node", node)

                if task.get("calls"):
                    call_group = tree.insert(
                        task_iid,
                        "end",
                        text="Forme di chiamata osservate",
                        values=("metadati", "non riproducibili", len(task["calls"])),
                    )
                    for call in task["calls"]:
                        call_iid = tree.insert(
                            call_group,
                            "end",
                            text=call.get("label", ""),
                            values=(
                                f"{call.get('transport', '').upper()}:{call.get('server_port')}",
                                "candidata",
                                "",
                            ),
                        )
                        state["items"][call_iid] = ("call", call)

        summary_var.set(
            f"{model['observation_count']} sessioni · {visible_tasks} task visibili · "
            f"{model['call_count']} forme totali · replay disabilitato"
        )
        tree.selection_set(root_iid)
        tree.focus(root_iid)
        show_details("summary", {})

    def refresh():
        state["model"] = load_task_call_map()
        domain_combo.configure(
            values=(
                "Tutti i domini",
                *[domain.get("label", "") for domain in state["model"]["domains"]],
            )
        )
        rebuild_tree()

    ttk.Button(toolbar, text="Aggiorna", command=refresh).pack(side="left")
    search_entry.bind("<KeyRelease>", rebuild_tree)
    domain_combo.bind("<<ComboboxSelected>>", rebuild_tree)
    maturity_combo.bind("<<ComboboxSelected>>", rebuild_tree)
    tree.bind("<<TreeviewSelect>>", on_select)
    refresh()

    return {
        "tree": tree,
        "details": details,
        "search_var": search_var,
        "domain_var": domain_var,
        "maturity_var": maturity_var,
        "refresh": refresh,
    }
