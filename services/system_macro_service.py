from __future__ import annotations

import os
import time
from datetime import datetime

import psutil

from core.config_store import load_app_config, save_app_config
from doomsday.vision.ui_graph import build_default_doomsday_ui_graph, evaluate_ui_graph
from repositories.macro_repository import (
    SYSTEM_MACRO_KIND,
    get_all_macros,
    get_macro_metadata_by_name,
    salva_macro_test,
    update_macro_full,
)


LAUNCH_GAME_SYSTEM_KEY = "launch_game"
LAUNCH_GAME_SYSTEM_NAME = "Sistema · Avvia Doomsday"
LOCAL_WORKSTATION_VARIANT_SCOPE = "local_workstation"
DEFAULT_LAUNCH_SHORTCUT_PATH = "C:/Users/Public/Desktop/Doomsday.lnk"
DEFAULT_BLOCKING_POPUP_ELEMENT_NAME = "popup_exit_close_symbol"
LAUNCH_GAME_OBJECTIVE = (
    "Arrivare all'interfaccia del gioco pronta all'uso dopo avvio, fullscreen, caricamento "
    "e rimozione dei popup iniziali bloccanti."
)


def get_launch_game_system_macro_definition():
    config = load_app_config()
    settings = config.get("system_macros", {}).get("launch_game", {})
    shortcut_path = settings.get("shortcut_path", DEFAULT_LAUNCH_SHORTCUT_PATH)
    target_exe = settings.get("target_exe", "Doomsday.exe")
    return {
        "name": LAUNCH_GAME_SYSTEM_NAME,
        "description": (
            "Macro di sistema che avvia il gioco se necessario e lo porta fino "
            "all'interfaccia pronta, superando fullscreen, caricamento e popup iniziali."
        ),
        "duration_sec": 1,
        "target_exe": target_exe,
        "system_key": LAUNCH_GAME_SYSTEM_KEY,
        "payload": {
            "shortcut_path": shortcut_path,
            "target_exe": target_exe,
            "fullscreen_poll_interval_sec": settings.get("fullscreen_poll_interval_sec", 1),
            "fullscreen_timeout_sec": settings.get("fullscreen_timeout_sec", 180),
            "initial_popup_poll_interval_sec": settings.get("initial_popup_poll_interval_sec", 10),
            "blocking_popup_element_name": settings.get(
                "blocking_popup_element_name",
                DEFAULT_BLOCKING_POPUP_ELEMENT_NAME,
            ),
            "blocking_popup_match_threshold": settings.get("blocking_popup_match_threshold", 0.85),
            "objective": LAUNCH_GAME_OBJECTIVE,
            "workflow_stages": [
                "launch_if_needed",
                "wait_for_fullscreen",
                "wait_for_game_loaded",
                "dismiss_initial_blocking_popups",
                "reach_playable_game_interface",
            ],
            "post_fullscreen_status": "pending_game_loaded_check",
            "initial_popup_recovery_status": "pending_recovery_definition",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
    }


def ensure_launch_game_system_macro():
    definition = get_launch_game_system_macro_definition()
    existing = get_macro_metadata_by_name(definition["name"])
    if not existing:
        return salva_macro_test(
            definition["name"],
            definition["description"],
            definition["duration_sec"],
            definition["target_exe"],
            [],
            macro_kind=SYSTEM_MACRO_KIND,
            is_protected=True,
            system_key=definition["system_key"],
            system_payload=definition["payload"],
        )

    current_payload = existing.get("system_payload") or {}
    payload = dict(current_payload)
    payload.update(definition["payload"])
    update_macro_full(
        existing["id"],
        definition["name"],
        definition["description"],
        definition["duration_sec"],
        definition["target_exe"],
        [],
        save_backup=False,
    )
    _update_system_fields(existing["id"], definition["system_key"], payload, is_protected=True)
    return existing["id"]


def _update_system_fields(macro_id, system_key, payload, *, is_protected):
    from repositories.database import connect_db
    import json

    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE Macro
            SET macro_kind = ?, is_protected = ?, system_key = ?, system_payload = ?, data_ultima_modifica = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (SYSTEM_MACRO_KIND, 1 if is_protected else 0, system_key, json.dumps(payload, ensure_ascii=False), macro_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_local_launch_context():
    return {
        "host_name": os.environ.get("COMPUTERNAME") or "HOST",
        "user_name": os.environ.get("USERNAME") or "USER",
    }


def remember_local_workstation_context():
    """Persist the current workstation identity so startup can select local variants."""
    context = get_local_launch_context()
    config = load_app_config()
    local_config = config.setdefault("local_workstation", {})
    local_config.update(
        {
            "host_name": context["host_name"],
            "user_name": context["user_name"],
            "last_seen_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    save_app_config(config)
    return context


def build_local_launch_game_macro_name(*, host_name, user_name):
    return f"{LAUNCH_GAME_SYSTEM_NAME} · Locale {host_name}\\{user_name}"


def get_local_launch_game_variant_for_current_context():
    context = get_local_launch_context()
    matching_variants = []
    for macro in get_all_macros():
        if macro.get("system_key") != LAUNCH_GAME_SYSTEM_KEY or macro.get("macro_kind") != SYSTEM_MACRO_KIND:
            continue
        payload = macro.get("system_payload") or {}
        if payload.get("variant_scope") != LOCAL_WORKSTATION_VARIANT_SCOPE:
            continue
        if payload.get("host_name") == context["host_name"] and payload.get("user_name") == context["user_name"]:
            matching_variants.append(macro)
    if not matching_variants:
        return None
    matching_variants.sort(
        key=lambda item: (
            item.get("data_ultima_modifica") or "",
            item.get("data_creazione") or "",
            int(item.get("id") or 0),
        ),
        reverse=True,
    )
    return matching_variants[0]


def save_launch_game_local_variant(shortcut_path, source_macro_metadata=None):
    normalized_shortcut = (shortcut_path or "").strip()
    if not normalized_shortcut:
        raise ValueError("Inserisci un collegamento valido per avviare il gioco.")

    source_macro_metadata = source_macro_metadata or get_macro_metadata_by_name(LAUNCH_GAME_SYSTEM_NAME)
    definition = get_launch_game_system_macro_definition()
    base_payload = dict(definition["payload"])
    if source_macro_metadata:
        base_payload.update(source_macro_metadata.get("system_payload") or {})

    context = get_local_launch_context()
    local_name = build_local_launch_game_macro_name(**context)
    payload = dict(base_payload)
    payload.update(
        {
            "shortcut_path": normalized_shortcut,
            "variant_scope": LOCAL_WORKSTATION_VARIANT_SCOPE,
            "host_name": context["host_name"],
            "user_name": context["user_name"],
            "source_macro_name": (source_macro_metadata or {}).get("nome") or LAUNCH_GAME_SYSTEM_NAME,
            "source_system_key": LAUNCH_GAME_SYSTEM_KEY,
            "remembered_state": True,
            "last_local_update": datetime.now().isoformat(timespec="seconds"),
        }
    )

    target_exe = payload.get("target_exe") or (source_macro_metadata or {}).get("eseguibile") or definition["target_exe"]
    description = (
        "Variante locale della macro di sistema per avviare il gioco con il collegamento "
        "specifico di questa postazione e proseguire verso l'interfaccia pronta."
    )
    existing = get_local_launch_game_variant_for_current_context()
    if existing:
        update_macro_full(
            existing["id"],
            existing["nome"] or local_name,
            description,
            1,
            target_exe,
            [],
            save_backup=False,
        )
        _update_system_fields(existing["id"], LAUNCH_GAME_SYSTEM_KEY, payload, is_protected=False)
        return existing["id"], existing["nome"] or local_name, False

    macro_id = salva_macro_test(
        local_name,
        description,
        1,
        target_exe,
        [],
        macro_kind=SYSTEM_MACRO_KIND,
        is_protected=False,
        system_key=LAUNCH_GAME_SYSTEM_KEY,
        system_payload=payload,
    )
    return macro_id, local_name, True


def resolve_launch_game_macro_for_current_context(macro_metadata):
    """Se esiste una variante locale DB per questa postazione, usa quella come sorgente reale."""
    if macro_metadata.get("system_key") != LAUNCH_GAME_SYSTEM_KEY:
        return macro_metadata

    payload = macro_metadata.get("system_payload") or {}
    if payload.get("variant_scope") == LOCAL_WORKSTATION_VARIANT_SCOPE:
        return macro_metadata

    local_variant = get_local_launch_game_variant_for_current_context()
    return local_variant or macro_metadata


def resolve_launch_shortcut_for_current_context(source_macro_metadata=None):
    """Restituisce il collegamento di avvio da usare per questa postazione."""
    local_variant = get_local_launch_game_variant_for_current_context()
    if local_variant:
        payload = local_variant.get("system_payload") or {}
        shortcut_path = (payload.get("shortcut_path") or "").strip()
        if shortcut_path:
            return shortcut_path

    source_payload = (source_macro_metadata or {}).get("system_payload") or {}
    source_shortcut = (source_payload.get("shortcut_path") or "").strip()
    if source_shortcut:
        return source_shortcut

    definition = get_launch_game_system_macro_definition()
    return (definition["payload"].get("shortcut_path") or DEFAULT_LAUNCH_SHORTCUT_PATH).strip()


def is_process_running(exe_name):
    target = (exe_name or "").lower()
    if not target:
        return False
    for proc in psutil.process_iter(["name"]):
        try:
            if (proc.info.get("name") or "").lower() == target:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def run_system_macro(macro_metadata, log_callback):
    if macro_metadata.get("system_key") != LAUNCH_GAME_SYSTEM_KEY:
        raise ValueError(f"Macro di sistema non gestita: {macro_metadata.get('system_key')}")

    effective_macro = resolve_launch_game_macro_for_current_context(macro_metadata)
    if effective_macro is not macro_metadata and log_callback:
        effective_payload = effective_macro.get("system_payload") or {}
        log_callback(
            (
                "ℹ️ Trovata variante locale per questa postazione. "
                f"Uso il collegamento ricordato: '{effective_payload.get('shortcut_path')}'."
            ),
            level="INFO",
        )

    payload = effective_macro.get("system_payload") or {}
    shortcut_path = payload.get("shortcut_path")
    target_exe = payload.get("target_exe") or effective_macro.get("eseguibile")
    poll_interval_sec = max(1, int(payload.get("fullscreen_poll_interval_sec", 1)))
    timeout_sec = max(1, int(payload.get("fullscreen_timeout_sec", 180)))
    initial_popup_poll_interval_sec = max(1, int(payload.get("initial_popup_poll_interval_sec", 10)))
    blocking_popup_element_name = payload.get("blocking_popup_element_name") or DEFAULT_BLOCKING_POPUP_ELEMENT_NAME
    blocking_popup_match_threshold = float(payload.get("blocking_popup_match_threshold", 0.85))

    fullscreen_result = None
    if is_process_running(target_exe):
        if log_callback:
            log_callback(f"ℹ️ '{target_exe}' è già attivo. Nessun avvio necessario.", level="INFO")
        fullscreen_result = wait_for_game_fullscreen(
            target_exe,
            poll_interval_sec=poll_interval_sec,
            timeout_sec=timeout_sec,
            log_callback=log_callback,
            launched_now=False,
        )
    else:
        if not shortcut_path or not os.path.exists(shortcut_path):
            raise FileNotFoundError(f"Collegamento di avvio non trovato: {shortcut_path}")

        os.startfile(shortcut_path)
        if log_callback:
            log_callback(f"🚀 Avvio richiesto per '{target_exe}' tramite '{shortcut_path}'.", level="INFO")
        fullscreen_result = wait_for_game_fullscreen(
            target_exe,
            poll_interval_sec=poll_interval_sec,
            timeout_sec=timeout_sec,
            log_callback=log_callback,
            launched_now=True,
        )

    if not fullscreen_result.get("fullscreen_ready"):
        return fullscreen_result

    return wait_for_initial_blocking_popup(
        target_exe,
        poll_interval_sec=initial_popup_poll_interval_sec,
        element_name=blocking_popup_element_name,
        match_threshold=blocking_popup_match_threshold,
        log_callback=log_callback,
        base_result=fullscreen_result,
    )


def wait_for_game_fullscreen(target_exe, *, poll_interval_sec, timeout_sec, log_callback, launched_now):
    """Attende il fullscreen; dopo quello i prossimi step sono caricamento e popup iniziali."""
    if log_callback:
        log_callback(
            (
                f"🖥️ Avvio polling fullscreen per '{target_exe}' ogni {poll_interval_sec}s "
                f"(timeout {timeout_sec}s). Obiettivo finale: interfaccia di gioco pronta."
            ),
            level="INFO",
        )

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if is_process_fullscreen(target_exe):
            if log_callback:
                log_callback(
                    (
                        f"✅ '{target_exe}' è passato in full screen. "
                        "Prossimi step: attendere fine caricamento e liberarsi dei popup iniziali bloccanti."
                    ),
                    level="INFO",
                )
            return {
                "launched": launched_now,
                "already_running": not launched_now,
                "fullscreen_ready": True,
                "fallback_required": False,
                "game_interface_ready": False,
                "next_step": "wait_for_initial_blocking_popup",
                "blocking_popups_pending": True,
            }
        time.sleep(poll_interval_sec)

    if log_callback:
        log_callback(
            f"⚠️ '{target_exe}' non è passato in full screen entro {timeout_sec} secondi. Serve procedura di fallback.",
            level="WARNING",
        )
    return {
        "launched": launched_now,
        "already_running": not launched_now,
        "fullscreen_ready": False,
        "fallback_required": True,
        "game_interface_ready": False,
        "next_step": "fallback_required",
        "blocking_popups_pending": True,
    }


def wait_for_initial_blocking_popup(target_exe, *, poll_interval_sec, element_name, match_threshold, log_callback, base_result):
    """Dopo il fullscreen osserva tutta la finestra di gioco finché compare il popup bloccante iniziale."""
    ui_graph = build_default_doomsday_ui_graph()
    if log_callback:
        log_callback(
            (
                f"👁️ Avvio polling grafico popup su '{target_exe}' ogni {poll_interval_sec}s. "
                f"Elemento atteso: '{element_name}'."
            ),
            level="INFO",
        )

    while True:
        window_rect = get_process_client_rect(target_exe)
        if window_rect:
            graph_evaluation = evaluate_ui_graph(ui_graph, window_rect)
            popup_node_result = graph_evaluation.get_node_result("initial_blocking_popup_close_symbol")
            search_result = None
            if popup_node_result and popup_node_result.condition_results:
                search_result = popup_node_result.condition_results[0].search_result
            if popup_node_result and popup_node_result.active and search_result and search_result.found:
                if log_callback:
                    log_callback(
                        (
                            f"🧩 Popup bloccante rilevato con compatibilità {search_result.score:.2f} "
                            f"in {search_result.center}. Pronto per la futura procedura di uscita."
                        ),
                        level="INFO",
                    )
                result = dict(base_result)
                result.update(
                    {
                        "blocking_popup_detected": True,
                        "blocking_popups_pending": True,
                        "game_interface_ready": False,
                        "fallback_required": False,
                        "next_step": "dismiss_initial_blocking_popup",
                        "blocking_popup_match_score": search_result.score,
                        "blocking_popup_center": search_result.center,
                        "blocking_popup_element_name": search_result.matched_element_name or element_name,
                        "blocking_popup_search_result": search_result,
                        "ui_graph_id": graph_evaluation.graph_id,
                        "ui_graph_active_nodes": graph_evaluation.active_node_ids,
                    }
                )
                return result
        elif log_callback:
            log_callback(
                f"⚠️ Finestra di '{target_exe}' non disponibile durante il controllo popup. Continuo ad attendere.",
                level="WARNING",
            )

        time.sleep(poll_interval_sec)


def is_process_fullscreen(target_exe, tolerance_px=8):
    """Verifica se la finestra client del processo target occupa il monitor attivo."""
    window_rect = get_process_client_rect(target_exe)
    if not window_rect:
        return False

    monitor_rect = get_monitor_rect_for_window(window_rect)
    if not monitor_rect:
        return False

    left, top, right, bottom = window_rect
    mon_left, mon_top, mon_right, mon_bottom = monitor_rect
    return (
        abs(left - mon_left) <= tolerance_px
        and abs(top - mon_top) <= tolerance_px
        and abs(right - mon_right) <= tolerance_px
        and abs(bottom - mon_bottom) <= tolerance_px
    )


def get_process_client_rect(target_exe):
    try:
        import win32gui
        import win32process
    except ImportError:
        return None

    windows = []
    win32gui.EnumWindows(lambda hwnd, acc: acc.append(hwnd), windows)
    for hwnd in windows:
        if not win32gui.IsWindowVisible(hwnd):
            continue
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            if (proc.name() or "").lower() != (target_exe or "").lower():
                continue
            client_left, client_top, client_right, client_bottom = win32gui.GetClientRect(hwnd)
            point_tl = win32gui.ClientToScreen(hwnd, (client_left, client_top))
            point_br = win32gui.ClientToScreen(hwnd, (client_right, client_bottom))
            return (point_tl[0], point_tl[1], point_br[0], point_br[1])
        except (psutil.NoSuchProcess, psutil.AccessDenied, win32gui.error):
            continue
        except Exception:
            continue
    return None


def get_monitor_rect_for_window(window_rect):
    try:
        import win32api
    except ImportError:
        return None

    try:
        monitor = win32api.MonitorFromRect(window_rect)
        monitor_info = win32api.GetMonitorInfo(monitor)
        return monitor_info.get("Monitor")
    except Exception:
        return None
