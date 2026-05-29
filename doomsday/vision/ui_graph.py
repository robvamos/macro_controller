"""Layer a grafi per modellare viste, pannelli, popup e transizioni del gioco."""

from __future__ import annotations

from dataclasses import dataclass

from doomsday.vision.game_element_recovery import GameScreenElementSearchResult, search_game_window_elements


@dataclass(slots=True)
class UIGraphCondition:
    condition_id: str
    element_names: tuple[str, ...]
    expected_presence: bool = True
    threshold: float = 0.85
    description: str = ""


@dataclass(slots=True)
class UIGraphNode:
    node_id: str
    label: str
    kind: str
    conditions: tuple[UIGraphCondition, ...]
    parent_node_id: str | None = None
    layout_role: str = "content"
    recovery_action: str | None = None
    tags: tuple[str, ...] = ()
    notes: str = ""


@dataclass(slots=True)
class UIGraphEdge:
    from_node_id: str
    to_node_id: str
    trigger: str
    action_name: str | None = None
    description: str = ""


@dataclass(slots=True)
class UIGraphConditionEvaluation:
    condition_id: str
    satisfied: bool
    search_result: GameScreenElementSearchResult


@dataclass(slots=True)
class UIGraphNodeEvaluation:
    node_id: str
    label: str
    kind: str
    active: bool
    confidence: float
    condition_results: tuple[UIGraphConditionEvaluation, ...]
    recovery_action: str | None = None


@dataclass(slots=True)
class UIGraphEvaluation:
    graph_id: str
    active_node_ids: tuple[str, ...]
    node_results: tuple[UIGraphNodeEvaluation, ...]

    def get_node_result(self, node_id: str) -> UIGraphNodeEvaluation | None:
        for node_result in self.node_results:
            if node_result.node_id == node_id:
                return node_result
        return None


@dataclass(slots=True)
class UIKnowledgeNodeRecord:
    node_id: str
    label: str
    kind: str
    parent_node_id: str | None
    layout_role: str
    seen_count: int
    avg_confidence: float
    recovery_action: str | None
    related_node_ids: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(slots=True)
class UIGraphKnowledgeBase:
    graph_id: str
    observed_nodes: tuple[UIKnowledgeNodeRecord, ...]
    active_node_ids: tuple[str, ...]
    notes: str = ""

    def get_node_record(self, node_id: str) -> UIKnowledgeNodeRecord | None:
        for record in self.observed_nodes:
            if record.node_id == node_id:
                return record
        return None


@dataclass(slots=True)
class UIGraphMacroLink:
    graph_id: str
    node_id: str
    relation_type: str
    macro_id: int | None
    macro_name: str | None
    intent_key: str | None = None
    priority: int = 100
    notes: str = ""


@dataclass(slots=True)
class UIGraphMacroPlan:
    graph_id: str
    intent_key: str | None
    target_node_id: str
    candidate_links: tuple[UIGraphMacroLink, ...]
    notes: str = ""


@dataclass(slots=True)
class UIGraphDefinition:
    graph_id: str
    name: str
    nodes: tuple[UIGraphNode, ...]
    edges: tuple[UIGraphEdge, ...]
    notes: str = ""

    def get_node(self, node_id: str) -> UIGraphNode | None:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None


