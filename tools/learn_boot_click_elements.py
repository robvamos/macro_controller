"""Elevated learner for Doomsday boot/startup click elements."""

from __future__ import annotations

import argparse
from datetime import datetime
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
from core.paths import LOGS_DIR

LOG_PATH = LOGS_DIR / "boot_click_elements_learner.log"
_log = make_file_logger(LOG_PATH)


def parse_args():
    parser = argparse.ArgumentParser(description="Sessione elevata di learning sugli elementi di boot del gioco.")
    parser.add_argument("--shortcut", default=None, help="Collegamento esplicito da usare al posto di quello risolto per la postazione.")
    parser.add_argument(
        "--network-observation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Collega la sessione al proxy metadata-only per PID (attivo per default).",
    )
    return parser.parse_args()


def main() -> int:
    os.chdir(REPO_ROOT)
    prepare_repo_imports()
    args = parse_args()

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
    from repositories.macro_repository import SYSTEM_MACRO_KIND, salva_macro_test
    from services.click_element_capture_service import DOOMSDAY_GRAPH_ID, register_recorded_click_element
    from services.learning_network_correlation_service import (
        append_learning_network_marker,
        build_network_correlation_window,
        capture_network_cursor,
        find_process_pid,
        start_or_attach_learning_network_observation,
        stop_owned_learning_network_observation,
    )
    from services.system_macro_service import (
        ensure_launch_game_system_macro,
        get_local_launch_context,
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
    shortcut_path = (args.shortcut or _resolve_learning_shortcut_path(SHORTCUT_PATH)).strip()
    save_launch_game_local_variant(shortcut_path)

    _log("=" * 76)
    _log("Doomsday boot click element learner - sessione elevata")
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
    _log("Ora clicca gli elementi dei popup/boot che vuoi censire.")
    _log(f"Premi {STOP_HOTKEY_TEXT} quando sei arrivato all'interfaccia giocabile.")
    _log("I click vengono acquisiti solo se il cursore e' dentro la finestra del gioco.")
    _log("")

    session_name = (
        "Sistema - Boot click elements - "
        f"Locale {context['host_name']}\\{context['user_name']} - "
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    network_observation = start_or_attach_learning_network_observation(
        target_pid=find_process_pid(TARGET_EXE) or 0,
        duration_seconds=15 * 60,
        enabled=bool(args.network_observation),
    )
    if network_observation.get("status") == "active":
        _log(
            "Osservazione rete collegata: "
            f"sessione={network_observation.get('network_session_id')}, "
            f"pid={network_observation.get('proxy_pid')}"
        )
    else:
        _log(
            "Osservazione rete non disponibile; il learning boot continua con copertura parziale: "
            f"{network_observation.get('reason', 'unknown')}"
        )
    started_at = time.monotonic()
    events = []
    observations = []
    previous_left = False
    previous_right = False
    last_click_at = 0.0

    while True:
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
            sequence_index = len(events) + 1
            normalized_x, normalized_y = _normalize_point(cursor_x, cursor_y, window_rect)
            event_data = {
                "time": event_time_ms,
                "type": "mouse",
                "event": "down",
                "button": clicked_button,
                "normalized_x": round(normalized_x, 4),
                "normalized_y": round(normalized_y, 4),
                "ui_graph_id": DOOMSDAY_GRAPH_ID,
                "ui_node_id": "boot_overlay_layer",
            }
            network_before = capture_network_cursor(network_observation)
            try:
                append_learning_network_marker(
                    binding=network_observation,
                    learning_session_name=session_name,
                    sequence_index=sequence_index,
                    event_time_ms=event_time_ms,
                    ui_node_id="boot_overlay_layer",
                    network_cursor=network_before,
                )
            except Exception as network_exc:
                _log(f"Marcatore rete non aggiornato: {network_exc}")
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
                    view_node_id="boot_overlay_layer",
                )
                event_data["game_element_id"] = observation.element_id
                observations.append(observation)
                _log(
                    f"Click censito #{len(observations)}: element_id={observation.element_id}, "
                    f"nome={observation.element_name}, pos=({cursor_x},{cursor_y})"
                )
            except Exception as exc:
                _log(f"Click rilevato ma censimento fallito in ({cursor_x},{cursor_y}): {exc}")
            event_data["network_correlation"] = build_network_correlation_window(
                binding=network_observation,
                before=network_before,
                after=capture_network_cursor(network_observation),
            )
            events.append(event_data)
            last_click_at = now_monotonic

        previous_left = left_down
        previous_right = right_down
        time.sleep(0.02)

    if not events:
        stop_owned_learning_network_observation(network_observation)
        _log("Nessun click acquisito; non salvo la macro componente.")
        return 1

    payload = {
        "parent_system_key": "launch_game",
        "component_system_key": "launch_game_boot_click_elements",
        "variant_scope": "local_workstation",
        "host_name": context["host_name"],
        "user_name": context["user_name"],
        "shortcut_path": shortcut_path,
        "target_exe": TARGET_EXE,
        "recorded_click_element_ids": [item.element_id for item in observations],
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "stop_hotkey": STOP_HOTKEY_TEXT,
        "objective": "Censire elementi grafici utili nella fase di boot/startup del gioco.",
        "network_observation_session_id": network_observation.get("network_session_id"),
        "network_observation_status": network_observation.get("status"),
    }
    macro_id = salva_macro_test(
        session_name,
        "Sessione elevata di censimento elementi cliccati durante boot/startup Doomsday.",
        max(1, int((events[-1].get("time") or 0) / 1000) + 1),
        TARGET_EXE,
        events,
        macro_kind=SYSTEM_MACRO_KIND,
        is_protected=False,
        system_key="launch_game_boot_click_elements",
        system_payload=payload,
    )
    _log("")
    _log(f"Macro componente salvata con ID {macro_id}: {session_name}")
    stop_owned_learning_network_observation(network_observation)
    _log(f"Click acquisiti: {len(events)}")
    _log(f"Elementi grafici censiti: {len(observations)}")
    _log("Puoi chiudere questa finestra.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        _log(f"ERRORE FATALE learner: {type(exc).__name__}: {exc}")
        time.sleep(10)
        raise
