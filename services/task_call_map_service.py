"""Build a read-only task/call map from supervised network observations."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

from services.shared_knowledge_export_service import SHARED_KNOWLEDGE_DIR


NETWORK_OBSERVATIONS_DIRNAME = "network_observations"
MATURITY_LABELS = {
    "observed": "Osservato",
    "repeated_candidate": "Candidato ripetuto",
    "cross_session_candidate": "Candidato multi-sessione",
    "human_reviewed": "Revisionato",
    "validated": "Validato",
}

_DOMAIN_KEYWORDS = {
    "battle_reports": (
        "battaglia",
        "battaglie",
        "messaggi",
        "rapporti",
        "report",
        "avversario",
        "registro",
    ),
    "resources": ("risorse", "inventario"),
    "armaments": ("armamento", "armamenti", "equipaggiamento"),
    "gathering": ("raccolta", "mappa"),
    "workshop": ("officina", "produzione"),
    "research": ("ricerca",),
    "missions": ("missione", "missioni", "obiettivo", "ricompensa"),
}

_UI_NODE_RULES = (
    (("messaggi",), ("communications_button", "communications_center_view")),
    (
        ("rapporti", "report"),
        ("battle_reports_tab_button", "battle_report_list_view", "battle_report_entry"),
    ),
    (("dettagli", "analizzo"), ("battle_report_detail_view",)),
    (("ciclo", "battaglie"), ("battle_report_list_view", "battle_report_entry")),
    (
        ("avversario",),
        (
            "battle_report_participants_panel",
            "battle_opponent_section",
            "battle_report_timeline_view",
        ),
    ),
)


def load_task_call_map(
    knowledge_dir: Path | str = SHARED_KNOWLEDGE_DIR,
) -> dict[str, Any]:
    """Load domains, UI nodes and every persisted metadata-only observation."""

    base_dir = Path(knowledge_dir)
    registry = _read_json(
        base_dir / "learning_domain_registry.json",
        default={"domains": []},
    )
    ui_graph = _read_json(base_dir / "ui_semantic_graph.json", default={"nodes": []})
    nodes_by_id = {
        str(node.get("node_id")): node
        for node in ui_graph.get("nodes", [])
        if node.get("node_id")
    }
    observation_paths = sorted(
        (base_dir / NETWORK_OBSERVATIONS_DIRNAME).glob("*.json")
    )
    observations = [
        _read_json(path, default={})
        for path in observation_paths
        if path.is_file()
    ]
    fingerprint_sessions: dict[str, set[str]] = {}
    for observation in observations:
        session_id = str(observation.get("network_session_id") or "sessione_sconosciuta")
        for window in observation.get("semantic_windows", []):
            fingerprint = str(window.get("shape_fingerprint") or "")
            if fingerprint and fingerprint != "no_distinct_application_shape":
                fingerprint_sessions.setdefault(fingerprint, set()).add(session_id)

    tasks = []
    for observation in observations:
        session_id = str(observation.get("network_session_id") or "sessione_sconosciuta")
        generated_at = observation.get("generated_at")
        replay_allowed = bool(
            (observation.get("capture_policy") or {}).get("replay_allowed", False)
        )
        for index, window in enumerate(observation.get("semantic_windows", []), start=1):
            label = str(window.get("declared_semantic_label") or f"Finestra {index}")
            fingerprint = str(
                window.get("shape_fingerprint") or "no_distinct_application_shape"
            )
            maturity = _derive_maturity(
                window,
                session_count=len(fingerprint_sessions.get(fingerprint, set())),
            )
            visual_node_ids = _match_ui_nodes(label, nodes_by_id)
            calls = _build_calls(window)
            tasks.append(
                {
                    "task_id": f"{session_id}:{index}",
                    "label": label,
                    "domain_id": _infer_domain(label),
                    "operation_class": _classify_operation(window),
                    "maturity": maturity,
                    "maturity_label": MATURITY_LABELS[maturity],
                    "semantic_status": window.get("semantic_status"),
                    "fingerprint": fingerprint,
                    "session_id": session_id,
                    "generated_at": generated_at,
                    "observed_at": window.get("marker_observed_at"),
                    "application_message_count": int(
                        window.get("application_message_count") or 0
                    ),
                    "visual_node_ids": visual_node_ids,
                    "visual_nodes": [
                        nodes_by_id[node_id] for node_id in visual_node_ids
                    ],
                    "channels": list(window.get("channel_summary") or []),
                    "calls": calls,
                    "replay_allowed": replay_allowed,
                    "evidence_note": _evidence_note(window, maturity),
                }
            )

    domains = []
    tasks_by_domain: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        tasks_by_domain.setdefault(task["domain_id"], []).append(task)
    for domain in registry.get("domains", []):
        domain_id = str(domain.get("domain_id"))
        domain_tasks = tasks_by_domain.get(domain_id, [])
        domains.append(
            {
                **domain,
                "task_count": len(domain_tasks),
                "tasks": domain_tasks,
            }
        )

    known_domain_ids = {str(domain.get("domain_id")) for domain in domains}
    for domain_id, domain_tasks in tasks_by_domain.items():
        if domain_id in known_domain_ids:
            continue
        domains.append(
            {
                "domain_id": domain_id,
                "label": domain_id.replace("_", " ").title(),
                "status": "observed",
                "task_count": len(domain_tasks),
                "tasks": domain_tasks,
            }
        )

    return {
        "knowledge_dir": str(base_dir),
        "domains": domains,
        "tasks": tasks,
        "nodes_by_id": nodes_by_id,
        "observation_count": len(observations),
        "task_count": len(tasks),
        "call_count": sum(len(task["calls"]) for task in tasks),
        "maturity_counts": dict(Counter(task["maturity"] for task in tasks)),
        "policy": {
            "read_only": True,
            "replay_allowed": False,
            "meaning_requires_visual_validation": True,
        },
    }


def format_task_call_details(
    item_kind: str,
    item: dict[str, Any],
    model: dict[str, Any],
) -> str:
    """Format a selected domain, task, UI node or call for the details pane."""

    if item_kind == "summary":
        return (
            "Schema task e chiamate ricostruito\n"
            f"Sessioni analizzate: {model['observation_count']}\n"
            f"Finestre/task osservati: {model['task_count']}\n"
            f"Forme di chiamata: {model['call_count']}\n\n"
            "Vista sola lettura. Le associazioni sono indizi controllati: nessuna "
            "chiamata viene decodificata, riprodotta o autorizzata."
        )
    if item_kind == "domain":
        return (
            f"Dominio: {item.get('label', '')}\n"
            f"ID: {item.get('domain_id', '')}\n"
            f"Stato: {item.get('status', '')}\n"
            f"Task osservati: {item.get('task_count', 0)}"
        )
    if item_kind == "task":
        nodes = ", ".join(
            f"{node.get('label', node.get('node_id'))} [{node.get('node_id')}]"
            for node in item.get("visual_nodes", [])
        )
        channels = ", ".join(
            f"{channel.get('transport', '').upper()}:{channel.get('server_port')}"
            for channel in item.get("channels", [])
        )
        return (
            f"Task dichiarato: {item.get('label', '')}\n"
            f"Dominio: {item.get('domain_id', '')}\n"
            f"Classe operativa: {item.get('operation_class', '')}\n"
            f"Maturità: {item.get('maturity_label', '')}\n"
            f"Sessione: {item.get('session_id', '')}\n"
            f"Osservato: {item.get('observed_at') or '-'}\n"
            f"Fingerprint: {item.get('fingerprint', '')}\n"
            f"Messaggi applicativi: {item.get('application_message_count', 0)}\n"
            f"Canali: {channels or '-'}\n"
            f"Nodi UI collegati: {nodes or '-'}\n"
            f"Replay consentito: NO\n\n"
            f"{item.get('evidence_note', '')}"
        )
    if item_kind == "ui_node":
        return (
            f"Funzione/nodo UI: {item.get('label', '')}\n"
            f"ID: {item.get('node_id', '')}\n"
            f"Tipo: {item.get('kind', '')}\n"
            f"Parent: {item.get('parent_node_id') or '-'}\n\n"
            f"{item.get('notes', '')}"
        )
    if item_kind == "call":
        if item.get("call_kind") == "exchange":
            shape = (
                f"{item.get('request_bytes')} B client → "
                f"{item.get('response_bytes')} B server"
            )
            latency = f"{item.get('latency_ms')} ms"
        elif item.get("call_kind") == "server_push":
            shape = f"{item.get('response_bytes')} B server → client"
            latency = "-"
        else:
            shape = (
                f"{item.get('bytes')} B {item.get('direction', '').replace('_', ' → ')}"
                f" × {item.get('count', 1)}"
            )
            latency = "-"
        return (
            f"Forma di chiamata: {item.get('label', '')}\n"
            f"Classe: {item.get('call_kind', '')}\n"
            f"Canale: {item.get('transport', '').upper()}:{item.get('server_port')}\n"
            f"Forma: {shape}\n"
            f"Latenza candidata: {latency}\n"
            f"Stato: {item.get('status', '')}\n\n"
            "È metadato di forma, non contenuto decodificato e non una chiamata "
            "riproducibile."
        )
    return "Seleziona un dominio, task, nodo UI o forma di chiamata."


def _derive_maturity(window: dict[str, Any], *, session_count: int) -> str:
    explicit = window.get("maturity")
    if explicit in MATURITY_LABELS:
        return str(explicit)
    if session_count >= 2:
        return "cross_session_candidate"
    if int(window.get("application_message_count") or 0) > 0:
        return "observed"
    return "observed"


def _infer_domain(label: str) -> str:
    normalized = _normalize(label)
    for domain_id, keywords in _DOMAIN_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return domain_id
    return "general"


def _classify_operation(window: dict[str, Any]) -> str:
    exchanges = window.get("candidate_exchanges") or []
    pushes = window.get("candidate_server_pushes") or []
    if exchanges and pushes:
        return "server-backed + aggiornamento asincrono"
    if exchanges:
        return "server-backed"
    if pushes:
        return "aggiornamento asincrono"
    if int(window.get("application_message_count") or 0) == 0:
        return "locale / cached / non osservato"
    return "forma applicativa non classificata"


def _match_ui_nodes(label: str, nodes_by_id: dict[str, dict[str, Any]]) -> list[str]:
    normalized = _normalize(label)
    matched: list[str] = []
    for keywords, node_ids in _UI_NODE_RULES:
        if not any(keyword in normalized for keyword in keywords):
            continue
        for node_id in node_ids:
            if node_id in nodes_by_id and node_id not in matched:
                matched.append(node_id)
    return matched


def _build_calls(window: dict[str, Any]) -> list[dict[str, Any]]:
    calls = []
    for index, exchange in enumerate(window.get("candidate_exchanges") or [], start=1):
        calls.append(
            {
                **exchange,
                "call_id": f"exchange:{index}",
                "call_kind": "exchange",
                "label": (
                    f"Scambio candidato {exchange.get('request_bytes')}→"
                    f"{exchange.get('response_bytes')} B"
                ),
            }
        )
    for index, push in enumerate(window.get("candidate_server_pushes") or [], start=1):
        calls.append(
            {
                **push,
                "call_id": f"push:{index}",
                "call_kind": "server_push",
                "label": f"Push server candidato {push.get('response_bytes')} B",
            }
        )
    if not calls:
        for index, shape in enumerate(window.get("application_shape") or [], start=1):
            calls.append(
                {
                    **shape,
                    "call_id": f"shape:{index}",
                    "call_kind": "shape",
                    "label": (
                        f"Forma {shape.get('direction', '')} "
                        f"{shape.get('bytes')} B × {shape.get('count', 1)}"
                    ),
                    "status": "shape_observed_not_replayable",
                }
            )
    return calls


def _evidence_note(window: dict[str, Any], maturity: str) -> str:
    status = window.get("semantic_status")
    if status == "unbounded_missing_next_marker":
        return (
            "Finestra priva del marcatore di chiusura successivo: non attribuire "
            "il traffico seguente a questo task."
        )
    if int(window.get("application_message_count") or 0) == 0:
        return (
            "Il marcatore dell'operatore è presente, ma in questa finestra non è "
            "emersa una forma applicativa distinta."
        )
    if maturity == "cross_session_candidate":
        return (
            "Lo stesso fingerprint compare in sessioni indipendenti; serve ancora "
            "conferma visiva e revisione umana."
        )
    return (
        "Associazione osservata una volta tra intento dichiarato e metadati di "
        "traffico. Richiede ripetizione, postcondizione visiva e revisione umana."
    )


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


__all__ = [
    "MATURITY_LABELS",
    "format_task_call_details",
    "load_task_call_map",
]