def evaluate_ui_graph(graph: UIGraphDefinition, window_rect: tuple[int, int, int, int]) -> UIGraphEvaluation:
    """Valuta l'intera schermata del gioco contro i nodi del grafo."""
    node_results: list[UIGraphNodeEvaluation] = []
    active_node_ids: list[str] = []

    for node in graph.nodes:
        condition_results: list[UIGraphConditionEvaluation] = []
        confidence_values: list[float] = []
        all_satisfied = True

        for condition in node.conditions:
            search_result = search_game_window_elements(
                window_rect,
                element_names=condition.element_names,
                threshold=condition.threshold,
                expected_presence=condition.expected_presence,
            )
            condition_results.append(
                UIGraphConditionEvaluation(
                    condition_id=condition.condition_id,
                    satisfied=search_result.condition_satisfied,
                    search_result=search_result,
                )
            )
            all_satisfied = all_satisfied and search_result.condition_satisfied
            if search_result.found and search_result.score is not None:
                confidence_values.append(float(search_result.score))
            elif search_result.condition_satisfied:
                confidence_values.append(1.0)
            else:
                confidence_values.append(0.0)

        confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
        node_result = UIGraphNodeEvaluation(
            node_id=node.node_id,
            label=node.label,
            kind=node.kind,
            active=all_satisfied,
            confidence=confidence,
            condition_results=tuple(condition_results),
            recovery_action=node.recovery_action,
        )
        node_results.append(node_result)
        if all_satisfied:
            active_node_ids.append(node.node_id)

    return UIGraphEvaluation(
        graph_id=graph.graph_id,
        active_node_ids=tuple(active_node_ids),
        node_results=tuple(node_results),
    )


