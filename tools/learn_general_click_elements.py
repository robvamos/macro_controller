"""Elevated two-minute learner for useful Doomsday click elements."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import time

from learning_mode_common import (
    REPO_ROOT,
    SHORTCUT_PATH,
    STOP_HOTKEY_TEXT,
    TARGET_EXE,
    VK_LBUTTON,
    VK_RBUTTON,
    cursor_position as _cursor_position,
    is_admin as _is_admin,
    key_down as _key_down,
    launch_shortcut_elevated as _launch_shortcut_elevated,
    make_file_logger,
    normalize_point as _normalize_point,
    point_inside_rect as _point_inside_rect,
    prepare_repo_imports,
    relaunch_as_admin as _relaunch_as_admin,
    resolve_learning_shortcut_path as _resolve_learning_shortcut_path,
    stop_hotkey_pressed as _stop_hotkey_pressed,
    wait_for_window_rect as _wait_for_window_rect,
)

LOG_PATH = REPO_ROOT / "logs" / "general_click_elements_learner.log"
SESSION_SECONDS = 120
_log = make_file_logger(LOG_PATH)


def parse_args():
    parser = argparse.ArgumentParser(description="Sessione elevata di learning generale sugli elementi cliccati.")
    parser.add_argument("--seconds", type=int, default=SESSION_SECONDS, help="Durata sessione in secondi.")
    return parser.parse_args()


def main() -> int:
    os.chdir(REPO_ROOT)
    prepare_repo_imports()
    args = parse_args()
    session_seconds = max(10, int(args.seconds))

    if not _is_admin():
        return _relaunch_as_admin(__file__)

    from repositories.database import (
        setup_backup_table,
        setup_game_elements_table,
        setup_main_table,
        setup_scheduled_tasks_table,
        setup_task_macro_sequence_table,
        setup_ui_graph_macro_links_table,
    )
    from repositories.game_element_repository import get_game_element_by_id, update_game_element
    from repositories.macro_repository import SYSTEM_MACRO_KIND, salva_macro_test
    from services.click_element_capture_service import (
        DOOMSDAY_GRAPH_ID,
        EMPTY_SPACE_DISMISSAL_NODE_ID,
        classify_horizontal_band_from_bottom,
        classify_doomsday_view,
        is_empty_space_popup_dismissal_band,
        register_recorded_click_element,
    )
    from services.system_macro_service import (
        ensure_launch_game_system_macro,
        get_process_client_rect,
        is_process_running,
        remember_local_workstation_context,
        save_launch_game_local_variant,
    )

    setup_main_table()
    setup_backup_table()
    setup_scheduled_tasks_table()
    setup_task_macro_sequence_table()
    setup_game_elements_table()
    setup_ui_graph_macro_links_table()

    context = remember_local_workstation_context()
    ensure_launch_game_system_macro()
    shortcut_path = _resolve_learning_shortcut_path(SHORTCUT_PATH)
    save_launch_game_local_variant(shortcut_path)

    _log("=" * 76)
    _log("Doomsday general click element learner - sessione elevata")
    _log(f"Postazione: {context['host_name']}\\{context['user_name']}")
    _log(f"Collegamento usato: {shortcut_path}")
    _log("=" * 76)

    if not is_process_running(TARGET_EXE):
        _launch_shortcut_elevated(shortcut_path)
        _log(f"Avvio elevato richiesto tramite {shortcut_path}")
    else:
        _log(f"{TARGET_EXE} risulta gia' in esecuzione: uso la finestra esistente per evitare doppio avvio.")

    if not _wait_for_window_rect(get_process_client_rect, TARGET_EXE, timeout_sec=120):
        _log(f"Finestra client di {TARGET_EXE} non trovata entro il timeout.")
        return 1

    _log("")
    _log(f"Monitoraggio click attivo per {session_seconds} secondi.")
    _log(f"Puoi fermare prima con {STOP_HOTKEY_TEXT}.")
    _log("Clicca liberamente elementi utili del gioco: li censisco con immagine, vista e zona schermo.")
    _log("")

    session_name = (
        "Sistema - General click elements - "
        f"Locale {context['host_name']}\\{context['user_name']} - "
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    started_at = time.monotonic()
    deadline = started_at + session_seconds
    events = []
    observations = []
    previous_element_id = None
    previous_left = False
    previous_right = False
    last_click_at = 0.0

    while time.monotonic() < deadline:
        if _stop_hotkey_pressed():
            _log(f"{STOP_HOTKEY_TEXT} ricevuto: salvo la sessione.")
            break

        window_rect = get_process_client_rect(TARGET_EXE)
        if not window_rect:
            time.sleep(0.1)
            continue

        cursor_x, cursor_y = _cursor_position()
        left_down = _key_down(VK_LBUTTON)
        right_down = _key_down(VK_RBUTTON)
        now_monotonic = time.monotonic()

        clicked_button = None
        if left_down and not previous_left:
            clicked_button = "left"
        elif right_down and not previous_right:
            clicked_button = "right"

        if clicked_button and _point_inside_rect(cursor_x, cursor_y, window_rect) and now_monotonic - last_click_at > 0.12:
            event_time_ms = int((now_monotonic - started_at) * 1000)
            normalized_x, normalized_y = _normalize_point(cursor_x, cursor_y, window_rect)
            view_node_id = _safe_classify_view(classify_doomsday_view, window_rect)
            screen_zone = _screen_zone(normalized_x, normalized_y)
            horizontal_band_from_bottom = classify_horizontal_band_from_bottom(normalized_y)
            empty_space_dismissal_candidate = is_empty_space_popup_dismissal_band(normalized_y)
            semantic_node_id = EMPTY_SPACE_DISMISSAL_NODE_ID if empty_space_dismissal_candidate else view_node_id
            event_data = {
                "time": event_time_ms,
                "type": "mouse",
                "event": "down",
                "button": clicked_button,
                "normalized_x": round(normalized_x, 4),
                "normalized_y": round(normalized_y, 4),
                "ui_graph_id": DOOMSDAY_GRAPH_ID,
                "ui_node_id": semantic_node_id,
            }
            try:
                observation = register_recorded_click_element(
                    macro_name=session_name,
                    event_time_ms=event_time_ms,
                    button=clicked_button,
                    abs_x=cursor_x,
                    abs_y=cursor_y,
                    normalized_x=event_data["normalized_x"],
                    normalized_y=event_data["normalized_y"],
                    window_rect=window_rect,
                    view_node_id=semantic_node_id,
                    sequence_index=len(events) + 1,
                    previous_element_id=previous_element_id,
                )
                event_data["game_element_id"] = observation.element_id
                if previous_element_id:
                    event_data["previous_game_element_id"] = previous_element_id
                observations.append(observation)
                _append_semantic_note(
                    get_game_element_by_id,
                    update_game_element,
                    observation.element_id,
                    view_node_id=view_node_id,
                    semantic_node_id=semantic_node_id,
                    screen_zone=screen_zone,
                    horizontal_band_from_bottom=horizontal_band_from_bottom,
                    empty_space_dismissal_candidate=empty_space_dismissal_candidate,
                    normalized_x=event_data["normalized_x"],
                    normalized_y=event_data["normalized_y"],
                    session_name=session_name,
                    sequence_index=len(events) + 1,
                    previous_element_id=previous_element_id,
                )
                previous_element_id = observation.element_id
                _log(
                    f"Click censito #{len(observations)}: element_id={observation.element_id}, "
                    f"vista={view_node_id}, nodo={semantic_node_id}, zona={screen_zone}, "
                    f"banda={horizontal_band_from_bottom}, pos=({cursor_x},{cursor_y})"
                )
            except Exception as exc:
                _log(f"Click rilevato ma censimento fallito in ({cursor_x},{cursor_y}): {exc}")
            events.append(event_data)
            last_click_at = now_monotonic

        previous_left = left_down
        previous_right = right_down
        time.sleep(0.02)

    if not events:
        _log("Nessun click acquisito; non salvo la macro componente.")
        return 1

    payload = {
        "parent_system_key": "launch_game",
        "component_system_key": "general_click_elements_learning",
        "variant_scope": "local_workstation",
        "host_name": context["host_name"],
        "user_name": context["user_name"],
        "shortcut_path": shortcut_path,
        "target_exe": TARGET_EXE,
        "recorded_click_element_ids": [item.element_id for item in observations],
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "duration_seconds": session_seconds,
        "stop_hotkey": STOP_HOTKEY_TEXT,
        "objective": "Censire elementi grafici utili generici, con vista e zona semantica.",
    }
    macro_id = salva_macro_test(
        session_name,
        "Sessione elevata di censimento elementi utili cliccati nel gioco.",
        max(1, int((events[-1].get("time") or 0) / 1000) + 1),
        TARGET_EXE,
        events,
        macro_kind=SYSTEM_MACRO_KIND,
        is_protected=False,
        system_key="general_click_elements_learning",
        system_payload=payload,
    )
    _log("")
    _log(f"Macro componente salvata con ID {macro_id}: {session_name}")
    _log(f"Click acquisiti: {len(events)}")
    _log(f"Elementi grafici censiti: {len(observations)}")
    _log("Puoi chiudere questa finestra.")
    return 0


def _append_semantic_note(
    get_game_element_by_id,
    update_game_element,
    element_id,
    *,
    view_node_id,
    semantic_node_id,
    screen_zone,
    horizontal_band_from_bottom,
    empty_space_dismissal_candidate,
    normalized_x,
    normalized_y,
    session_name,
    sequence_index,
    previous_element_id,
):
    element = get_game_element_by_id(element_id)
    if not element:
        return
    desc = element.get("descrizione") or ""
    note = {
        "source": "general_click_elements_learning",
        "view_node_id": view_node_id,
        "semantic_node_id": semantic_node_id,
        "screen_zone": screen_zone,
        "horizontal_band_from_bottom": horizontal_band_from_bottom,
        "empty_space_popup_dismissal_candidate": empty_space_dismissal_candidate,
        "normalized_position": {"x": normalized_x, "y": normalized_y},
        "session_name": session_name,
        "sequence_index": sequence_index,
        "previous_element_id": previous_element_id,
        "sequence_relation": "after_previous_click" if previous_element_id else "sequence_start",
        "semantic_status": "needs_human_function_label",
    }
    semantic_block = "\n\nGENERAL_CLICK_SEMANTIC_NOTE:" + json.dumps(note, ensure_ascii=False, sort_keys=True)
    update_game_element(element_id, descrizione=desc + semantic_block)


def _safe_classify_view(classify_doomsday_view, window_rect):
    try:
        return classify_doomsday_view(window_rect)
    except Exception as exc:
        _log(f"Vista non classificabile per questo click: {exc}")
        return "unknown_main_view"


def _screen_zone(normalized_x, normalized_y):
    horizontal = "left" if normalized_x < 0.33 else "center" if normalized_x < 0.66 else "right"
    vertical = "top" if normalized_y < 0.33 else "middle" if normalized_y < 0.66 else "bottom"
    return f"{vertical}_{horizontal}"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        _log(f"ERRORE FATALE learner: {type(exc).__name__}: {exc}")
        time.sleep(10)
        raise
