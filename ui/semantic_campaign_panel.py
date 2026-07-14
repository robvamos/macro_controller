"""Consult and curate semantic campaign attribution for game macros."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from repositories.macro_repository import get_all_macros
from services.semantic_campaign_service import (
    ASSET_DOMAINS,
    CAMPAIGN_KINDS,
    OPERATION_TAGS,
    attribute_macro_to_campaign,
    create_semantic_campaign,
    list_semantic_campaigns,
    suggest_campaign_attributions,
)


def build_semantic_campaign_tab(parent, *, console_log=None):
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(1, weight=1)

    form = ttk.LabelFrame(parent, text="Campagna e operazione", padding=8)
    form.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
    for column in (1, 3):
        form.columnconfigure(column, weight=1)

    label_var = tk.StringVar()
    kind_var = tk.StringVar(value=CAMPAIGN_KINDS[0])
    objective_var = tk.StringVar()
    version_var = tk.StringVar()
    tags_var = tk.StringVar(value="battle,march")
    assets_var = tk.StringVar(value="heroes,beasts")
    campaign_var = tk.StringVar()
    macro_var = tk.StringVar()
    operation_var = tk.StringVar()
    status_var = tk.StringVar(value="candidate")

    def add_field(row, label, widget, column=0):
        ttk.Label(form, text=label).grid(row=row, column=column, sticky="w", padx=(0, 6), pady=3)
        widget.grid(row=row, column=column + 1, sticky="ew", pady=3)

    add_field(0, "Campagna", ttk.Entry(form, textvariable=label_var))
    add_field(0, "Tipo", ttk.Combobox(form, textvariable=kind_var, values=CAMPAIGN_KINDS, state="readonly"), 2)
    add_field(1, "Obiettivo", ttk.Entry(form, textvariable=objective_var))
    add_field(1, "Versione", ttk.Entry(form, textvariable=version_var), 2)
    add_field(2, "Tag operazione", ttk.Entry(form, textvariable=tags_var))
    add_field(2, "Asset", ttk.Entry(form, textvariable=assets_var), 2)

    body = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
    body.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
    campaigns_frame = ttk.LabelFrame(body, text="Campagne registrate", padding=6)
    bindings_frame = ttk.LabelFrame(body, text="Macro e attribuzioni", padding=6)
    body.add(campaigns_frame, weight=3)
    body.add(bindings_frame, weight=4)
    campaigns_frame.columnconfigure(0, weight=1)
    campaigns_frame.rowconfigure(0, weight=1)
    bindings_frame.columnconfigure(0, weight=1)
    bindings_frame.rowconfigure(2, weight=1)

    campaign_tree = ttk.Treeview(campaigns_frame, columns=("label", "kind", "objective", "status"), show="headings")
    for key, title, width in (("label", "Campagna", 170), ("kind", "Tipo", 115), ("objective", "Obiettivo", 190), ("status", "Stato", 90)):
        campaign_tree.heading(key, text=title)
        campaign_tree.column(key, width=width, stretch=key in {"label", "objective"})
    campaign_tree.grid(row=0, column=0, sticky="nsew")
    campaign_scroll = ttk.Scrollbar(campaigns_frame, orient="vertical", command=campaign_tree.yview)
    campaign_scroll.grid(row=0, column=1, sticky="ns")
    campaign_tree.configure(yscrollcommand=campaign_scroll.set)

    attach_form = ttk.Frame(bindings_frame)
    attach_form.grid(row=0, column=0, sticky="ew", pady=(0, 6))
    attach_form.columnconfigure(1, weight=1)
    ttk.Label(attach_form, text="Macro").grid(row=0, column=0, sticky="w", padx=(0, 6))
    macro_box = ttk.Combobox(attach_form, textvariable=macro_var, state="readonly")
    macro_box.grid(row=0, column=1, sticky="ew")
    ttk.Label(attach_form, text="Operazione").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=(4, 0))
    ttk.Entry(attach_form, textvariable=operation_var).grid(row=1, column=1, sticky="ew", pady=(4, 0))
    ttk.Label(attach_form, text="Validazione").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=(4, 0))
    ttk.Combobox(attach_form, textvariable=status_var, values=("candidate", "human_reviewed", "validated"), state="readonly").grid(row=2, column=1, sticky="ew", pady=(4, 0))

    binding_tree = ttk.Treeview(bindings_frame, columns=("macro", "operation", "validation", "confidence"), show="headings", height=10)
    for key, title, width in (("macro", "Macro", 180), ("operation", "Operazione", 160), ("validation", "Validazione", 115), ("confidence", "Conf.", 65)):
        binding_tree.heading(key, text=title)
        binding_tree.column(key, width=width, stretch=key in {"macro", "operation"})
    binding_tree.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
    coverage_label = ttk.Label(bindings_frame, text="Seleziona una campagna per vedere copertura ed evidenze.", anchor="w")
    coverage_label.grid(row=3, column=0, sticky="ew", pady=(6, 0))

    campaigns: dict[str, dict] = {}

    def values_from_csv(value: str) -> tuple[str, ...]:
        return tuple(item.strip() for item in value.split(",") if item.strip())

    def refresh() -> None:
        nonlocal campaigns
        campaigns = {item["campaign_id"]: item for item in list_semantic_campaigns()}
        for item in campaign_tree.get_children():
            campaign_tree.delete(item)
        for campaign_id, campaign in campaigns.items():
            campaign_tree.insert("", "end", iid=campaign_id, values=(campaign["label"], campaign["campaign_kind"], campaign["objective"], campaign["status"]))
        options = [f"{macro['id']} - {macro['nome']}" for macro in get_all_macros() if macro.get("macro_kind") != "system"]
        macro_box.configure(values=options)
        show_bindings()

    def selected_campaign_id() -> str | None:
        selection = campaign_tree.selection()
        return selection[0] if selection else None

    def show_bindings(_event=None) -> None:
        for item in binding_tree.get_children():
            binding_tree.delete(item)
        campaign_id = selected_campaign_id()
        if not campaign_id or campaign_id not in campaigns:
            coverage_label.configure(text="Seleziona una campagna per vedere copertura ed evidenze.")
            return
        coverage = campaigns[campaign_id]["coverage"]
        coverage_label.configure(
            text=(
                f"Binding: {coverage['macro_bindings']} | validati: {coverage['validated_bindings']} | "
                f"run osservati: {coverage['observed_runs']} | successi: {coverage['successful_runs']}"
            )
        )
        macro_names = {int(item["id"]): item.get("nome", "") for item in get_all_macros()}
        for binding in campaigns[campaign_id]["macro_bindings"]:
            binding_tree.insert("", "end", values=(macro_names.get(binding["macro_id"], f"Macro {binding['macro_id']}"), binding["operation_id"], binding["validation_status"], f"{binding['confidence']:.0%}"))

    def create_campaign() -> None:
        try:
            create_semantic_campaign(
                label=label_var.get(), campaign_kind=kind_var.get(), objective=objective_var.get(),
                operation_tags=values_from_csv(tags_var.get()), asset_domains=values_from_csv(assets_var.get()),
                game_version=version_var.get(),
            )
            label_var.set("")
            objective_var.set("")
            refresh()
            if console_log:
                console_log("Campagna semantica creata: attribuisci ora le macro candidate.")
        except ValueError as exc:
            if console_log:
                console_log(f"Campagna non creata: {exc}", level="WARNING")

    def attach_macro() -> None:
        campaign_id = selected_campaign_id()
        if not campaign_id or not macro_var.get() or not operation_var.get().strip():
            if console_log:
                console_log("Seleziona una campagna, una macro e un'operazione.", level="WARNING")
            return
        try:
            macro_id = int(macro_var.get().split(" - ", 1)[0])
            validation = status_var.get()
            attribute_macro_to_campaign(
                campaign_id=campaign_id, macro_id=macro_id, operation_id=operation_var.get(),
                relation_type=validation, confidence=1.0 if validation == "validated" else 0.6 if validation == "human_reviewed" else 0.25,
                validation_status="unverified" if validation == "candidate" else validation,
            )
            operation_var.set("")
            refresh()
            campaign_tree.selection_set(campaign_id)
            show_bindings()
            if console_log:
                console_log("Macro attribuita con snapshot della sequenza e stato di validazione.")
        except (ValueError, IndexError) as exc:
            if console_log:
                console_log(f"Attribuzione non salvata: {exc}", level="WARNING")

    def show_suggestions() -> None:
        suggestions = suggest_campaign_attributions()
        if not suggestions:
            text = "Nessuna macro non attribuita con una corrispondenza semantica sufficiente."
        else:
            text = "\n".join(
                f"{item['macro_name']} -> {item['campaign_label']} ({item['confidence']:.0%}; {', '.join(item['matched_terms'])})"
                for item in suggestions[:8]
            )
        if console_log:
            console_log(f"Suggerimenti di attribuzione (solo consultivi):\n{text}")

    ttk.Button(form, text="Crea Campagna", command=create_campaign).grid(row=3, column=3, sticky="e", pady=(7, 0))
    ttk.Button(attach_form, text="Attribuisci Macro", command=attach_macro).grid(row=3, column=1, sticky="e", pady=(6, 0))
    ttk.Button(form, text="Suggerimenti", command=show_suggestions).grid(row=3, column=2, sticky="e", padx=(0, 6), pady=(7, 0))
    campaign_tree.bind("<<TreeviewSelect>>", show_bindings)
    refresh()
    return {"campaign_tree": campaign_tree, "binding_tree": binding_tree}


__all__ = ["build_semantic_campaign_tab"]