def build_default_doomsday_ui_graph() -> UIGraphDefinition:
    """Grafo iniziale delle schermate e popup più importanti per l'automazione esterna."""
    root_runtime_node = UIGraphNode(
        node_id="game_runtime_root",
        label="Runtime gioco",
        kind="view",
        conditions=(),
        parent_node_id=None,
        layout_role="root",
        recovery_action=None,
        tags=("runtime", "root"),
        notes="Nodo radice logico dell'interfaccia di gioco usato per collegare viste, layer e popup.",
    )
    exterior_region_view = UIGraphNode(
        node_id="exterior_region_view",
        label="Vista esterna o regionale",
        kind="view",
        conditions=(),
        parent_node_id="game_runtime_root",
        layout_role="main_view",
        recovery_action=None,
        tags=("region", "exterior", "navigation"),
        notes=(
            "Vista esterna o regionale del gioco. Condivide pannelli superiori comuni con il rifugio "
            "e usa il pulsante in basso a sinistra per entrare nel rifugio."
        ),
    )
    shelter_interior_view = UIGraphNode(
        node_id="shelter_interior_view",
        label="Vista interna rifugio",
        kind="view",
        conditions=(),
        parent_node_id="game_runtime_root",
        layout_role="main_view",
        recovery_action=None,
        tags=("shelter", "interior", "navigation"),
        notes=(
            "Vista interna del rifugio. Condivide i pannelli superiori comuni ma aggiunge controlli "
            "specifici sul lato basso sinistro e destro."
        ),
    )
    top_left_compact_status_panel = UIGraphNode(
        node_id="top_left_compact_status_panel",
        label="Pannello compatto alto sinistra",
        kind="panel",
        conditions=(),
        parent_node_id="game_runtime_root",
        layout_role="top_left_compact",
        recovery_action=None,
        tags=("shared", "hud", "status"),
        notes=(
            "Riquadro rettangolare compatto in alto a sinistra, comune sia alla vista esterna "
            "sia alla vista rifugio."
        ),
    )
    top_right_extended_status_panel = UIGraphNode(
        node_id="top_right_extended_status_panel",
        label="Pannello esteso alto destra",
        kind="panel",
        conditions=(),
        parent_node_id="game_runtime_root",
        layout_role="top_right_extended",
        recovery_action=None,
        tags=("shared", "hud", "resources"),
        notes=(
            "Riquadro rettangolare più esteso in alto a destra, circa triplo del pannello compatto "
            "alto sinistra, comune alle due viste principali."
        ),
    )
    bottom_left_shelter_switch_button = UIGraphNode(
        node_id="bottom_left_shelter_switch_button",
        label="Bottone passaggio vista rifugio",
        kind="control",
        conditions=(),
        parent_node_id="game_runtime_root",
        layout_role="bottom_left_primary",
        recovery_action=None,
        tags=("shared", "navigation", "shelter-switch"),
        notes=(
            "Bottone importante in basso a sinistra usato per passare dalla vista esterna "
            "alla vista rifugio e viceversa."
        ),
    )
    shelter_left_side_controls_panel = UIGraphNode(
        node_id="shelter_left_side_controls_panel",
        label="Pannellino controlli sinistra rifugio",
        kind="panel",
        conditions=(),
        parent_node_id="shelter_interior_view",
        layout_role="left_side_aux",
        recovery_action=None,
        tags=("shelter", "controls", "left"),
        notes=(
            "Pannellino appoggiato al margine sinistro nella vista rifugio, appena sopra il bottone "
            "di passaggio vista, con controlli aggiuntivi."
        ),
    )
    shelter_bottom_right_sections_panel = UIGraphNode(
        node_id="shelter_bottom_right_sections_panel",
        label="Pannello sezioni basso destra rifugio",
        kind="panel",
        conditions=(),
        parent_node_id="shelter_interior_view",
        layout_role="bottom_right_sections",
        recovery_action=None,
        tags=("shelter", "sections", "campagna", "zaino", "alleanza", "bestie", "eroe"),
        notes=(
            "Pannellino esteso in basso a destra nella vista rifugio con le sezioni campagna, "
            "zaino, alleanza, bestie ed eroe."
        ),
    )
    shelter_right_edge_alerts_panel = UIGraphNode(
        node_id="shelter_right_edge_alerts_panel",
        label="Pannellino destro controlli e avvisi",
        kind="panel",
        conditions=(),
        parent_node_id="shelter_interior_view",
        layout_role="right_edge_aux",
        recovery_action=None,
        tags=("shelter", "alerts", "controls", "right"),
        notes=(
            "Pannellino appoggiato sul bordo destro appena sopra il pannello sezioni basso destra, "
            "dedicato a controlli e avvisi della vista rifugio."
        ),
    )
    boot_overlay_node = UIGraphNode(
        node_id="boot_overlay_layer",
        label="Layer overlay boot",
        kind="panel",
        conditions=(),
        parent_node_id="game_runtime_root",
        layout_role="overlay",
        recovery_action=None,
        tags=("boot", "overlay"),
        notes="Layer logico che ospita popup e blocchi temporanei durante boot e caricamento.",
    )
    popup_node = UIGraphNode(
        node_id="initial_blocking_popup_close_symbol",
        label="Popup bloccante iniziale",
        kind="popup",
        conditions=(
            UIGraphCondition(
                condition_id="close_symbol_visible",
                element_names=("popup_exit_close_symbol",),
                expected_presence=True,
                threshold=0.85,
                description="Il simbolo di chiusura del popup è visibile sulla schermata.",
            ),
        ),
        parent_node_id="boot_overlay_layer",
        layout_role="modal",
        recovery_action="click_popup_exit_close_symbol",
        tags=("boot", "blocking", "popup"),
        notes="Popup bloccante che appare dopo il caricamento del gioco.",
    )
    playable_node = UIGraphNode(
        node_id="playable_interface_without_boot_popup",
        label="Interfaccia pronta senza popup iniziale",
        kind="view",
        conditions=(
            UIGraphCondition(
                condition_id="close_symbol_not_visible",
                element_names=("popup_exit_close_symbol",),
                expected_presence=False,
                threshold=0.85,
                description="Il simbolo di chiusura popup non è presente, quindi la vista è libera da quel blocco.",
            ),
        ),
        parent_node_id="game_runtime_root",
        layout_role="main_view",
        recovery_action=None,
        tags=("boot", "playable"),
        notes="Vista libera dal popup di boot; non garantisce ancora il completamento di tutto il flusso.",
    )
    edges = (
        UIGraphEdge(
            from_node_id="game_runtime_root",
            to_node_id="exterior_region_view",
            trigger="region_view_active",
            action_name=None,
            description="Il runtime può presentare la vista esterna o regionale come vista principale.",
        ),
        UIGraphEdge(
            from_node_id="game_runtime_root",
            to_node_id="shelter_interior_view",
            trigger="shelter_view_active",
            action_name=None,
            description="Il runtime può presentare la vista interna del rifugio come vista principale.",
        ),
        UIGraphEdge(
            from_node_id="exterior_region_view",
            to_node_id="bottom_left_shelter_switch_button",
            trigger="shared_navigation_controls_visible",
            action_name=None,
            description="La vista esterna espone il bottone basso sinistra di passaggio rifugio.",
        ),
        UIGraphEdge(
            from_node_id="shelter_interior_view",
            to_node_id="bottom_left_shelter_switch_button",
            trigger="shared_navigation_controls_visible",
            action_name=None,
            description="Anche la vista rifugio mantiene il bottone basso sinistra per tornare o cambiare vista.",
        ),
        UIGraphEdge(
            from_node_id="exterior_region_view",
            to_node_id="top_left_compact_status_panel",
            trigger="shared_top_panels_visible",
            action_name=None,
            description="La vista esterna include il pannello compatto alto sinistra.",
        ),
        UIGraphEdge(
            from_node_id="exterior_region_view",
            to_node_id="top_right_extended_status_panel",
            trigger="shared_top_panels_visible",
            action_name=None,
            description="La vista esterna include il pannello esteso alto destra.",
        ),
        UIGraphEdge(
            from_node_id="shelter_interior_view",
            to_node_id="top_left_compact_status_panel",
            trigger="shared_top_panels_visible",
            action_name=None,
            description="La vista rifugio include il pannello compatto alto sinistra.",
        ),
        UIGraphEdge(
            from_node_id="shelter_interior_view",
            to_node_id="top_right_extended_status_panel",
            trigger="shared_top_panels_visible",
            action_name=None,
            description="La vista rifugio include il pannello esteso alto destra.",
        ),
        UIGraphEdge(
            from_node_id="shelter_interior_view",
            to_node_id="shelter_left_side_controls_panel",
            trigger="shelter_aux_left_visible",
            action_name=None,
            description="La vista rifugio espone un pannellino di controlli sul margine sinistro sopra il bottone di cambio vista.",
        ),
        UIGraphEdge(
            from_node_id="shelter_interior_view",
            to_node_id="shelter_bottom_right_sections_panel",
            trigger="shelter_sections_visible",
            action_name=None,
            description="La vista rifugio espone il pannello basso destra con le sezioni principali.",
        ),
        UIGraphEdge(
            from_node_id="shelter_interior_view",
            to_node_id="shelter_right_edge_alerts_panel",
            trigger="shelter_alerts_visible",
            action_name=None,
            description="La vista rifugio espone il pannellino destro con controlli e avvisi.",
        ),
        UIGraphEdge(
            from_node_id="bottom_left_shelter_switch_button",
            to_node_id="shelter_interior_view",
            trigger="enter_shelter",
            action_name="open_shelter_view",
            description="Usando il bottone basso sinistra dalla vista esterna si entra nel rifugio.",
        ),
        UIGraphEdge(
            from_node_id="bottom_left_shelter_switch_button",
            to_node_id="exterior_region_view",
            trigger="exit_shelter",
            action_name="open_region_view",
            description="Usando il bottone basso sinistra dalla vista rifugio si torna alla vista esterna o regionale.",
        ),
        UIGraphEdge(
            from_node_id="game_runtime_root",
            to_node_id="boot_overlay_layer",
            trigger="boot_overlay_visible",
            action_name=None,
            description="Il runtime del gioco può presentare un layer overlay durante fasi di boot o popup.",
        ),
        UIGraphEdge(
            from_node_id="initial_blocking_popup_close_symbol",
            to_node_id="playable_interface_without_boot_popup",
            trigger="popup_closed",
            action_name="resume_boot_flow",
            description="Una volta chiuso il popup bloccante il boot può proseguire verso la vista giocabile.",
        ),
    )
    return UIGraphDefinition(
        graph_id="doomsday-default-ui-graph",
        name="Doomsday Default UI Graph",
        nodes=(
            root_runtime_node,
            exterior_region_view,
            shelter_interior_view,
            top_left_compact_status_panel,
            top_right_extended_status_panel,
            bottom_left_shelter_switch_button,
            shelter_left_side_controls_panel,
            shelter_bottom_right_sections_panel,
            shelter_right_edge_alerts_panel,
            boot_overlay_node,
            popup_node,
            playable_node,
        ),
        edges=edges,
        notes=(
            "Grafo iniziale dell'architettura UI del gioco: distingue vista esterna e rifugio, "
            "pannelli comuni superiori, controlli di cambio vista, sezioni del rifugio e popup di boot."
        ),
    )


