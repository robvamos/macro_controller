"""Run an elevated assisted session to learn startup popup cleanup clicks."""

from __future__ import annotations

from datetime import datetime
import os
import time

from learning_mode_common import (
    REPO_ROOT,
    SHORTCUT_PATH,
    TARGET_EXE,
    is_admin as _is_admin,
    launch_shortcut_elevated as _launch_shortcut_elevated,
    make_file_logger,
    prepare_repo_imports,
    relaunch_as_admin as _relaunch_as_admin,
)

HOTKEY = "ctrl+alt+s"
COMPONENT_SYSTEM_KEY = "launch_game_popup_cleanup"
LOG_PATH = REPO_ROOT / "logs" / "startup_popup_learner.log"
_log = make_file_logger(LOG_PATH)


def main() -> int:
    os.chdir(REPO_ROOT)
    prepare_repo_imports()

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
    from services.system_macro_service import (
        ensure_launch_game_system_macro,
        get_local_launch_context,
        is_process_running,
        remember_local_workstation_context,
        save_launch_game_local_variant,
    )
    import keyboard
    import macro_controller

    setup_main_table()
    setup_backup_table()
    setup_scheduled_tasks_table()
    setup_task_macro_sequence_table()
    setup_game_elements_table()
    setup_ui_graph_macro_links_table()

    context = remember_local_workstation_context()
    ensure_launch_game_system_macro()
    save_launch_game_local_variant(SHORTCUT_PATH)

    _print_header(context)
    if not is_process_running(TARGET_EXE):
        _launch_shortcut_elevated(SHORTCUT_PATH)
        _log(f"Avvio elevato richiesto tramite {SHORTCUT_PATH}")
    else:
        _log(f"{TARGET_EXE} risulta gia' in esecuzione: usero' la finestra attiva.")

    if not _wait_for_process(is_process_running, TARGET_EXE, timeout_sec=120):
        _log(f"{TARGET_EXE} non rilevato entro il timeout; sessione annullata.")
        return 1

    _log("Processo rilevato. Porta il gioco in primo piano e chiudi manualmente i popup iniziali.")
    _log(f"Quando arrivi all'interfaccia giocabile premi {HOTKEY.upper()} per fermare e salvare.")
    _log("")

    macro_name = (
        "Sistema - Startup popup cleanup - "
        f"Locale {context['host_name']}\\{context['user_name']} - "
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    def log_callback(message, level="INFO", **_kwargs):
        _log(f"[{level}] {message}")

    def stop_recording():
        _log(f"\nHotkey {HOTKEY} ricevuta: fermo la registrazione...")
        macro_controller.stop_recording(log_callback=log_callback)

    keyboard.add_hotkey(HOTKEY, stop_recording)
    try:
        events = macro_controller.registra_eventi(
            nome_macro=macro_name,
            durata_sec=0,
            target_exe=TARGET_EXE,
            log_callback=log_callback,
        )
    finally:
        try:
            keyboard.remove_hotkey(HOTKEY)
        except Exception:
            pass

    if not events:
        _log("Nessun evento utile registrato; non salvo la macro componente.")
        return 1

    element_ids = [
        event.get("game_element_id")
        for event in events
        if event.get("type") == "mouse" and event.get("event") == "down" and event.get("game_element_id")
    ]
    payload = {
        "parent_system_key": "launch_game",
        "component_system_key": COMPONENT_SYSTEM_KEY,
        "variant_scope": "local_workstation",
        "host_name": context["host_name"],
        "user_name": context["user_name"],
        "shortcut_path": SHORTCUT_PATH,
        "target_exe": TARGET_EXE,
        "recorded_click_element_ids": element_ids,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "stop_hotkey": HOTKEY,
        "objective": "Liberare i popup iniziali fino al raggiungimento dell'interfaccia giocabile.",
    }
    macro_id = salva_macro_test(
        macro_name,
        "Componente locale appresa per liberare i popup iniziali dello startup Doomsday.",
        max(1, int((events[-1].get("time") or 0) / 1000) + 1),
        TARGET_EXE,
        events,
        log_callback=log_callback,
        macro_kind=SYSTEM_MACRO_KIND,
        is_protected=False,
        system_key=COMPONENT_SYSTEM_KEY,
        system_payload=payload,
    )
    _log("")
    _log(f"Macro componente salvata con ID {macro_id}: {macro_name}")
    _log(f"Elementi cliccati censiti e agganciati: {len(element_ids)}")
    _log("Puoi chiudere questa finestra.")
    return 0


def _print_header(context):
    _log("=" * 72)
    _log("Doomsday startup popup learner - sessione elevata")
    _log(f"Postazione: {context['host_name']}\\{context['user_name']}")
    _log("=" * 72)


def _wait_for_process(is_process_running, target_exe, *, timeout_sec):
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if is_process_running(target_exe):
            return True
        time.sleep(1)
    return False


if __name__ == "__main__":
    raise SystemExit(main())
