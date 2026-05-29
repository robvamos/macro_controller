"""Read the shared Doomsday knowledge graph exported to versionable files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.shared_knowledge_export_service import SHARED_KNOWLEDGE_DIR


def load_knowledge_graph_model(knowledge_dir: Path | str = SHARED_KNOWLEDGE_DIR) -> dict[str, Any]:
    """Load graph, element catalog, learning sessions and pattern hints as one model."""
    base_dir = Path(knowledge_dir)
    ui_graph = _read_json(base_dir / "ui_semantic_graph.json", default={})
    elements_payload = _read_json(base_dir / "game_elements_manifest.json", default={"game_elements": []})
    sessions_payload = _read_json(base_dir / "learning_sessions.json", default={"learning_sessions": []})
    patterns_payload = _read_json(base_dir / "pattern_suggestions.json", default={"pattern_suggestions": []})

    nodes = ui_graph.get("nodes", [])
    edges = ui_graph.get("edges", [])
    game_elements = elements_payload.get("game_elements", [])
    learning_sessions = sessions_payload.get("learning_sessions", [])
    pattern_suggestions = patterns_payload.get("pattern_suggestions", [])

    children_by_parent = _group_nodes_by_parent(nodes)
    edges_by_source = _group_edges_by_source(edges)
    elements_by_node = _group_elements_by_node(game_elements)
    clicks_by_node = _group_learning_clicks_by_node(learning_sessions)

    return {
        "knowledge_dir": str(base_dir),
        "graph": ui_graph,
        "nodes": nodes,
        "edges": edges,
        "game_elements": game_elements,
        "learning_sessions": learning_sessions,
        "pattern_suggestions": pattern_suggestions,
        "children_by_parent": children_by_parent,
        "edges_by_source": edges_by_source,
        "elements_by_node": elements_by_node,
        "clicks_by_node": clicks_by_node,
        "nodes_by_id": {node.get("node_id"): node for node in nodes},
        "elements_by_id": {str(element.get("id")): element for element in game_elements},
    }


def format_knowledge_graph_details(item_kind: str, item: dict[str, Any], model: dict[str, Any]) -> str:
    """Return readable details for the selected graph item."""
    if item_kind == "graph":
        graph = model["graph"]
        return (
            f"Grafo: {graph.get('name', graph.get('graph_id', ''))}\n"
            f"ID: {graph.get('graph_id', '')}\n"
            f"Nodi: {len(model['nodes'])}\n"
            f"Archi: {len(model['edges'])}\n"
            f"Elementi censiti: {len(model['game_elements'])}\n"
            f"Sessioni learning: {len(model['learning_sessions'])}\n\n"
            f"{graph.get('notes', '')}"
        )
    if item_kind == "node":
        node_id = item.get("node_id")
        linked_elements = model["elements_by_node"].get(node_id, [])
        linked_clicks = model["clicks_by_node"].get(node_id, [])
        return (
            f"Nodo: {item.get('label', '')}\n"
            f"ID: {node_id}\n"
            f"Tipo: {item.get('kind', '')}\n"
            f"Ruolo layout: {item.get('layout_role', '')}\n"
            f"Parent: {item.get('parent_node_id') or '-'}\n"
            f"Recovery action: {item.get('recovery_action') or '-'}\n"
            f"Tag: {', '.join(item.get('tags', [])) or '-'}\n"
            f"Elementi collegati: {len(linked_elements)}\n"
            f"Click learning collegati: {len(linked_clicks)}\n\n"
            f"{item.get('notes', '')}"
        )
    if item_kind == "element":
        return (
            f"Elemento: {item.get('name', '')}\n"
            f"ID: {item.get('id', '')}\n"
            f"Immagine: {item.get('image_path') or '-'}\n"
            f"Dimensione: {_format_image_size(item.get('image_size'))}\n"
            f"Ruolo semantico: {item.get('semantic_hint') or '-'}\n"
            f"Memoria: {item.get('memory_note') or '-'}\n\n"
            f"{item.get('description', '')}"
        )
    if item_kind == "edge":
        return (
            f"Transizione: {item.get('from_node_id', '')} -> {item.get('to_node_id', '')}\n"
            f"Trigger: {item.get('trigger', '')}\n"
            f"Azione: {item.get('action_name') or '-'}\n\n"
            f"{item.get('description', '')}"
        )
    if item_kind == "click":
        return (
            f"Click learning\n"
            f"Macro: {item.get('macro_name', '')} ({item.get('macro_id', '')})\n"
            f"Elemento: {item.get('game_element_id') or '-'}\n"
            f"Posizione: {item.get('x')}, {item.get('y')}\n"
            f"Normalizzata: {item.get('normalized_x')}, {item.get('normalized_y')}"
        )
    return "Seleziona un nodo del grafo."


def _read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _group_nodes_by_parent(nodes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        parent_key = node.get("parent_node_id") or "__root__"
        grouped.setdefault(parent_key, []).append(node)
    for children in grouped.values():
        children.sort(key=lambda item: (item.get("kind", ""), item.get("label", "")))
    return grouped


def _group_edges_by_source(edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        grouped.setdefault(edge.get("from_node_id"), []).append(edge)
    for source_edges in grouped.values():
        source_edges.sort(key=lambda item: (item.get("trigger", ""), item.get("to_node_id", "")))
    return grouped


def _group_elements_by_node(elements: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for element in elements:
        for node_id in _extract_node_ids_from_element(element):
            grouped.setdefault(node_id, []).append(element)
    for node_elements in grouped.values():
        node_elements.sort(key=lambda item: int(item.get("id") or 0))
    return grouped


def _extract_node_ids_from_element(element: dict[str, Any]) -> set[str]:
    node_ids: set[str] = set()
    metadata_blocks = element.get("metadata_blocks") or {}
    for blocks in metadata_blocks.values():
        for block in blocks:
            for key in ("ui_node_id", "view_node_id", "node_id"):
                value = block.get(key) if isinstance(block, dict) else None
                if value:
                    node_ids.add(str(value))
    return node_ids


def _group_learning_clicks_by_node(sessions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for session in sessions:
        for click in session.get("click_sequence", []):
            node_id = click.get("ui_node_id")
            if not node_id:
                continue
            grouped.setdefault(node_id, []).append(
                {
                    **click,
                    "macro_id": session.get("macro_id"),
                    "macro_name": session.get("name"),
                }
            )
    return grouped


def _format_image_size(image_size: dict[str, Any] | None) -> str:
    if not image_size:
        return "-"
    return f"{image_size.get('width', '?')}x{image_size.get('height', '?')}"


__all__ = [
    "format_knowledge_graph_details",
    "load_knowledge_graph_model",
]