def learn_ui_knowledge(graph: UIGraphDefinition, evaluation: UIGraphEvaluation, previous: UIGraphKnowledgeBase | None = None) -> UIGraphKnowledgeBase:
    """Arricchisce una knowledge base dell'interfaccia a partire dalle osservazioni del grafo."""
    existing_records: dict[str, UIKnowledgeNodeRecord] = {}
    if previous and previous.graph_id == graph.graph_id:
        existing_records = {record.node_id: record for record in previous.observed_nodes}

    active_node_ids = tuple(node_id for node_id in evaluation.active_node_ids)
    related_by_node: dict[str, set[str]] = {
        node.node_id: set(existing_records.get(node.node_id, UIKnowledgeNodeRecord(
            node_id=node.node_id,
            label=node.label,
            kind=node.kind,
            parent_node_id=node.parent_node_id,
            layout_role=node.layout_role,
            seen_count=0,
            avg_confidence=0.0,
            recovery_action=node.recovery_action,
            related_node_ids=(),
            tags=node.tags,
        )).related_node_ids)
        for node in graph.nodes
    }

    for edge in graph.edges:
        if edge.from_node_id in active_node_ids or edge.to_node_id in active_node_ids:
            related_by_node.setdefault(edge.from_node_id, set()).add(edge.to_node_id)
            related_by_node.setdefault(edge.to_node_id, set()).add(edge.from_node_id)

    for node in graph.nodes:
        if not node.parent_node_id:
            continue
        related_by_node.setdefault(node.node_id, set()).add(node.parent_node_id)
        related_by_node.setdefault(node.parent_node_id, set()).add(node.node_id)

    updated_records: list[UIKnowledgeNodeRecord] = []
    for node in graph.nodes:
        node_result = evaluation.get_node_result(node.node_id)
        previous_record = existing_records.get(node.node_id)
        if node_result and node_result.active:
            previous_seen = previous_record.seen_count if previous_record else 0
            previous_avg = previous_record.avg_confidence if previous_record else 0.0
            new_seen_count = previous_seen + 1
            new_avg_confidence = ((previous_avg * previous_seen) + node_result.confidence) / new_seen_count
        else:
            new_seen_count = previous_record.seen_count if previous_record else 0
            new_avg_confidence = previous_record.avg_confidence if previous_record else 0.0

        updated_records.append(
            UIKnowledgeNodeRecord(
                node_id=node.node_id,
                label=node.label,
                kind=node.kind,
                parent_node_id=node.parent_node_id,
                layout_role=node.layout_role,
                seen_count=new_seen_count,
                avg_confidence=new_avg_confidence,
                recovery_action=node.recovery_action,
                related_node_ids=tuple(sorted(related_by_node.get(node.node_id, set()))),
                tags=node.tags,
            )
        )

    return UIGraphKnowledgeBase(
        graph_id=graph.graph_id,
        observed_nodes=tuple(updated_records),
        active_node_ids=active_node_ids,
        notes="Knowledge base incrementale dell'architettura UI del gioco, arricchita dalle osservazioni live.",
    )
