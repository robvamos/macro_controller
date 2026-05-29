"""Servizio per collegare il layer a grafi UI alle macro operative del progetto."""

from __future__ import annotations

from doomsday.vision.ui_graph import UIGraphMacroLink, UIGraphMacroPlan
from repositories.macro_repository import get_macro_metadata_by_id
from repositories.ui_graph_macro_link_repository import (
    create_ui_graph_macro_link,
    get_ui_graph_macro_links,
)


def link_macro_to_ui_node(
    *,
    graph_id,
    node_id,
    macro_id,
    intent_key=None,
    relation_type="candidate",
    priority=100,
    notes=None,
):
    macro = get_macro_metadata_by_id(macro_id)
    if not macro:
        raise ValueError(f"Macro con ID {macro_id} non trovata.")
    return create_ui_graph_macro_link(
        graph_id=graph_id,
        node_id=node_id,
        macro_id=macro_id,
        macro_name_snapshot=macro.get("nome"),
        intent_key=intent_key,
        relation_type=relation_type,
        priority=priority,
        notes=notes,
    )


def get_macro_plan_for_ui_node(*, graph_id, node_id, intent_key=None):
    links = get_ui_graph_macro_links(
        graph_id=graph_id,
        node_id=node_id,
        intent_key=intent_key,
        enabled_only=True,
    )
    if not links and intent_key is not None:
        links = get_ui_graph_macro_links(
            graph_id=graph_id,
            node_id=node_id,
            intent_key=None,
            enabled_only=True,
        )

    candidate_links = []
    for link in links:
        macro_name = link.get("macro_name_snapshot")
        if link.get("macro_id"):
            current_macro = get_macro_metadata_by_id(link["macro_id"])
            if current_macro:
                macro_name = current_macro.get("nome") or macro_name
        candidate_links.append(
            UIGraphMacroLink(
                graph_id=link["graph_id"],
                node_id=link["node_id"],
                relation_type=link["relation_type"],
                macro_id=link.get("macro_id"),
                macro_name=macro_name,
                intent_key=link.get("intent_key"),
                priority=link.get("priority", 100),
                notes=link.get("notes") or "",
            )
        )

    return UIGraphMacroPlan(
        graph_id=graph_id,
        intent_key=intent_key,
        target_node_id=node_id,
        candidate_links=tuple(candidate_links),
        notes="Piano macro candidato derivato dai collegamenti tra grafo UI e macro.",
    )


__all__ = [
    "get_macro_plan_for_ui_node",
    "link_macro_to_ui_node",
]
