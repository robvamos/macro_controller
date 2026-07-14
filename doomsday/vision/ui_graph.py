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
    observable: bool
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
        # A structural node expresses the taxonomy of the interface, not a live
        # observation. It must remain unknown until it has visual conditions.
        all_satisfied = bool(node.conditions)

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
            observable=bool(node.conditions),
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
    top_left_profile_portrait = UIGraphNode(
        node_id="top_left_profile_portrait",
        label="Riquadro eroe profilo alto sinistra",
        kind="control",
        conditions=(),
        parent_node_id="top_left_compact_status_panel",
        layout_role="portrait_anchor",
        recovery_action=None,
        tags=("shared", "hud", "profile", "portrait", "hero", "user-customizable"),
        notes=(
            "Primo riquadro quadrato del pannello alto sinistra, associato all'eroe o profilo. "
            "L'immagine interna puo' essere casuale o personalizzata dall'utente del gioco, quindi "
            "non e' un riferimento stabile. Per il matching contano soprattutto cornice, posizione, "
            "forma del riquadro e struttura generale del blocco."
        ),
    )
    top_left_status_bar = UIGraphNode(
        node_id="top_left_status_bar",
        label="Barra stato profilo alto sinistra",
        kind="control",
        conditions=(),
        parent_node_id="top_left_compact_status_panel",
        layout_role="status_bar",
        recovery_action=None,
        tags=("shared", "hud", "status-bar"),
        notes="Barra orizzontale sotto il ritratto profilo. Il livello di riempimento puo' variare e non va confrontato in modo rigido.",
    )
    top_left_power_indicator = UIGraphNode(
        node_id="top_left_power_indicator",
        label="Indicatore potenza alto sinistra",
        kind="control",
        conditions=(),
        parent_node_id="top_left_compact_status_panel",
        layout_role="power_indicator",
        recovery_action=None,
        tags=("shared", "hud", "power", "language-agnostic"),
        notes=(
            "Area con icona pugno e valore numerico della potenza. Il numero cambia spesso, quindi il riferimento "
            "stabile e' l'icona e la posizione, non il valore. Serve soprattutto a sapere dove si trova "
            "l'indicatore, cosi' da poterne eventualmente leggere il numero come dato separato."
        ),
    )
    top_left_vip_indicator = UIGraphNode(
        node_id="top_left_vip_indicator",
        label="Indicatore VIP alto sinistra",
        kind="control",
        conditions=(),
        parent_node_id="top_left_compact_status_panel",
        layout_role="vip_indicator",
        recovery_action=None,
        tags=("shared", "hud", "vip", "language-agnostic"),
        notes=(
            "Indicatore VIP nel pannello alto sinistra, tipicamente composto dalla scritta VIP e da un numero. "
            "Il numero del livello puo' cambiare, quindi il riferimento stabile resta il blocco VIP nella sua posizione "
            "e non il valore numerico preciso."
        ),
    )
    top_left_left_quick_action = UIGraphNode(
        node_id="top_left_left_quick_action",
        label="Scorciatoia sinistra alto sinistra",
        kind="control",
        conditions=(),
        parent_node_id="top_left_compact_status_panel",
        layout_role="quick_action",
        recovery_action=None,
        tags=("shared", "hud", "quick-action", "left"),
        notes="Primo piccolo pulsante rapido sulla destra del pannello alto sinistra.",
    )
    top_left_right_quick_action = UIGraphNode(
        node_id="top_left_right_quick_action",
        label="Scorciatoia destra alto sinistra",
        kind="control",
        conditions=(),
        parent_node_id="top_left_compact_status_panel",
        layout_role="quick_action",
        recovery_action=None,
        tags=("shared", "hud", "quick-action", "right"),
        notes="Secondo piccolo pulsante rapido sulla destra del pannello alto sinistra.",
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
        conditions=(
            UIGraphCondition(
                condition_id="view_switch_icon_visible",
                element_names=("region_view_switch_globe_icon", "shelter_view_switch_home_icon"),
                expected_presence=True,
                threshold=0.85,
                description=(
                    "E' visibile una delle due icone del cambio vista in basso a sinistra: "
                    "globo per andare in regione oppure rifugio per entrare nel shelter. "
                    "La scritta puo' cambiare con la lingua, quindi il matching si basa sul simbolo."
                ),
            ),
        ),
        parent_node_id="game_runtime_root",
        layout_role="bottom_left_primary",
        recovery_action=None,
        tags=("shared", "navigation", "shelter-switch", "language-agnostic"),
        notes=(
            "Bottone importante in basso a sinistra usato per passare dalla vista esterna "
            "alla vista rifugio e viceversa. Nella vista rifugio puo' mostrare il globo con "
            "la scritta Regione o equivalenti in altre lingue; nella vista regione puo' mostrare "
            "l'icona del rifugio con la scritta Rifugio o equivalenti. Per questo il riferimento "
            "semantico corretto e' l'icona, non il testo."
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
        label="Pannello sezioni basso destra condiviso",
        kind="panel",
        conditions=(),
        parent_node_id="game_runtime_root",
        layout_role="bottom_right_sections",
        recovery_action=None,
        tags=("shared", "sections", "campagna", "zaino", "alleanza", "bestie", "eroe", "language-agnostic"),
        notes=(
            "Pannellino esteso in basso a destra presente sia nella vista regione sia nella vista "
            "rifugio con le sezioni campagna, zaino, alleanza, bestie ed eroe. I badge rossi e i "
            "numeri di eventi in sospeso sono variabili e non devono far parte del riferimento "
            "grafico stabile. Anche le scritte possono cambiare lingua, quindi il matching dovrebbe "
            "privilegiare icone, disposizione e struttura del pannello."
        ),
    )
    campaign_section_button = UIGraphNode(
        node_id="campaign_section_button",
        label="Sezione Campagna",
        kind="control",
        conditions=(),
        parent_node_id="shelter_bottom_right_sections_panel",
        layout_role="section_slot",
        recovery_action=None,
        tags=("shared", "section", "campaign", "language-agnostic"),
        notes=(
            "Sezione Campagna del pannello basso destra condiviso. Il badge rosso eventi e la scritta "
            "non sono il riferimento principale: conta soprattutto l'icona stabile."
        ),
    )
    backpack_section_button = UIGraphNode(
        node_id="backpack_section_button",
        label="Sezione Zaino",
        kind="control",
        conditions=(),
        parent_node_id="shelter_bottom_right_sections_panel",
        layout_role="section_slot",
        recovery_action=None,
        tags=("shared", "section", "backpack", "language-agnostic"),
        notes="Sezione Zaino del pannello basso destra condiviso, da riconoscere soprattutto tramite icona.",
    )
    alliance_section_button = UIGraphNode(
        node_id="alliance_section_button",
        label="Sezione Alleanza",
        kind="control",
        conditions=(),
        parent_node_id="shelter_bottom_right_sections_panel",
        layout_role="section_slot",
        recovery_action=None,
        tags=("shared", "section", "alliance", "language-agnostic"),
        notes=(
            "Sezione Alleanza del pannello basso destra condiviso. I numeri rossi variabili non fanno "
            "parte del riferimento stabile."
        ),
    )
    beast_section_button = UIGraphNode(
        node_id="beast_section_button",
        label="Sezione Bestia",
        kind="control",
        conditions=(),
        parent_node_id="shelter_bottom_right_sections_panel",
        layout_role="section_slot",
        recovery_action=None,
        tags=("shared", "section", "beast", "language-agnostic"),
        notes="Sezione Bestia del pannello basso destra condiviso, con matching basato soprattutto sull'icona.",
    )
    hero_section_button = UIGraphNode(
        node_id="hero_section_button",
        label="Sezione Eroe",
        kind="control",
        conditions=(),
        parent_node_id="shelter_bottom_right_sections_panel",
        layout_role="section_slot",
        recovery_action=None,
        tags=("shared", "section", "hero", "language-agnostic"),
        notes="Sezione Eroe del pannello basso destra condiviso, con riferimento principale sull'icona.",
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
    troop_heal_action_symbol = UIGraphNode(
        node_id="troop_heal_action_symbol",
        label="Azione cura truppe",
        kind="control",
        conditions=(
            UIGraphCondition(
                condition_id="troop_heal_action_symbol_visible",
                element_names=("troop_heal_action_symbol",),
                expected_presence=True,
                threshold=0.85,
                description="Il simbolo grafico della cura truppe è visibile nella schermata.",
            ),
        ),
        parent_node_id="shelter_interior_view",
        layout_role="action_symbol",
        recovery_action=None,
        tags=("shelter", "troops", "healing", "macro-reference", "visual-guard"),
        notes=(
            "Elemento operativo per la cura delle truppe. Può essere usato come riferimento visivo "
            "alternativo quando una macro di cura contiene questo elemento tra i click registrati."
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
                element_names=("popup_exit_close_symbol", "boot_blocking_popup_close_button"),
                expected_presence=True,
                threshold=0.85,
                description="Il simbolo o bottone di chiusura del popup è visibile sulla schermata.",
            ),
        ),
        parent_node_id="boot_overlay_layer",
        layout_role="modal",
        recovery_action="click_popup_exit_close_symbol",
        tags=("boot", "blocking", "popup"),
        notes=(
            "Popup bloccante che appare dopo il caricamento del gioco. Quando è visibile, "
            "di norma basta cliccare l'elemento di chiusura catalogato per liberare la schermata."
        ),
    )
    popup_back_return_node = UIGraphNode(
        node_id="popup_back_return_symbol",
        label="Simbolo popup di ritorno alto sinistra",
        kind="popup",
        conditions=(
            UIGraphCondition(
                condition_id="back_return_symbol_visible",
                element_names=("popup_back_return_symbol",),
                expected_presence=True,
                threshold=0.85,
                description=(
                    "Il simbolo grafico di ritorno alto sinistra è visibile sul popup e può essere "
                    "cliccato più volte finché resta presente."
                ),
            ),
        ),
        parent_node_id="boot_overlay_layer",
        layout_role="modal",
        recovery_action="click_popup_back_return_symbol_until_gone",
        tags=("boot", "blocking", "popup", "return", "recovery"),
        notes=(
            "Alcuni popup bloccanti non mostrano un bottone classico di chiusura ma questo simbolo "
            "di ritorno in alto a sinistra. La strategia corretta è cliccarlo 2 o 3 volte finché "
            "resta presente, verificando dopo ogni tentativo se il riferimento visivo della macro è tornato compatibile."
        ),
    )
    popup_crossed_circle_node = UIGraphNode(
        node_id="popup_crossed_circle_symbol",
        label="Simbolo popup cerchio barrato",
        kind="popup",
        conditions=(
            UIGraphCondition(
                condition_id="crossed_circle_symbol_visible",
                element_names=("popup_crossed_circle_symbol",),
                expected_presence=True,
                threshold=0.85,
                description=(
                    "Il simbolo grafico cerchio barrato è visibile sul popup e può essere usato come chiusura "
                    "ripetuta finché resta presente."
                ),
            ),
        ),
        parent_node_id="boot_overlay_layer",
        layout_role="modal",
        recovery_action="click_popup_crossed_circle_symbol_until_gone",
        tags=("boot", "blocking", "popup", "crossed-circle", "recovery"),
        notes=(
            "Alcuni popup bloccanti possono essere chiusi quando compare questo simbolo grafico cerchio barrato. "
            "La strategia è cliccarlo 2 o 3 volte finché resta presente e verificare dopo ogni tentativo "
            "se il riferimento visivo della macro è tornato compatibile."
        ),
    )
    empty_space_dismissal_node = UIGraphNode(
        node_id="empty_space_popup_dismissal_band_4",
        label="Dismiss popup con spazio vuoto fascia medio alta",
        kind="spatial_action",
        conditions=(),
        parent_node_id="boot_overlay_layer",
        layout_role="empty_space_recovery",
        recovery_action="click_empty_space_band_4_from_bottom",
        tags=("boot", "blocking", "popup", "empty-space", "fallback", "learned"),
        notes=(
            "Regola appresa: alcuni popup bloccanti non espongono un identificatore stabile e si chiudono "
            "cliccando in uno spazio vuoto dello schermo. Dividendo lo schermo in 5 bande orizzontali "
            "contate dal basso, la fascia 4 corrisponde di solito a una zona medio alta utile per tentare il dismiss "
            "senza colpire controlli principali. Semanticamente questa azione e' lo stesso elemento logico anche quando "
            "compare su popup diversi. Questa e' una recovery spaziale non vincolante, da usare dopo i bottoni "
            "di chiusura riconoscibili."
        ),
    )
    playable_node = UIGraphNode(
        node_id="playable_interface_without_boot_popup",
        label="Interfaccia pronta senza popup iniziale",
        kind="view",
        conditions=(
            UIGraphCondition(
                condition_id="close_symbol_not_visible",
                element_names=("popup_exit_close_symbol", "boot_blocking_popup_close_button"),
                expected_presence=False,
                threshold=0.85,
                description="Il simbolo di chiusura popup non è presente, quindi la vista è libera da quel blocco.",
            ),
            UIGraphCondition(
                condition_id="back_return_symbol_not_visible",
                element_names=("popup_back_return_symbol",),
                expected_presence=False,
                threshold=0.85,
                description="Il simbolo popup di ritorno non è presente, quindi quel blocco non è attivo.",
            ),
            UIGraphCondition(
                condition_id="crossed_circle_symbol_not_visible",
                element_names=("popup_crossed_circle_symbol",),
                expected_presence=False,
                threshold=0.85,
                description="Il simbolo popup con cerchio barrato non è presente, quindi quel blocco non è attivo.",
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
            from_node_id="top_left_compact_status_panel",
            to_node_id="top_left_profile_portrait",
            trigger="profile_portrait_visible",
            action_name=None,
            description="Il pannello alto sinistra espone il riquadro ritratto profilo.",
        ),
        UIGraphEdge(
            from_node_id="top_left_compact_status_panel",
            to_node_id="top_left_status_bar",
            trigger="status_bar_visible",
            action_name=None,
            description="Il pannello alto sinistra espone una barra stato sotto il ritratto.",
        ),
        UIGraphEdge(
            from_node_id="top_left_compact_status_panel",
            to_node_id="top_left_power_indicator",
            trigger="power_indicator_visible",
            action_name=None,
            description="Il pannello alto sinistra espone l'indicatore di potenza con icona pugno e valore.",
        ),
        UIGraphEdge(
            from_node_id="top_left_compact_status_panel",
            to_node_id="top_left_vip_indicator",
            trigger="vip_indicator_visible",
            action_name=None,
            description="Il pannello alto sinistra espone il blocco VIP.",
        ),
        UIGraphEdge(
            from_node_id="top_left_compact_status_panel",
            to_node_id="top_left_left_quick_action",
            trigger="left_quick_action_visible",
            action_name=None,
            description="Il pannello alto sinistra espone una prima scorciatoia rapida laterale.",
        ),
        UIGraphEdge(
            from_node_id="top_left_compact_status_panel",
            to_node_id="top_left_right_quick_action",
            trigger="right_quick_action_visible",
            action_name=None,
            description="Il pannello alto sinistra espone una seconda scorciatoia rapida laterale.",
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
            from_node_id="exterior_region_view",
            to_node_id="shelter_bottom_right_sections_panel",
            trigger="shared_bottom_right_sections_visible",
            action_name=None,
            description="La vista esterna espone il pannello basso destra condiviso con le sezioni principali.",
        ),
        UIGraphEdge(
            from_node_id="shelter_interior_view",
            to_node_id="shelter_bottom_right_sections_panel",
            trigger="shared_bottom_right_sections_visible",
            action_name=None,
            description="La vista rifugio espone lo stesso pannello basso destra condiviso con le sezioni principali.",
        ),
        UIGraphEdge(
            from_node_id="shelter_bottom_right_sections_panel",
            to_node_id="campaign_section_button",
            trigger="campaign_slot_visible",
            action_name="open_campaign_section",
            description="Il pannello condiviso espone la sezione Campagna.",
        ),
        UIGraphEdge(
            from_node_id="shelter_bottom_right_sections_panel",
            to_node_id="backpack_section_button",
            trigger="backpack_slot_visible",
            action_name="open_backpack_section",
            description="Il pannello condiviso espone la sezione Zaino.",
        ),
        UIGraphEdge(
            from_node_id="shelter_bottom_right_sections_panel",
            to_node_id="alliance_section_button",
            trigger="alliance_slot_visible",
            action_name="open_alliance_section",
            description="Il pannello condiviso espone la sezione Alleanza.",
        ),
        UIGraphEdge(
            from_node_id="shelter_bottom_right_sections_panel",
            to_node_id="beast_section_button",
            trigger="beast_slot_visible",
            action_name="open_beast_section",
            description="Il pannello condiviso espone la sezione Bestia.",
        ),
        UIGraphEdge(
            from_node_id="shelter_bottom_right_sections_panel",
            to_node_id="hero_section_button",
            trigger="hero_slot_visible",
            action_name="open_hero_section",
            description="Il pannello condiviso espone la sezione Eroe.",
        ),
        UIGraphEdge(
            from_node_id="shelter_interior_view",
            to_node_id="shelter_right_edge_alerts_panel",
            trigger="shelter_alerts_visible",
            action_name=None,
            description="La vista rifugio espone il pannellino destro con controlli e avvisi.",
        ),
        UIGraphEdge(
            from_node_id="shelter_interior_view",
            to_node_id="troop_heal_action_symbol",
            trigger="troop_heal_available",
            action_name="open_troop_healing_flow",
            description="La vista rifugio può esporre il simbolo di cura truppe come azione operativa.",
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
        UIGraphEdge(
            from_node_id="popup_back_return_symbol",
            to_node_id="playable_interface_without_boot_popup",
            trigger="popup_back_return_clicked",
            action_name="resume_after_popup_back_return",
            description="Il popup viene chiuso con il simbolo di ritorno e il flusso può riprendere.",
        ),
        UIGraphEdge(
            from_node_id="popup_crossed_circle_symbol",
            to_node_id="playable_interface_without_boot_popup",
            trigger="popup_crossed_circle_clicked",
            action_name="resume_after_popup_crossed_circle",
            description="Il popup viene chiuso con il simbolo cerchio barrato e il flusso può riprendere.",
        ),
        UIGraphEdge(
            from_node_id="empty_space_popup_dismissal_band_4",
            to_node_id="playable_interface_without_boot_popup",
            trigger="empty_space_dismissal_clicked",
            action_name="resume_after_empty_space_popup_dismissal",
            description="Fallback appreso: click su spazio vuoto nella fascia 4 dal basso per chiudere popup senza identificatori.",
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
            top_left_profile_portrait,
            top_left_status_bar,
            top_left_power_indicator,
            top_left_vip_indicator,
            top_left_left_quick_action,
            top_left_right_quick_action,
            top_right_extended_status_panel,
            bottom_left_shelter_switch_button,
            shelter_left_side_controls_panel,
            shelter_bottom_right_sections_panel,
            campaign_section_button,
            backpack_section_button,
            alliance_section_button,
            beast_section_button,
            hero_section_button,
            shelter_right_edge_alerts_panel,
            troop_heal_action_symbol,
            boot_overlay_node,
            popup_node,
            popup_back_return_node,
            popup_crossed_circle_node,
            empty_space_dismissal_node,
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
