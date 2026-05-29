import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import threading
import time
import keyboard
import mouse
import json
import psutil
import win32gui
import win32process
import subprocess
import logging
import queue
import datetime
import os
import sys
from pathlib import Path
from macro_config import (
    get_debug_config,
    get_log_level,
    get_log_level_value,
    normalize_log_level,
    should_emit_log_level,
)

# Custom logging handler that sends messages to console_log
class ConsoleLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_queue = queue.Queue()
    
    def emit(self, record):
        try:
            # Format the message
            msg = self.format(record)
            # Add to queue for processing in main thread
            self.log_queue.put((record.levelname, msg))
        except Exception:
            self.handleError(record)

# Global handler instance
console_log_handler = None
file_log_handler = None
playback_debug_log_path = None

def setup_console_logging():
    """Setup centralized logging to console_log function"""
    global console_log_handler, file_log_handler, playback_debug_log_path
    debug_config = get_debug_config()
    configured_level_name = normalize_log_level(get_log_level())
    configured_level = get_log_level_value(configured_level_name)
    
    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create custom handler
    console_log_handler = ConsoleLogHandler()
    console_log_handler.setLevel(configured_level)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_log_handler.setFormatter(formatter)
    
    # Add handler to root logger
    root_logger.addHandler(console_log_handler)
    root_logger.setLevel(configured_level)

    file_log_handler = None
    playback_debug_log_path = None
    if debug_config.get("save_playback_logs"):
        logs_dir = Path(__file__).resolve().parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        log_path = logs_dir / "playback_focus_debug.log"
        playback_debug_log_path = log_path
        file_log_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_log_handler.setLevel(configured_level)
        file_log_handler.setFormatter(formatter)
        root_logger.addHandler(file_log_handler)
    
    # No parent for root; child loggers will propagate to root by default
    # Keep propagate default behavior on child loggers

def process_log_queue():
    """Process log messages from queue and send to console_log"""
    if console_log_handler and not console_log_handler.log_queue.empty():
        try:
            while not console_log_handler.log_queue.empty():
                level, message = console_log_handler.log_queue.get_nowait()
                console_log(message, level, mirror_to_file=False)
        except queue.Empty:
            pass
    
    # Schedule next check
    if root and root.winfo_exists():
        try:
            root.after(100, process_log_queue)
        except tk.TclError:
            # La finestra è stata chiusa, non programmare più chiamate
            pass

logger = logging.getLogger(__name__)
# Importa i repository e il nuovo macro_editor
from repositories.database import (
    setup_game_elements_table,
    setup_main_table,
    setup_scheduled_tasks_table,
    setup_task_macro_sequence_table,
    setup_ui_graph_macro_links_table,
)
from repositories.game_element_repository import (
    create_game_element,
    delete_game_element,
    get_all_game_elements,
    get_game_element_by_id,
    update_game_element,
)
from repositories.macro_repository import (
    delete_macro,
    duplicate_macro,
    get_all_macros,
    get_game_element_event_references,
    get_macro_metadata_by_id,
    get_macro_metadata_by_name,
    load_macro_events,
    salva_macro_test,
)
from repositories.task_repository import (
    add_macro_to_task_sequence,
    add_macro_to_task_sequence_with_order,
    clear_task_macro_sequence,
    create_scheduled_task,
    delete_scheduled_task,
    duplicate_scheduled_task,
    get_active_tasks_ordered_by_next_execution,
    get_all_scheduled_tasks,
    get_scheduled_task_by_id,
    get_task_macro_sequence,
    get_tasks_due_for_execution,
    reactivate_completed_task,
    remove_macro_from_task_sequence,
    start_task_scheduling,
    stop_task_scheduling,
    update_last_execution,
    update_macro_sequence_wait_time,
    update_scheduled_task,
)
import macro_editor # Importa il modulo macro_editor
from ui.scheduled_tasks_panel import (
    build_countdown_entries,
    build_scheduled_task_row,
    format_countdown as format_scheduled_task_countdown,
    update_action_buttons_state,
)
from ui.game_elements_panel import (
    build_game_element_details_text,
    build_game_element_row,
    compute_crop_display_size,
    map_display_selection_to_original,
    render_fullsize_image_on_canvas,
    render_preview_image,
)
from ui.macro_management_panel import build_macro_management_tab
from ui.main_window_helpers import (
    bind_main_window_events,
    build_log_console,
    build_status_bar,
)
from ui.collapsible_panel import CollapsibleSection
from ui.knowledge_graph_panel import build_knowledge_graph_tab
from ui.tab_bootstrap import build_secondary_tabs
from ui.status_console import (
    append_console_message,
    apply_status_indicator_state,
)
from core.config_store import (
    DEFAULT_APP_CONFIG,
    get_window_geometry,
    load_app_config,
    load_style_config,
    save_app_config,
    set_window_geometry,
)
from core.app_state import AppState
from core.windows_elevation import (
    build_restart_as_admin_message,
    enforce_single_macro_manager_instance,
    relaunch_current_process_as_admin,
    target_requires_elevation,
)
from services.operation_state_service import OperationStateService
from services.app_cleanup_service import cleanup_runtime_artifacts, close_logging_handlers
from services.focus_monitor_service import FocusMonitorService
from services.playback_service import PlaybackService
from services.recording_service import RecordingService
from services.system_macro_service import ensure_launch_game_system_macro, remember_local_workstation_context, run_system_macro
from services.system_macro_service import (
    LAUNCH_GAME_SYSTEM_KEY,
    get_local_launch_game_variant_for_current_context,
    save_launch_game_local_variant,
)
from services.ui_graph_macro_link_service import get_macro_plan_for_ui_node
from services.knowledge_graph_service import format_knowledge_graph_details, load_knowledge_graph_model
from services.game_element_ingestion_service import (
    build_game_element_description,
    build_game_element_ingestion_guidelines,
    build_prepared_asset_summary,
    create_or_merge_game_element,
    find_matching_game_element,
    prepare_game_element_asset,
)
from doomsday.vision.ui_graph import build_default_doomsday_ui_graph
# CORREZIONE: Cambiato 'wait_for_target_window_active_only' a 'wait_for_app_window'
from macro_controller import (
    get_game_window_rect,
    wait_for_app_window,
    stop_recording,
    registra_eventi,
    play_macro_events,
    clear_playback_stop_request,
    is_playback_stop_requested,
    request_playback_stop,
)
import task_controller # Importa il nuovo task_controller
from task_controller import test_execute_scheduled_task
import game_elements # Importa il modulo per la gestione degli elementi grafici
from game_elements import load_image_from_file, paste_image_from_clipboard, image_to_blob, blob_to_image


app_state = AppState()
state_service = OperationStateService(app_state)
focus_monitor_service = FocusMonitorService(app_state, state_service)
playback_service = PlaybackService(app_state, state_service)
recording_service = RecordingService(app_state, state_service)
config = {}
shutdown_cleanup_done = False

# Variabili globali per i pulsanti per poterli abilitare/disabilitare
new_macro_button = None # Assicurati che sia dichiarato globalmente
record_button = None # CORREZIONE: Aggiunto qui
play_button = None
stop_button = None
emergency_stop_button = None  # Pulsante di emergenza
edit_button = None
delete_button = None
duplicate_button = None # Pulsante per duplicare macro
concat_button = None # Pulsante per concatenare macro
loop_var = None # Variabile per il checkbox del loop
loop_delay_entry = None # Riferimento al campo di input per il tempo di attesa del loop
max_repetitions_entry = None # Riferimento al campo di input per il numero massimo di ripetizioni
root = None # Riferimento alla finestra principale
macro_list_tree = None
console_text = None
status_bar = None
_game_client_rect_screen = None # Variabile per memorizzare il rettangolo della finestra di gioco

# Nuove variabili globali per gli indicatori
recording_indicator_button = None
playing_indicator_button = None
focus_monitor_indicator = None
macro_details_text = None  # Widget per i dettagli della macro

# Variabili per il timer di registrazione
recording_timer_label = None
execution_visualizer_events_list = None
execution_visualizer_canvas = None
execution_visualizer_canvas_image = None
execution_visualizer_status_label = None
execution_visualizer_reference_image_label = None
execution_visualizer_candidate_image_label = None
execution_visualizer_reference_caption_label = None
execution_visualizer_candidate_caption_label = None
live_click_reference_image_label = None
live_click_candidate_image_label = None
live_click_reference_caption_label = None
live_click_candidate_caption_label = None
CLICK_PREVIEW_MAX_SIZE = (220, 140)
execution_click_history = []
# Variabili per scheduled tasks
scheduled_tasks_list_tree = None
scheduled_task_buttons_frame = None
next_tasks_countdown_frame = None
next_tasks_countdown_text = None
countdown_update_job = None


def restore_saved_window_geometry(window, config_key, description):
    """Ripristina la geometria salvata per una finestra/dialog."""
    try:
        geometry = get_window_geometry(config_key)
        if geometry:
            geom = f"{geometry['width']}x{geometry['height']}+{geometry['x']}+{geometry['y']}"
            window.geometry(geom)
            logger.info("Ripristinata geometria %s: %s", description, geom)
    except Exception as exc:
        logger.warning("Nessuna geometria valida per %s: %s", description, exc)


def save_window_geometry_config(window, config_key, description):
    """Salva la geometria corrente di una finestra/dialog."""
    try:
        set_window_geometry(
            config_key,
            x=window.winfo_x(),
            y=window.winfo_y(),
            width=window.winfo_width(),
            height=window.winfo_height(),
        )
        logger.info("Salvata geometria %s", description)
    except Exception as exc:
        logger.error("Errore salvataggio geometria %s: %s", description, exc)


def schedule_on_ui(callback):
    """Esegue un callback sul thread UI se la finestra principale e' attiva."""
    if root and root.winfo_exists():
        root.after(0, callback)


def schedule_status_update(message, indicator="idle"):
    """Programma l'aggiornamento della status bar sul thread UI."""
    schedule_on_ui(lambda: update_status(message, indicator=indicator))


def schedule_macro_views_refresh():
    """Aggiorna pulsanti e dettagli macro sul thread UI."""
    schedule_on_ui(update_button_states)
    schedule_on_ui(update_macro_details)


def schedule_macro_list_refresh():
    """Aggiorna la lista macro e i relativi dettagli sul thread UI."""
    schedule_on_ui(refresh_macro_list)
    schedule_macro_views_refresh()


def schedule_operation_idle_cleanup(refresh_list=False):
    """Riporta la UI a idle dopo il completamento di un'operazione."""
    if refresh_list:
        schedule_on_ui(refresh_macro_list)
    schedule_status_update("Pronto", indicator="idle")
    schedule_macro_views_refresh()


def schedule_messagebox(kind, title, message, parent=None):
    """Mostra un messagebox sul thread UI."""
    messagebox_fn = getattr(messagebox, kind)
    schedule_on_ui(lambda: messagebox_fn(title, message, parent=parent))


def refresh_macro_ui_state():
    """Aggiorna lista e dettagli macro dopo modifiche ai dati."""
    refresh_macro_list()
    update_macro_details()


def schedule_recording_finish_cleanup(*, refresh_list=False, debug_message=None):
    """Esegue il cleanup comune a fine registrazione."""
    schedule_on_ui(stop_recording_timer)
    if not app_state.playing_flag:
        stop_focus_monitoring()
    schedule_operation_idle_cleanup(refresh_list=refresh_list)
    if debug_message:
        console_log(debug_message)


def handle_playback_target_wait_cancelled():
    """Gestisce l'annullamento dell'attesa della finestra target."""
    schedule_operation_idle_cleanup()
    console_log("🛑 Attesa della finestra target annullata prima dell'avvio del playback.")


def handle_playback_target_wait_failed(failed_target_exe):
    """Gestisce il timeout o fallimento nell'aggancio alla finestra target."""
    schedule_operation_idle_cleanup()
    console_log(
        f"❌ Finestra dell'applicazione '{failed_target_exe}' non trovata o non raggiungibile durante l'attesa.",
        level="ERROR",
    )
    schedule_messagebox(
        "showerror",
        "Errore Riproduzione",
        f"Impossibile trovare la finestra dell'applicazione '{failed_target_exe}' nei 15 secondi di timeout.\n\n"
        f"SOLUZIONI:\n"
        f"• Assicurati che '{failed_target_exe}' sia aperto e visibile\n"
        f"• Clicca sulla finestra '{failed_target_exe}' per portarla in primo piano\n"
        f"• Riprova la riproduzione",
        parent=root,
    )


def handle_playback_started():
    """Aggiorna la UI quando parte la riproduzione."""
    schedule_status_update("🟢 Riproduzione macro in corso...", indicator="playing")


def handle_playback_finished():
    """Ripristina la UI al termine della riproduzione."""
    schedule_operation_idle_cleanup()


def get_selected_macro_metadata(
    *,
    action_label,
    missing_selection_message,
    invalid_selection_message,
    missing_metadata_message,
    parent=None,
    log_missing_selection=None,
    log_invalid_selection=None,
    log_missing_metadata=None,
):
    """Restituisce `(macro_id, metadata)` per la macro selezionata o `None`."""
    selected_item = macro_list_tree.selection()
    if not selected_item:
        if log_missing_selection:
            console_log(log_missing_selection, level="WARNING")
        messagebox.showwarning(action_label, missing_selection_message, parent=parent)
        return None

    macro_id_str = selected_item[0]
    try:
        macro_id = int(macro_id_str)
    except ValueError:
        if log_invalid_selection:
            console_log(log_invalid_selection.format(macro_id_str=macro_id_str), level="ERROR")
        messagebox.showerror(f"Errore {action_label}", invalid_selection_message, parent=parent)
        return None

    macro_metadata = get_macro_metadata_by_id(macro_id)
    if not macro_metadata:
        if log_missing_metadata:
            console_log(log_missing_metadata.format(macro_id=macro_id), level="ERROR")
        messagebox.showerror(f"Errore {action_label}", missing_metadata_message.format(macro_id=macro_id), parent=parent)
        return None

    return macro_id, macro_metadata


def validate_new_macro_input(name, exe, duration_str, *, parent):
    """Valida i campi del dialog di nuova macro e restituisce la durata intera."""
    if not name:
        messagebox.showwarning("Input Errato", "Il nome della macro non può essere vuoto.", parent=parent)
        return None
    if not exe:
        messagebox.showwarning("Input Errato", "Il nome dell'eseguibile non può essere vuoto.", parent=parent)
        return None

    try:
        duration = int(duration_str)
        if duration <= 0:
            raise ValueError("La durata deve essere un numero intero positivo.")
    except ValueError:
        messagebox.showwarning("Input Errato", "La durata deve essere un numero intero valido per i secondi.", parent=parent)
        return None

    return duration


def create_recording_thread(*args):
    """Crea il thread daemon usato per la registrazione di una nuova macro."""
    return threading.Thread(target=record_macro_thread_target, args=args, daemon=True)


def handle_recording_started(macro_name):
    """Aggiorna la UI quando parte la registrazione."""
    schedule_status_update(f"🔴 Registrazione di '{macro_name}' in corso...", indicator="recording")


def handle_empty_recording():
    """Mostra il messaggio per una registrazione senza eventi."""
    schedule_messagebox(
        "showwarning",
        "Registrazione Macro",
        "Nessun evento registrato. Potrebbe indicare:\n• Registrazione troppo veloce\n• Mancanza di input utente\n• Problema con la finestra target",
        parent=root,
    )


def handle_recording_save_error(macro_name, exc):
    """Gestisce un errore di salvataggio a fine registrazione."""
    console_log(f"❌ Errore durante il salvataggio della macro '{macro_name}': {exc}", level="ERROR")
    schedule_messagebox("showerror", "Errore Salvataggio", f"Errore: {exc}", parent=root)


def handle_recording_cancelled(cancelled_exe):
    """Gestisce l'annullamento o fallimento della registrazione sul target."""
    schedule_messagebox(
        "showinfo",
        "Registrazione Macro",
        "Registrazione annullata o processo non trovato.\n\nAssicurati che:\n"
        + f"• '{cancelled_exe}' sia avviato\n"
        + "• La finestra target sia in primo piano\n"
        + "• Nessun altro software interferisca",
        parent=root,
    )


def handle_recording_unhandled_error(exc):
    """Gestisce un errore non previsto durante la registrazione."""
    console_log(f"❌ Errore durante la registrazione della macro: {exc}", level="ERROR")
    schedule_messagebox(
        "showerror",
        "Errore Registrazione",
        f"Si è verificato un errore durante la registrazione: {exc}",
        parent=root,
    )


def should_flush_playback_move(playback_ui_state, index, total):
    """Decide quando aggiornare la UI durante raffiche di mouse move."""
    now_monotonic = time.monotonic()
    should_flush = (
        playback_ui_state["move_events_since_flush"] >= 12
        or (now_monotonic - playback_ui_state["last_move_ui_update"]) >= 0.08
        or index + 1 == total
    )
    if should_flush:
        playback_ui_state["last_move_ui_update"] = now_monotonic
        playback_ui_state["move_events_since_flush"] = 0
    return should_flush


def build_execution_visualizer_event_text(action_type, button_or_key, x, y, delta, timestamp):
    """Restituisce il testo leggibile da mostrare nel visualizer eventi."""
    time_str = f"{timestamp}ms"
    if action_type == "key_press":
        return f"[{time_str}] ⌨️ Premuto tasto: {button_or_key}"
    if action_type == "key_release":
        return f"[{time_str}] ⌨️ Rilasciato tasto: {button_or_key}"
    if action_type == "mouse_move":
        return f"[{time_str}] 🖱️ Spostamento mouse: ({x}, {y})"
    if action_type == "mouse_down":
        button_name = button_or_key or "sconosciuto"
        return f"[{time_str}] 🖱️ Click DOWN {button_name} in ({x}, {y})"
    if action_type == "mouse_up":
        button_name = button_or_key or "sconosciuto"
        return f"[{time_str}] 🖱️ Click UP {button_name} in ({x}, {y})"
    if action_type == "mouse_scroll":
        return f"[{time_str}] 🖱️ Scroll: {delta} in ({x}, {y})"
    return f"[{time_str}] {action_type}"


def update_execution_visualizer(event, index, total, action_type, button_or_key=None, x=None, y=None, delta=None, visual_context=None):
    """Aggiorna il visualizer di esecuzione sul thread UI."""
    if execution_visualizer_status_label:
        execution_visualizer_status_label.config(text=f"Esecuzione: {index + 1}/{total}")

    if not execution_visualizer_events_list:
        return

    timestamp = event.get("time", 0)
    event_text = build_execution_visualizer_event_text(action_type, button_or_key, x, y, delta, timestamp)

    if action_type == "mouse_down":
        if execution_visualizer_canvas and x is not None and y is not None:
            draw_mouse_position(execution_visualizer_canvas, x, y, button_or_key or "sconosciuto")
        if visual_context:
            update_execution_visualizer_context_preview(visual_context)

    execution_visualizer_events_list.insert(tk.END, event_text)
    execution_visualizer_events_list.see(tk.END)


def reset_execution_visualizer():
    """Pulisce il visualizer prima di una nuova riproduzione."""
    global execution_click_history
    execution_click_history = []
    if execution_visualizer_events_list:
        root.after(0, lambda: execution_visualizer_events_list.delete(0, tk.END))
    if execution_visualizer_canvas:
        root.after(0, lambda: execution_visualizer_canvas.delete("all"))
    if execution_visualizer_status_label:
        root.after(0, lambda: execution_visualizer_status_label.config(text="Pronto all'esecuzione..."))
    if execution_visualizer_reference_image_label:
        root.after(0, clear_execution_visualizer_context_preview)


def redraw_execution_click_history():
    """Ridisegna la traccia dei click in base alla dimensione corrente del canvas."""
    if execution_visualizer_canvas is None or not execution_click_history:
        return
    _draw_execution_click_history(execution_visualizer_canvas, execution_click_history[-50:])


def update_execution_visualizer_context_preview(visual_context):
    """Mostra riferimento e ritaglio corrente del controllo visivo click."""
    reference_preview = visual_context.get("reference_preview")
    candidate_preview = visual_context.get("candidate_preview")
    score = visual_context.get("score")
    threshold = visual_context.get("threshold")

    preview_targets = [
        (
            execution_visualizer_reference_image_label,
            execution_visualizer_reference_caption_label,
            execution_visualizer_candidate_image_label,
            execution_visualizer_candidate_caption_label,
        ),
        (
            live_click_reference_image_label,
            live_click_reference_caption_label,
            live_click_candidate_image_label,
            live_click_candidate_caption_label,
        ),
    ]

    for reference_label, reference_caption, candidate_label, candidate_caption in preview_targets:
        if reference_preview and reference_label:
            render_preview_image(reference_preview, reference_label, max_size=CLICK_PREVIEW_MAX_SIZE)
            if reference_caption:
                reference_caption.config(text="Primo riferimento click")

        if candidate_preview and candidate_label:
            render_preview_image(candidate_preview, candidate_label, max_size=CLICK_PREVIEW_MAX_SIZE)
            if candidate_caption:
                if score is not None and threshold is not None:
                    candidate_caption.config(
                        text=f"Controllo corrente · compatibilità {score:.2f}/{threshold:.2f}"
                    )
                else:
                    candidate_caption.config(text="Controllo corrente")


def clear_execution_visualizer_context_preview():
    """Pulisce i due riquadri di anteprima del controllo visivo."""
    for image_label, caption_label, caption_text in (
        (execution_visualizer_reference_image_label, execution_visualizer_reference_caption_label, "Primo riferimento click"),
        (execution_visualizer_candidate_image_label, execution_visualizer_candidate_caption_label, "Controllo corrente"),
        (live_click_reference_image_label, live_click_reference_caption_label, "Primo riferimento click"),
        (live_click_candidate_image_label, live_click_candidate_caption_label, "Controllo corrente"),
    ):
        if image_label:
            image_label.configure(image="", text="Anteprima non disponibile")
            image_label.image = None
        if caption_label:
            caption_label.config(text=caption_text)


def setup_click_context_preview(parent):
    """Crea il riquadro compatto con riferimento e ritaglio corrente."""
    global live_click_reference_image_label, live_click_candidate_image_label
    global live_click_reference_caption_label, live_click_candidate_caption_label

    preview_hint = ttk.Label(
        parent,
        text="Alla prima esecuzione vedrai qui il riferimento del primo click e il ritaglio corrente prima dei click successivi.",
        foreground=config['theme']['text_color'],
        font=(config['theme']['font_family'], config['theme']['font_size_small']),
        wraplength=320,
        justify="left",
    )
    preview_hint.pack(fill="x", pady=(0, 8))

    previews_frame = ttk.Frame(parent)
    previews_frame.pack(fill="both", expand=True)
    previews_frame.columnconfigure(0, weight=1)
    previews_frame.columnconfigure(1, weight=1)
    previews_frame.rowconfigure(0, weight=1)

    reference_frame = ttk.LabelFrame(previews_frame, text="Primo Click", padding="6")
    reference_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    reference_frame.columnconfigure(0, weight=1)
    reference_frame.rowconfigure(1, weight=1)
    live_click_reference_caption_label = ttk.Label(
        reference_frame,
        text="Primo riferimento click",
        foreground=config['theme']['text_color'],
        font=(config['theme']['font_family'], config['theme']['font_size_small']),
    )
    live_click_reference_caption_label.grid(row=0, column=0, sticky="ew", pady=(0, 4))
    reference_preview_holder = tk.Frame(
        reference_frame,
        background=config['theme']['border_color'],
        highlightthickness=1,
        highlightbackground=config['theme']['text_color'],
        width=220,
        height=140,
    )
    reference_preview_holder.grid(row=1, column=0, sticky="nsew")
    reference_preview_holder.grid_propagate(False)
    live_click_reference_image_label = tk.Label(
        reference_preview_holder,
        text="Anteprima non disponibile",
        background=config['theme']['border_color'],
        anchor="center",
        fg=config['theme']['text_color'],
    )
    live_click_reference_image_label.pack(fill="both", expand=True)

    candidate_frame = ttk.LabelFrame(previews_frame, text="Prima Del Click", padding="6")
    candidate_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
    candidate_frame.columnconfigure(0, weight=1)
    candidate_frame.rowconfigure(1, weight=1)
    live_click_candidate_caption_label = ttk.Label(
        candidate_frame,
        text="Controllo corrente",
        foreground=config['theme']['text_color'],
        font=(config['theme']['font_family'], config['theme']['font_size_small']),
    )
    live_click_candidate_caption_label.grid(row=0, column=0, sticky="ew", pady=(0, 4))
    candidate_preview_holder = tk.Frame(
        candidate_frame,
        background=config['theme']['border_color'],
        highlightthickness=1,
        highlightbackground=config['theme']['text_color'],
        width=220,
        height=140,
    )
    candidate_preview_holder.grid(row=1, column=0, sticky="nsew")
    candidate_preview_holder.grid_propagate(False)
    live_click_candidate_image_label = tk.Label(
        candidate_preview_holder,
        text="Anteprima non disponibile",
        background=config['theme']['border_color'],
        anchor="center",
        fg=config['theme']['text_color'],
    )
    live_click_candidate_image_label.pack(fill="both", expand=True)

    clear_execution_visualizer_context_preview()


def cleanup_input_hooks(gui_active):
    """Pulisce gli hook globali di tastiera e mouse."""
    try:
        keyboard.unhook_all()
        mouse.unhook_all()
        if gui_active:
            console_log("🧹 Hook di tastiera e mouse puliti.")
    except Exception as exc:
        if gui_active:
            console_log(f"⚠️ Errore durante la pulizia degli hook: {exc}", level="WARNING")


def finalize_stop_operation(gui_active):
    """Ripristina la UI dopo uno stop e pulisce gli hook residui."""
    if gui_active:
        update_status("Pronto", indicator="idle")
        update_button_states()
        update_macro_details()
    cleanup_input_hooks(gui_active)
    if gui_active:
        console_log("✅ Operazioni fermate con successo.")


def stop_active_recording(gui_active):
    """Ferma una registrazione attiva e ripulisce lo stato associato."""
    if gui_active:
        console_log("🛑 Fermando la registrazione...")
        stop_recording_timer()

    if stop_recording(console_log):
        if gui_active:
            console_log("✅ Registrazione fermata con successo.")
    elif gui_active:
        console_log("⚠️ Nessuna registrazione attiva da fermare.")

    state_service.stop_recording()


def stop_active_playback(gui_active):
    """Ferma una riproduzione attiva e segnala eventuali thread coinvolti."""
    if gui_active:
        console_log("🛑 Fermando la riproduzione...")
    request_playback_stop(console_log)

    if hasattr(threading, "_active"):
        for thread in threading._active.values():
            if thread.is_alive() and hasattr(thread, "_name") and "playback" in thread._name:
                if gui_active:
                    console_log(f"🔄 Terminando thread di riproduzione: {thread._name}")

    if gui_active:
        console_log("✅ Segnalato alla riproduzione di fermarsi.")
    reset_playback_state()


def log_force_stop_candidate_threads():
    """Segnala i thread operativi che lo stop emergenza sta tentando di fermare."""
    if not hasattr(threading, "_active"):
        return

    for thread_id, thread in threading._active.items():
        if not thread.is_alive() or thread == threading.current_thread():
            continue
        try:
            if hasattr(thread, "_name") and any(keyword in thread._name.lower() for keyword in ["record", "playback", "macro"]):
                console_log(f"🔄 Terminando forzatamente thread: {thread._name}")
        except Exception as exc:
            console_log(f"⚠️ Errore durante la gestione del thread {thread_id}: {exc}", level="ERROR")


def emergency_cleanup():
    """Esegue il cleanup forzato usato dallo stop emergenza."""
    try:
        keyboard.unhook_all()
        mouse.unhook_all()
        console_log("🔌 Tutti gli hook di tastiera e mouse sganciati forzatamente.")
    except Exception as exc:
        console_log(f"⚠️ Errore durante la pulizia forzata degli hook: {exc}", level="ERROR")

    log_force_stop_candidate_threads()
    stop_focus_monitoring()
    update_status("🚨 STOP EMERGENZA - Operazioni fermate", indicator="idle")
    update_button_states()
    update_macro_details()


def initialize_runtime_components():
    """Inizializza tabelle, scheduler e stato UI iniziale."""
    logger.info("Inizializzazione database e GUI")
    setup_main_table()
    setup_scheduled_tasks_table()
    setup_task_macro_sequence_table()
    setup_game_elements_table()
    setup_ui_graph_macro_links_table()
    remember_local_workstation_context()
    ensure_launch_game_system_macro()
    refresh_macro_list()
    task_controller.start_scheduler(log_callback=console_log, root_callback=lambda: root and root.winfo_exists())
    update_status("Pronto", indicator="idle")
    update_button_states()
    update_macro_details()


def log_startup_messages():
    """Scrive i messaggi informativi iniziali in console."""
    console_log("🚀 Macro Manager avviato con funzionalità avanzate di controllo!")
    console_log("🔍 Monitoraggio intelligente del focus della finestra attivo")
    console_log("✅ Le macro continuano a funzionare quando la finestra target è attiva")
    console_log("⚠️ Le operazioni si interrompono solo se la finestra target non è più attiva")
    console_log("⚡ Funzione di stop migliorata per maggiore responsività")
    console_log("■ Pulsante Stop disponibile accanto a Play")
    console_log("⌨️ Scorciatoie: ESC / Ctrl+Alt+S / Ctrl+Alt+E = Stop Emergenza")
    console_log("ℹ️ Il sistema distingue tra 'perdita di focus' e 'focus su finestra target'")
    console_log("📅 Scheduled Tasks ora disponibili - puoi programmare l'esecuzione delle macro!")
    console_log("🔄 Background Scheduler attivo - I task verranno eseguiti automaticamente!")


def is_target_window_active():
    """Verifica se la finestra target è attualmente attiva"""
    if not app_state.current_target_exe:
        return False
    
    try:
        import win32gui
        import win32process
        import psutil
        
        # Ottieni la finestra attualmente attiva
        active_window = win32gui.GetForegroundWindow()
        if active_window:
            # Controlla se è la finestra target
            _, pid = win32process.GetWindowThreadProcessId(active_window)
            proc = psutil.Process(pid)
            return proc.name().lower() == app_state.current_target_exe.lower()
    except Exception as e:
        console_log(f"Errore nel controllo della finestra target: {e}", level="ERROR")
    
    return False

def reset_playback_state():
    """Riporta lo stato della riproduzione a idle in un unico punto."""
    state_service.reset_playback()


def load_config():
    global config
    logger.info("Caricamento configurazione")
    config = load_app_config()
    logger.info("Configurazione caricata con successo")
    load_style(config.get("selected_style", "default"))

def load_style(style_name):
    """Carica uno stile da file di configurazione specifico"""
    global config
    try:
        style_config = load_style_config(style_name)
        config["theme"] = dict(DEFAULT_APP_CONFIG["theme"])
        config["theme"].update(style_config)
        config["selected_style"] = style_name
        logger.info(f"Stile '{style_name}' caricato con successo")
    except Exception as e:
        logger.error(f"Errore nel caricamento dello stile '{style_name}': {e}")

def save_style_selection(style_name):
    """Salva la selezione dello stile nel config principale"""
    global config
    try:
        cfg = load_app_config()
        cfg["selected_style"] = style_name
        save_app_config(cfg)
        logger.info(f"Stile '{style_name}' salvato nelle configurazioni")
    except Exception as e:
        logger.error(f"Errore nel salvataggio dello stile: {e}")

def apply_dialog_styles(dialog):
    """Applica gli stili della configurazione al dialog"""
    dialog.configure(bg=config['theme']['background_color'])
    
    # Applica stili TTK
    dlg_style = ttk.Style()
    
    # Configura i colori per tutti i widget del dialog
    dlg_style.configure('.', 
                       background=config['theme']['background_color'], 
                       foreground=config['theme']['text_color'])
    dlg_style.configure('TFrame', background=config['theme']['background_color'])
    dlg_style.configure('TLabel', 
                       background=config['theme']['background_color'], 
                       foreground=config['theme']['text_color'],
                       font=(config['theme']['font_family'], config['theme']['font_size_medium']))
    dlg_style.configure('TButton', 
                       background=config['theme']['button_bg_color'],
                       foreground=config['theme']['button_fg_color'],
                       font=(config['theme']['font_family'], config['theme']['font_size_medium'], 'bold'))
    dlg_style.configure('TEntry', 
                       fieldbackground=config['theme']['border_color'], 
                       foreground=config['theme']['text_color'],
                       borderwidth=1, 
                       relief="solid")
    dlg_style.configure('TCheckbutton', 
                       background=config['theme']['background_color'], 
                       foreground=config['theme']['text_color'])
    dlg_style.configure('TRadiobutton', 
                       background=config['theme']['background_color'], 
                       foreground=config['theme']['text_color'])
    dlg_style.configure('TLabelFrame', 
                       background=config['theme']['background_color'], 
                       foreground=config['theme']['text_color'],
                       relief="solid", 
                       borderwidth=1)
    dlg_style.configure('TCombobox', 
                       fieldbackground=config['theme']['border_color'], 
                       foreground=config['theme']['text_color'],
                       background=config['theme']['border_color'],
                       borderwidth=1, 
                       relief="solid")
    # Assicura che il testo rimanga leggibile anche quando perde il focus
    dlg_style.map('TCombobox',
                 fieldbackground=[('readonly', config['theme']['border_color']), ('!readonly', config['theme']['border_color'])],
                 foreground=[('readonly', config['theme']['text_color']), ('!readonly', config['theme']['text_color'])],
                 background=[('readonly', config['theme']['border_color']), ('!readonly', config['theme']['border_color'])])

def apply_window_styles(root_window):
    """Applica gli stili al window specificato"""
    root_window.configure(bg=config['theme']['background_color'])

def apply_dynamic_styles():
    """Aggiorna dinamicamente tutti gli stili dei widget esistenti"""
    global root, macro_list_tree, status_bar, macro_details_text, console_text
    
    # Aggiorna i colori del root window
    if root and root.winfo_exists():
        root.configure(bg=config['theme']['background_color'])
    
    # Aggiorna stile TTK Style - Applica a tutti i widget TTK
    try:
        style = ttk.Style()
        
        # Applica colori base a tutti i widget TTK
        style.configure('.', 
                       background=config['theme']['background_color'], 
                       foreground=config['theme']['text_color'])
        style.configure('TFrame', background=config['theme']['background_color'])
        style.configure('TLabel', 
                       background=config['theme']['background_color'], 
                       foreground=config['theme']['text_color'])
        style.configure('TButton', 
                       background=config['theme']['button_bg_color'],
                       foreground=config['theme']['button_fg_color'])
        style.configure('Treeview', 
                       background=config['theme']['border_color'], 
                       foreground=config['theme']['text_color'],
                       fieldbackground=config['theme']['border_color'])
        style.map('Treeview', background=[('selected', config['theme']['button_bg_color'])])
        style.configure('Treeview.Heading', 
                       background=config['theme']['button_bg_color'], 
                       foreground=config['theme']['button_fg_color'])
        style.configure('TEntry', 
                       fieldbackground=config['theme']['border_color'], 
                       foreground=config['theme']['text_color'])
        style.configure('TCombobox', 
                       fieldbackground=config['theme']['border_color'], 
                       foreground=config['theme']['text_color'],
                       background=config['theme']['border_color'],
                       borderwidth=1, 
                       relief="solid")
        # Assicura che il testo rimanga leggibile anche quando perde il focus
        style.map('TCombobox',
                 fieldbackground=[('readonly', config['theme']['border_color']), ('!readonly', config['theme']['border_color'])],
                 foreground=[('readonly', config['theme']['text_color']), ('!readonly', config['theme']['text_color'])],
                 background=[('readonly', config['theme']['border_color']), ('!readonly', config['theme']['border_color'])])
        style.configure('TScrolledText', 
                       background=config['theme']['border_color'], 
                       foreground=config['theme']['text_color'])
        style.configure('TCheckbutton', 
                       background=config['theme']['background_color'], 
                       foreground=config['theme']['text_color'])
        style.configure('TRadiobutton', 
                       background=config['theme']['background_color'], 
                       foreground=config['theme']['text_color'])
        style.configure('TLabelFrame', 
                       background=config['theme']['background_color'], 
                       foreground=config['theme']['text_color'])
        style.configure('TNotebook.Tab', 
                       foreground='black')
        style.configure('TNotebook', 
                       background=config['theme']['background_color'])
        style.configure('TScrollbar', 
                       background=config['theme']['border_color'])
    except Exception as e:
        console_log(f"⚠️ Errore nell'aggiornamento dello stile TTK: {e}", level="WARNING")
    
    # Aggiorna i widget di testo specifici che usano i colori hardcoded
    try:
        # ScrolledText per dettagli macro
        if macro_details_text and macro_details_text.winfo_exists():
            macro_details_text.configure(
                bg=config['theme']['border_color'], 
                fg=config['theme']['text_color'],
                insertbackground=config['theme']['text_color']
            )
        
        # Console log text
        if console_text and console_text.winfo_exists():
            console_text.configure(
                bg=config['theme']['border_color'], 
                fg=config['theme']['text_color'],
                insertbackground=config['theme']['text_color']
            )
    except Exception as e:
        console_log(f"⚠️ Errore nell'aggiornamento dei widget di testo: {e}", level="WARNING")
    
    # Aggiorna status bar
    try:
        if status_bar and status_bar.winfo_exists():
            current_status = status_bar.cget('text')
            status_bar.config(
                bg=config['theme']['status_idle_color'], 
                fg=config['theme']['text_color']
            )
            status_bar.config(text=current_status)  # Mantieni il testo ma con nuovi colori
    except Exception as e:
        pass
    
    # Forzare il refresh di tutti i frame con background per forzare le riparazioni visive
    try:
        # Riavvia il refresh di tutti i widget basati sui colori di base
        root.update_idletasks()
    except Exception as e:
        pass
    
    # Ripassa gli aggiornamenti dello status per applicare i nuovi colori
    try:
        update_status()
    except Exception as e:
        pass

def setup_settings_tab(parent):
    """Configura l'interfaccia del tab Settings"""
    main_frame = ttk.Frame(parent)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Frame principale
    settings_frame = ttk.LabelFrame(main_frame, text="Impostazioni Stile", padding="20")
    settings_frame.pack(fill="x", pady=10)
    
    # Titolo
    title_label = ttk.Label(settings_frame, text="🎨 Seleziona Stile di Visualizzazione", 
                           font=(config['theme']['font_family'], config['theme']['font_size_large'], "bold"))
    title_label.pack(pady=10)
    
    # Variabile per il radio button selezionato
    selected_style_var = tk.StringVar(value=config.get('selected_style', 'default'))
    
    # Stili disponibili
    styles = [
        ("default", "🖥️ Default (Scuro)", "Stile scuro predefinito dell'applicazione"),
        ("light", "☀️ Light (Chiaro)", "Tema chiaro e minimalista"),
        ("dark_blue", "🌙 Dark Blue", "Tema blu scuro moderno"),
        ("neon", "⚡ Neon", "Tema neon cyberpunk")
    ]
    
    # Radio buttons per la selezione
    for style_id, description, detailed_desc in styles:
        style_frame = ttk.Frame(settings_frame)
        style_frame.pack(fill="x", pady=5)
        
        rb = ttk.Radiobutton(style_frame, text=description, 
                           variable=selected_style_var, value=style_id,
                           command=lambda style=style_id: on_style_selected(style))
        rb.pack(side="left")
        
        desc_label = ttk.Label(style_frame, text=f"  - {detailed_desc}",
                              foreground=config['theme']['status_idle_color'])
        desc_label.pack(side="left")
    
    # Info sezione
    info_frame = ttk.LabelFrame(main_frame, text="ℹ️ Informazioni", padding="15")
    info_frame.pack(fill="x", pady=10)
    
    info_text = """📋 Importante:
• Gli stili vengono applicati immediatamente quando selezionati
• La posizione e dimensioni della finestra vengono salvate automaticamente
• Lo stile selezionato viene salvato e verrà ripristinato al prossimo avvio
• Non è necessario riavviare l'applicazione per vedere i cambiamenti"""

    info_label = ttk.Label(info_frame, text=info_text, 
                          foreground=config['theme']['text_color'],
                          font=(config['theme']['font_family'], config['theme']['font_size_small']))
    info_label.pack(anchor="w")

def on_style_selected(style_name):
    """Gestisce la selezione di un nuovo stile"""
    try:
        save_style_selection(style_name)
        # Carica e applica immediatamente lo stile
        load_style(style_name)
        apply_dynamic_styles()
        console_log(f"✅ Stile '{style_name}' applicato immediatamente")
    except Exception as e:
        console_log(f"❌ Errore nel salvataggio dello stile '{style_name}': {e}", level="ERROR")
        messagebox.showerror("Errore Stile", f"Errore nel salvataggio dello stile: {e}", parent=root)

def append_playback_debug_log(message, level):
    """Scrive un messaggio operativo direttamente nel file di debug, se attivo."""
    if not playback_debug_log_path:
        return
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    try:
        with playback_debug_log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"{timestamp} - __main__ - {level} - {message}\n")
    except Exception:
        pass


def console_log(message, level="INFO", mirror_to_file=True):
    """Funzione per stampare messaggi nella console testuale della GUI."""
    normalized_level = normalize_log_level(level)
    if not should_emit_log_level(normalized_level):
        return
    if mirror_to_file:
        append_playback_debug_log(message, normalized_level)
    append_console_message(console_text, message, level=normalized_level, fallback_print=print)

# Aggiorna update_status per supportare nuovi indicatori

def update_status(message="Pronto", indicator="idle"):
    """Aggiorna la barra di stato e gli indicatori visivi."""
    try:
        if (status_bar and recording_indicator_button and playing_indicator_button and 
            status_bar.winfo_exists() and recording_indicator_button.winfo_exists() and 
            playing_indicator_button.winfo_exists()): # Assicurati che i widget esistano e siano validi
            apply_status_indicator_state(
                status_bar=status_bar,
                recording_indicator_button=recording_indicator_button,
                playing_indicator_button=playing_indicator_button,
                focus_monitor_indicator=focus_monitor_indicator,
                message=message,
                indicator=indicator,
                theme=config["theme"],
                focus_monitor_active=app_state.focus_monitor_active,
                recording_timer_active=app_state.recording_timer_active,
                recording_duration=app_state.recording_duration,
                start_recording_timer=start_recording_timer,
            )
    except tk.TclError:
        # Widget è stato distrutto, ignora l'aggiornamento
        pass
    except Exception as e:
        # Altri errori, stampa su console
        print(f"Errore durante l'aggiornamento dello stato: {e}")
    
    # Aggiorna i pulsanti solo se la GUI è ancora attiva
    if root and root.winfo_exists():
        update_button_states()
        update_macro_details()

def start_recording_timer(duration_sec):
    """Avvia il timer di countdown per la registrazione."""
    if duration_sec <= 0:
        return

    state_service.start_recording_timer(duration_sec)
    
    # Mostra il widget del timer
    if recording_timer_label:
        recording_timer_label.pack(side="left", padx=(10, 5))
    
    # Avvia l'aggiornamento del timer
    update_recording_timer()

def update_recording_timer():
    """Aggiorna il display del timer ogni secondo."""
    if not app_state.recording_timer_active or not app_state.recording_start_time:
        return
    
    if not root or not root.winfo_exists():
        return
    
    try:
        elapsed = time.time() - app_state.recording_start_time
        remaining = max(0, app_state.recording_duration - elapsed)
        
        if remaining <= 0:
            # Timer scaduto
            stop_recording_timer()
            return
        
        # Formatta il tempo rimanente come MM:SS
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        time_str = f"{minutes:02d}:{seconds:02d}"
        
        # Aggiorna il label del timer
        if recording_timer_label and recording_timer_label.winfo_exists():
            recording_timer_label.config(text=f"⏱️ {time_str}")
            
            # Cambia colore quando il tempo è basso (ultimi 10 secondi)
            if remaining <= 10:
                recording_timer_label.config(foreground="red", font=("Segoe UI", 16, "bold"))
            elif remaining <= 30:
                recording_timer_label.config(foreground="orange", font=("Segoe UI", 16, "bold"))
            else:
                recording_timer_label.config(foreground="white", font=("Segoe UI", 16, "bold"))
        
        # Programma il prossimo aggiornamento
        state_service.set_recording_timer_job(root.after(1000, update_recording_timer))
    except tk.TclError:
        # Widget distrutto, ferma il timer
        stop_recording_timer()
    except Exception as e:
        print(f"Errore durante l'aggiornamento del timer: {e}")
        stop_recording_timer()

def stop_recording_timer():
    """Ferma il timer di registrazione e nasconde il widget."""
    # Cancella il job di aggiornamento se esiste
    if app_state.recording_timer_job and root and root.winfo_exists():
        try:
            root.after_cancel(app_state.recording_timer_job)
        except:
            pass
    state_service.stop_recording_timer()
    
    # Nascondi il widget del timer
    if recording_timer_label and recording_timer_label.winfo_exists():
        try:
            recording_timer_label.pack_forget()
        except:
            pass

def refresh_macro_list():
    """Aggiorna la Treeview con le macro dal database."""
    logger.info("Refresh lista macro")
    try:
        if macro_list_tree and macro_list_tree.winfo_exists(): # Assicurati che macro_list_tree esista e sia valido
            for iid in macro_list_tree.get_children():
                macro_list_tree.delete(iid)
            macros = get_all_macros()
            logger.info(f"Trovate {len(macros)} macro nel database")
            for macro in macros:
                # Usa l'ID della macro come iid della Treeview
                macro_list_tree.insert("", "end", iid=macro['id'],
                                       values=(macro['nome'], macro['durata_sec'],
                                               macro['eseguibile'], macro['data_creazione']))
    except tk.TclError:
        # Widget è stato distrutto, ignora l'aggiornamento
        pass
    except Exception as e:
        # Altri errori, stampa su console
        print(f"Errore durante il refresh della lista macro: {e}")
    
    # Aggiorna lo stato dei pulsanti solo se la GUI è ancora attiva
    if root and root.winfo_exists():
        update_button_states()
        update_macro_details()

def update_macro_details():
    """Aggiorna i dettagli della macro selezionata nel pannello destro."""
    try:
        if not macro_details_text or not macro_details_text.winfo_exists():
            return
            
        selected_item = macro_list_tree.selection()
        if not selected_item:
            # Nessuna macro selezionata, mostra messaggio informativo
            macro_details_text.config(state=tk.NORMAL)
            macro_details_text.delete(1.0, tk.END)
            macro_details_text.insert(tk.END, "Seleziona una macro dalla lista per visualizzare i dettagli.")
            macro_details_text.config(state=tk.DISABLED)
            return
            
        macro_id_str = selected_item[0]
        try:
            macro_id = int(macro_id_str)
        except ValueError:
            macro_details_text.config(state=tk.NORMAL)
            macro_details_text.delete(1.0, tk.END)
            macro_details_text.insert(tk.END, "Errore: ID macro non valido.")
            macro_details_text.config(state=tk.DISABLED)
            return
            
        # Ottieni i metadati della macro
        macro_metadata = get_macro_metadata_by_id(macro_id)
        if not macro_metadata:
            macro_details_text.config(state=tk.NORMAL)
            macro_details_text.delete(1.0, tk.END)
            macro_details_text.insert(tk.END, "Errore: Metadati macro non trovati.")
            macro_details_text.config(state=tk.DISABLED)
            return
            
        # Prepara il testo dei dettagli (solo metadati, senza eventi)
        details = f"""DETTAGLI MACRO: {macro_metadata['nome']}
{'='*50}

METADATI:
• ID: {macro_metadata['id']}
• Nome: {macro_metadata['nome']}
• Descrizione: {macro_metadata.get('descrizione', 'N/A')}
• Durata: {macro_metadata['durata_sec']} secondi
• Eseguibile: {macro_metadata['eseguibile']}
• Tipo: {"Macro di sistema" if macro_metadata.get('macro_kind') == 'system' else "Macro standard"}
• Protetta: {"Sì" if macro_metadata.get('is_protected') else "No"}
• Data Creazione: {macro_metadata['data_creazione']}

SINTESI:
• Gli eventi della macro non vengono mostrati nella sintesi per migliorare la leggibilità.
• Per visualizzare i dettagli degli eventi utilizza il pulsante '✏️ Modifica' per aprire l'editor.
"""
        if macro_metadata.get("macro_kind") == "system":
            payload = macro_metadata.get("system_payload") or {}
            local_context = ""
            if payload.get("variant_scope") == "local_workstation":
                local_context = f"{payload.get('host_name') or '-'}\\{payload.get('user_name') or '-'}"
            details += f"""

MACRO DI SISTEMA:
• Chiave: {macro_metadata.get('system_key') or '-'}
• Collegamento di avvio: {payload.get('shortcut_path') or '-'}
• Obiettivo: {payload.get('objective') or 'Arrivare al gioco pronto.'}
• Comportamento iniziale: avvia il gioco se non è già attivo e attende il fullscreen.
• Polling popup iniziali: ogni {payload.get('initial_popup_poll_interval_sec') or 10}s sull'intera finestra.
• Step successivi previsti: caricamento completo, rilevamento/chiusura popup iniziali bloccanti, accesso al gioco.
• Variante locale: {local_context or 'No'}
"""
            
        # Mostra i dettagli
        macro_details_text.config(state=tk.NORMAL)
        macro_details_text.delete(1.0, tk.END)
        macro_details_text.insert(tk.END, details)
        macro_details_text.config(state=tk.DISABLED)
        
    except Exception as e:
        if macro_details_text and macro_details_text.winfo_exists():
            macro_details_text.config(state=tk.NORMAL)
            macro_details_text.delete(1.0, tk.END)
            macro_details_text.insert(tk.END, f"Errore nel caricamento dei dettagli: {e}")
            macro_details_text.config(state=tk.DISABLED)
        console_log(f"Errore nell'aggiornamento dettagli macro: {e}", level="ERROR")


def update_button_states():
    """Abilita/disabilita i pulsanti in base alla selezione e allo stato delle operazioni."""
    try:
        # Controlla che tutti i pulsanti e widget necessari siano stati inizializzati e siano ancora validi
        widgets = [new_macro_button, record_button, play_button, stop_button,
                  emergency_stop_button, edit_button, delete_button, duplicate_button,
                  loop_var_checkbox, loop_delay_entry, max_repetitions_entry, macro_list_tree]
        
        if not all(widgets) or not all(widget.winfo_exists() for widget in widgets if widget):
            return # Esce se non tutti i widget sono pronti o sono stati distrutti

        selected_item = macro_list_tree.selection()
        has_selection = bool(selected_item)
        selected_macro_metadata = None
        if has_selection:
            try:
                selected_macro_metadata = get_macro_metadata_by_id(int(selected_item[0]))
            except Exception:
                selected_macro_metadata = None

        def set_play_button_highlight(is_active):
            if is_active:
                play_button.config(style="ActivePlay.TButton")
            else:
                play_button.config(style="TButton")

        # Stato iniziale: disabilita tutto tranne "Nuova Macro"
        new_macro_button.config(state=tk.NORMAL)
        stop_button.config(state=tk.DISABLED)
        emergency_stop_button.config(state=tk.DISABLED)
        set_play_button_highlight(False)
        
        # Abilita/Disabilita basandosi su flags globali (riproduzione/registrazione)
        if app_state.recording_flag:
            new_macro_button.config(state=tk.DISABLED)
            record_button.config(state=tk.DISABLED)
            play_button.config(state=tk.DISABLED)
            emergency_stop_button.config(state=tk.NORMAL) # Abilita sempre il pulsante di emergenza
            edit_button.config(state=tk.DISABLED)
            delete_button.config(state=tk.DISABLED)
            duplicate_button.config(state=tk.DISABLED)
            concat_button.config(state=tk.DISABLED)
            loop_var_checkbox.config(state=tk.DISABLED)
            loop_delay_entry.config(state=tk.DISABLED)
        
        elif app_state.playing_flag:
            new_macro_button.config(state=tk.DISABLED)
            record_button.config(state=tk.DISABLED)
            play_button.config(state=tk.DISABLED)
            set_play_button_highlight(True)
            emergency_stop_button.config(state=tk.NORMAL) # Abilita sempre il pulsante di emergenza
            edit_button.config(state=tk.DISABLED)
            delete_button.config(state=tk.DISABLED)
            duplicate_button.config(state=tk.DISABLED)
            concat_button.config(state=tk.DISABLED)
            loop_var_checkbox.config(state=tk.DISABLED)
            loop_delay_entry.config(state=tk.DISABLED)
            
        else: # Nessuna registrazione o riproduzione in corso
            emergency_stop_button.config(state=tk.DISABLED)
            new_macro_button.config(state=tk.NORMAL)
            record_button.config(state=tk.DISABLED)
            # Il bottone concatena può essere sempre abilitato (non richiede selezione)
            concat_button.config(state=tk.NORMAL)

            if has_selection:
                play_button.config(state=tk.NORMAL)
                is_system_macro = bool(selected_macro_metadata and selected_macro_metadata.get("macro_kind") == "system")
                is_protected = bool(selected_macro_metadata and selected_macro_metadata.get("is_protected"))
                edit_button.config(state=tk.DISABLED if is_system_macro else tk.NORMAL)
                delete_button.config(state=tk.DISABLED if is_protected else tk.NORMAL)
                duplicate_button.config(state=tk.NORMAL) # Abilita anche duplicate
                loop_var_checkbox.config(state=tk.NORMAL)
                loop_delay_entry.config(state=tk.NORMAL if loop_var.get() else tk.DISABLED)
            else:
                play_button.config(state=tk.DISABLED)
                edit_button.config(state=tk.DISABLED)
                delete_button.config(state=tk.DISABLED)
                duplicate_button.config(state=tk.DISABLED)
                loop_var_checkbox.config(state=tk.DISABLED)
                loop_delay_entry.config(state=tk.DISABLED) # Disabilita sempre se non c'è selezione

        # Il pulsante di emergenza è sempre abilitato per sicurezza
        # (non è incluso nella lista dei controlli perché è aggiunto dinamicamente)
        # Questo garantisce che l'utente possa sempre fermare le operazioni in caso di problemi
        
    except tk.TclError:
        # Widget è stato distrutto, ignora l'aggiornamento
        pass
    except Exception as e:
        # Altri errori, stampa su console
        print(f"Errore durante l'aggiornamento dei pulsanti: {e}")

def get_loop_delay():
    try:
        delay = float(loop_delay_entry.get())
        if delay < 0:
            raise ValueError("Il ritardo del loop non può essere negativo.")
        save_loop_delay_preference(delay)
        return delay
    except ValueError:
        console_log("⚠️ Valore non valido per il ritardo del loop. Usando il default.", level="WARNING")
        return config['macro_manager']['loop_interval_sec_default']


def save_loop_delay_preference(delay):
    """Memorizza il ritardo loop scelto dall'utente."""
    try:
        delay_value = float(delay)
        if delay_value < 0:
            raise ValueError
    except (TypeError, ValueError):
        return

    config_data = load_app_config()
    macro_cfg = dict(config_data.get("macro_manager", {}))
    if macro_cfg.get("loop_interval_sec_default") == delay_value:
        return

    macro_cfg["loop_interval_sec_default"] = delay_value
    config_data["macro_manager"] = macro_cfg
    save_app_config(config_data)
    config["macro_manager"]["loop_interval_sec_default"] = delay_value


def persist_loop_delay_from_entry(event=None):
    """Salva il ritardo loop corrente se valido."""
    if loop_delay_entry is None or not loop_delay_entry.winfo_exists():
        return
    try:
        delay = float(loop_delay_entry.get())
        if delay < 0:
            raise ValueError
        save_loop_delay_preference(delay)
    except ValueError:
        return


def get_max_repetitions():
    try:
        max_rep = int(max_repetitions_entry.get())
        if max_rep < 0:
            raise ValueError("Il numero massimo di ripetizioni non può essere negativo.")
        return max_rep if max_rep > 0 else None  # 0 o None significa nessun limite
    except ValueError:
        console_log("⚠️ Valore non valido per il numero massimo di ripetizioni. Nessun limite impostato.", level="WARNING")
        return None  # Nessun limite se il valore non è valido


def check_window_focus():
    """Controlla se la finestra dell'applicazione ha ancora il focus"""
    try:
        # Controlla se la GUI è ancora attiva
        if not root or not root.winfo_exists():
            return True
        
        # Ottieni la finestra attualmente attiva
        active_window = win32gui.GetForegroundWindow()
        if active_window:
            # Controlla se è la nostra finestra
            current_focus, changed = focus_monitor_service.check_app_focus(
                active_window_id=active_window,
                app_window_id=root.winfo_id(),
            )
            if changed:
                if not current_focus:
                    # Se stiamo riproducendo una macro, verifica se la finestra target è attiva
                    if app_state.playing_flag and app_state.current_target_exe:
                        if is_target_window_active():
                            console_log(f"✅ Finestra target '{app_state.current_target_exe}' è attiva - Continuo la macro", level="INFO")
                        else:
                            console_log("⚠️ Finestra dell'applicazione ha perso il focus e la finestra target non è attiva - Interrompo la riproduzione", level="WARNING")
                            stop_current_operation()
                    # Se stiamo registrando, interrompi sempre se perdiamo il focus
                    elif app_state.recording_flag:
                        # Only stop if we're actually recording (not just in the waiting phase)
                        # Check if this is triggered during the wait_for_app_window phase by seeing if recording has had time to establish
                        # A simple way: check if we've been recording for more than 0.1 seconds (indicating start_time is set)
                        try:
                            import macro_controller
                            _start_time = getattr(macro_controller, '_start_time', None)
                            if _start_time is not None:
                                # We're actually recording, stop on focus loss
                                console_log("⚠️ Finestra dell'applicazione ha perso il focus durante la registrazione - Interrompo la registrazione", level="WARNING")
                                stop_current_operation()
                            else:
                                # We're in the waiting phase, don't stop
                                console_log("ℹ️ Finestra perso focus durante fase di attesa target window - Procedo con l'attesa", level="INFO")
                        except Exception as e:
                            # Fallback: don't stop on focus loss if we can't determine if we're really recording
                            console_log(f"Debug - Focus lost during recording check failed: {e}", level="INFO")
                    # Se non stiamo facendo nulla, è solo un cambio di focus normale
                    else:
                        console_log("ℹ️ Finestra dell'applicazione ha perso il focus", level="INFO")
            return current_focus
    except Exception as e:
        console_log(f"Errore nel controllo del focus: {e}", level="ERROR")
    return True


def start_focus_monitoring():
    """Avvia il monitoraggio del focus della finestra"""
    started = focus_monitor_service.start_monitoring(
        is_gui_available=lambda: bool(root and root.winfo_exists()),
        poll_focus=check_window_focus,
        on_error=lambda exc: console_log(f"Errore nel monitoraggio del focus: {exc}", level="ERROR"),
    )
    if not started:
        return
    console_log("🔍 Monitoraggio focus finestra avviato")
    
    # Aggiorna la GUI per mostrare l'indicatore solo se è ancora attiva
    if root and root.winfo_exists():
        root.after(0, lambda: update_status("Monitoraggio focus attivo", indicator="idle"))
        root.after(0, update_macro_details)


def stop_focus_monitoring():
    """Ferma il monitoraggio del focus della finestra"""
    stopped = focus_monitor_service.stop_monitoring()
    if not stopped:
        return
    console_log("🔍 Monitoraggio focus finestra fermato")
    
    # Aggiorna la GUI per nascondere l'indicatore solo se è ancora attiva
    schedule_status_update("Pronto", indicator="idle")
    schedule_on_ui(update_macro_details)


def on_window_focus_in():
    """Gestisce l'evento quando la finestra riacquista il focus"""
    if focus_monitor_service.mark_focus_in():
        console_log("✅ Finestra dell'applicazione ha riacquistato il focus")
        if root and root.winfo_exists():
            root.after(0, update_macro_details)


def on_window_focus_out():
    """Gestisce l'evento quando la finestra perde il focus"""
    if focus_monitor_service.mark_focus_out():
        # Se stiamo riproducendo una macro, verifica se la finestra target è attiva
        if app_state.playing_flag and app_state.current_target_exe:
            if is_target_window_active():
                console_log(f"✅ Finestra target '{app_state.current_target_exe}' è attiva - Continuo la macro", level="INFO")
            else:
                console_log("⚠️ Finestra dell'applicazione ha perso il focus e la finestra target non è attiva - Interrompo la riproduzione", level="WARNING")
                stop_current_operation()
        # Se stiamo registrando, interrompi sempre se perdiamo il focus
        elif app_state.recording_flag:
            console_log("⚠️ Finestra dell'applicazione ha perso il focus durante la registrazione - Interrompo la registrazione", level="WARNING")
            stop_current_operation()
        # Se non stiamo facendo nulla, è solo un cambio di focus normale
        else:
            console_log("ℹ️ Finestra dell'applicazione ha perso il focus", level="INFO")
        if root and root.winfo_exists():
            root.after(0, update_macro_details)


def on_window_destroy(event=None):
    """Gestisce l'evento di chiusura della finestra"""
    if event is not None and event.widget is not root:
        return
    try:
        stop_focus_monitoring()
        task_controller.stop_scheduler(log_callback=console_log if root and root.winfo_exists() else None)
        stop_current_operation()
        schedule_on_ui(update_macro_details)
    except Exception as e:
        # Se c'è un errore durante la chiusura, stampa solo su console
        print(f"Errore durante la chiusura della finestra: {e}")
    finally:
        cleanup_on_application_close()


def cleanup_on_application_close():
    """Chiude i log e pulisce artefatti runtime locali una sola volta."""
    global shutdown_cleanup_done, file_log_handler, playback_debug_log_path
    if shutdown_cleanup_done:
        return {"files_removed": 0, "dirs_removed": 0, "errors": 0}
    shutdown_cleanup_done = True
    close_logging_handlers()
    file_log_handler = None
    playback_debug_log_path = None
    return cleanup_runtime_artifacts()


def close_current_window_after_admin_relaunch():
    """Chiude in modo deciso l'istanza non elevata dopo il rilancio admin."""
    try:
        stop_focus_monitoring()
        task_controller.stop_scheduler(log_callback=console_log if root and root.winfo_exists() else None)
        stop_current_operation()
        if root and root.winfo_exists():
            save_window_geometry()
            root.after(0, root.quit)
            root.after(50, root.destroy)
    finally:
        cleanup_on_application_close()
        # Alcuni thread daemon possono tenere viva l'istanza non elevata:
        # forziamo l'uscita poco dopo il rilancio del nuovo processo.
        if root and root.winfo_exists():
            root.after(400, lambda: os._exit(0))
        else:
            os._exit(0)


# --- Funzioni di gestione Macro ---
def create_new_macro_dialog():
    dialog = tk.Toplevel(root)
    dialog.title(config['new_macro_dialog']['window_title'])
    dialog.transient(root) # Rendi la finestra di dialogo modale
    dialog.grab_set() # Blocca l'interazione con la finestra principale
    
    # Carica posizione/dimensione salvata per questa finestra
    restore_saved_window_geometry(dialog, "new_macro_dialog_window", "new macro dialog")
    
    # Salva posizione/dimensione alla chiusura
    def save_dialog_geometry():
        save_window_geometry_config(dialog, "new_macro_dialog_window", "new macro dialog")
    
    def on_dialog_close():
        save_dialog_geometry()
        dialog.destroy()
    
    dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)
    
    # Applica lo stesso stile della finestra principale al dialog
    apply_dialog_styles(dialog)

    # Variabili per i campi di input
    macro_name_var = tk.StringVar(dialog)
    macro_desc_var = tk.StringVar(dialog)
    macro_duration_var = tk.StringVar(dialog, value=str(config['new_macro_dialog']['default_duration_sec'])) # Default da config
    macro_exe_var = tk.StringVar(dialog, value=config['new_macro_dialog']['default_exe_name']) # Default da config

    ttk.Label(dialog, text="Nome Macro:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    name_entry = ttk.Entry(dialog, textvariable=macro_name_var, width=40)
    name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    name_entry.focus_set()

    ttk.Label(dialog, text="Descrizione:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
    desc_entry = ttk.Entry(dialog, textvariable=macro_desc_var, width=40)
    desc_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

    ttk.Label(dialog, text="Durata Registrazione (secondi):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
    duration_entry = ttk.Entry(dialog, textvariable=macro_duration_var, width=40)
    duration_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

    ttk.Label(dialog, text="Eseguibile Target (es. Doomsday.exe):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
    exe_entry = ttk.Entry(dialog, textvariable=macro_exe_var, width=40)
    exe_entry.grid(row=3, column=1, padx=5, pady=5, sticky="ew")

    def validate_and_start_recording():
        name = macro_name_var.get().strip()
        desc = macro_desc_var.get().strip()
        duration_str = macro_duration_var.get().strip()
        exe = macro_exe_var.get().strip()

        duration = validate_new_macro_input(name, exe, duration_str, parent=dialog)
        if duration is None:
            return

        dialog.destroy() # Chiudi il dialogo prima di iniziare la registrazione
        start_recording_for_new_macro(name, desc, duration, exe)

    ttk.Button(dialog, text="Avvia Registrazione", command=validate_and_start_recording, style='TButton').grid(row=4, column=0, columnspan=2, pady=10)

def start_recording_for_new_macro(macro_name, macro_desc, macro_duration, macro_exe):
    if app_state.recording_flag:
        messagebox.showwarning("Registrazione", "Una registrazione è già in corso.", parent=root)
        return

    if not recording_service.start_recording_session(target_exe=macro_exe, duration_sec=macro_duration):
        messagebox.showwarning("Registrazione", "Una registrazione è già in corso.", parent=root)
        return
    
    # Attendi che la finestra del gioco sia attiva prima di avviare la registrazione
    console_log(f"🕹️ In attesa che '{macro_exe}' sia in primo piano prima di avviare la registrazione...")
    update_status(f"🕹️ Attendendo '{macro_exe}' in primo piano...", indicator="waiting")
    
    # Avvia il monitoraggio del focus se non è già'attivo
    start_focus_monitoring()

    # Avvia la registrazione in un thread separato per non bloccare la GUI
    record_thread = create_recording_thread(macro_name, macro_desc, macro_duration, macro_exe)
    record_thread.start()

def record_macro_thread_target(macro_name, macro_desc, macro_duration, macro_exe):
    recording_service.run_new_macro_recording(
        macro_name=macro_name,
        macro_desc=macro_desc,
        macro_duration=macro_duration,
        macro_exe=macro_exe,
        registra_eventi=registra_eventi,
        save_macro=salva_macro_test,
        log_callback=console_log,
        on_recording_started=lambda: handle_recording_started(macro_name),
        on_empty_recording=handle_empty_recording,
        on_save_error=lambda exc: handle_recording_save_error(macro_name, exc),
        on_cancelled=handle_recording_cancelled,
        on_unhandled_error=handle_recording_unhandled_error,
        on_finished=lambda: schedule_recording_finish_cleanup(
            refresh_list=True,
            debug_message="DEBUG: Fine funzione record_macro_thread_target.",
        ),
    )

def emergency_stop_all():
    """Ferma immediatamente tutte le operazioni in corso in modo forzato"""
    console_log("🚨 STOP EMERGENZA - Fermando immediatamente tutte le operazioni...")
    
    # Ferma immediatamente tutti i flag
    state_service.stop_recording()
    reset_playback_state()
    request_playback_stop(console_log)
    
    # Ferma il timer di registrazione
    stop_recording_timer()
    emergency_cleanup()
    console_log("✅ STOP EMERGENZA completato - Tutte le operazioni sono state fermate.")


def stop_current_operation():
    """Ferma qualsiasi registrazione o riproduzione in corso in modo più responsivo."""
    # Check se la GUI è ancora attiva prima di usare console_log
    gui_active = root and root.winfo_exists()
    
    if gui_active:
        console_log("🛑 Tentativo di fermare le operazioni in corso...")
    
    if app_state.recording_flag:
        stop_active_recording(gui_active)
    elif app_state.playing_flag:
        stop_active_playback(gui_active)
    else:
        if gui_active:
            console_log("ℹ️ Nessuna operazione attiva da fermare.")
        return

    finalize_stop_operation(gui_active)


def start_playback_thread():
    selected_macro = get_selected_macro_metadata(
        action_label="Riproduzione",
        missing_selection_message="Seleziona una macro dalla lista per riprodurla.",
        invalid_selection_message="ID macro non valido selezionato.",
        missing_metadata_message="Metadati macro non trovati.",
        parent=root,
        log_invalid_selection="❌ Errore: ID macro non valido dalla selezione: {macro_id_str}",
        log_missing_metadata="❌ Errore: Metadati macro non trovati per ID: {macro_id}",
    )
    if not selected_macro:
        return
    macro_id, macro_metadata = selected_macro

    macro_kind = macro_metadata.get("macro_kind", "standard")
    macro_events = load_macro_events(macro_id)
    if macro_kind != "system" and not macro_events:
        messagebox.showwarning("Riproduzione Macro", f"Nessun evento trovato per la macro '{macro_metadata['nome']}'.", parent=root)
        console_log(f"⚠️ Nessun evento trovato per la macro '{macro_metadata['nome']}'.", level="WARNING")
        return

    if macro_kind == "system":
        try:
            run_system_macro(macro_metadata, console_log)
            update_status("Macro di sistema eseguita", indicator="idle")
        except Exception as exc:
            messagebox.showerror("Macro di sistema", f"Errore durante l'esecuzione della macro di sistema:\n{exc}", parent=root)
            console_log(f"❌ Errore macro di sistema '{macro_metadata['nome']}': {exc}", level="ERROR")
        return

    target_exe = macro_metadata['eseguibile']
    elevation_state = target_requires_elevation(target_exe)
    if elevation_state["requires_restart"]:
        should_restart = messagebox.askyesno(
            "Riavvio come amministratore",
            build_restart_as_admin_message(target_exe),
            parent=root,
        )
        if should_restart:
            console_log(
                f"⚠️ Riavvio richiesto come amministratore per controllare '{target_exe}'.",
                level="WARNING",
            )
            if relaunch_current_process_as_admin():
                close_current_window_after_admin_relaunch()
                return
            messagebox.showerror(
                "Riavvio non riuscito",
                "Non sono riuscito ad avviare di nuovo l'app come amministratore.",
                parent=root,
            )
            return

        console_log(
            f"⚠️ Riproduzione annullata: '{target_exe}' gira come amministratore ma l'app no.",
            level="WARNING",
        )
        update_status("Riavvio admin consigliato", indicator="idle")
        return

    logger.info(
        "Avvio playback richiesto: macro='%s' id=%s target='%s' eventi=%s",
        macro_metadata["nome"],
        macro_id,
        target_exe,
        len(macro_events),
    )
    loop_enabled = loop_var.get()
    loop_delay = get_loop_delay() # Questa funzione è già robusta
    max_repetitions = get_max_repetitions() # Ottiene il numero massimo di ripetizioni

    if app_state.playing_flag:
        messagebox.showwarning("Riproduzione Macro", "Una macro è già in riproduzione.", parent=root)
        return

    clear_playback_stop_request()
    if not playback_service.start_playback(loop_enabled=loop_enabled):
        messagebox.showwarning("Riproduzione Macro", "Una macro è già in riproduzione.", parent=root)
        return
    
    playback_thread = threading.Thread(target=play_macro_thread_target, args=(macro_metadata, macro_events, target_exe, loop_enabled, loop_delay, max_repetitions))
    playback_thread.daemon = True # Il thread terminerà con l'applicazione principale
    playback_thread.start()

    update_button_states()
    update_status(f"🕹️ Attendendo '{target_exe}' in primo piano...", indicator="searching")

def play_macro_thread_target(macro_metadata, macro_events, target_exe, loop_enabled, loop_delay, max_repetitions=None):
    global _game_client_rect_screen
    playback_ui_state = {
        "last_move_ui_update": 0.0,
        "pending_move_event": None,
        "move_events_since_flush": 0,
    }
    
    def gui_log(msg, level="INFO"):
        if "In attesa che" in msg or "waiting for" in msg:
            root.after(0, lambda: update_status(msg, indicator="searching"))
        elif "è in primo piano" in msg or "finestra trovata" in msg or "FINESTRA TROVATA" in msg:
            root.after(0, lambda: update_status(msg, indicator="found"))
        elif "Riproduzione macro completata" in msg or "interrotta" in msg:
            root.after(0, lambda: update_status("Pronto", indicator="idle"))
        elif "non più attiva" in msg:
            root.after(0, lambda: update_status(msg, indicator="idle"))
        console_log(msg, level=level)
    
    def event_callback(event, index, total, action_type, button_or_key=None, x=None, y=None, delta=None, visual_context=None):
        """Callback chiamato per ogni evento eseguito durante la riproduzione"""
        if action_type == "mouse_move":
            playback_ui_state["pending_move_event"] = (event, index, total, action_type, button_or_key, x, y, delta, visual_context)
            playback_ui_state["move_events_since_flush"] += 1

            if not should_flush_playback_move(playback_ui_state, index, total):
                return

            event, index, total, action_type, button_or_key, x, y, delta, visual_context = playback_ui_state["pending_move_event"]

        root.after(
            0,
            lambda event=event, index=index, total=total, action_type=action_type,
                   button_or_key=button_or_key, x=x, y=y, delta=delta, visual_context=visual_context:
                update_execution_visualizer(event, index, total, action_type, button_or_key, x, y, delta, visual_context),
        )
    
    reset_execution_visualizer()

    playback_service.run_playback(
        macro_events=macro_events,
        target_exe=target_exe,
        loop_enabled=loop_enabled,
        loop_delay=loop_delay,
        max_repetitions=max_repetitions,
        gui_log=gui_log,
        event_callback=event_callback,
        wait_for_app_window=wait_for_app_window,
        play_macro_events=play_macro_events,
        is_playback_stop_requested=is_playback_stop_requested,
        start_focus_monitoring=start_focus_monitoring,
        stop_focus_monitoring=stop_focus_monitoring,
        on_target_wait_cancelled=handle_playback_target_wait_cancelled,
        on_target_wait_failed=handle_playback_target_wait_failed,
        on_before_playback=handle_playback_started,
        on_playback_finished=handle_playback_finished,
    )


def edit_selected_macro():
    logger.info("Tentativo di apertura editor macro")
    selected_macro = get_selected_macro_metadata(
        action_label="Modifica",
        missing_selection_message="Seleziona una macro da modificare.",
        invalid_selection_message="ID macro non valido selezionato.",
        missing_metadata_message="Metadati macro non trovati per ID: {macro_id}",
        parent=root,
    )
    if not selected_macro:
        logger.warning("Nessuna macro selezionata per l'editing")
        return

    macro_id_to_edit, macro_metadata = selected_macro
    if macro_metadata.get("macro_kind") == "system":
        messagebox.showinfo(
            "Macro di sistema",
            "Questa macro di sistema per ora può essere duplicata ma non modificata direttamente.",
            parent=root,
        )
        return
    logger.info(f"Editor richiesto per macro ID: {macro_id_to_edit}")
    macro_name = macro_metadata['nome']
    logger.info(f"Apertura editor per macro: {macro_name}")

    # Apri l'editor in una nuova finestra
    editor_root = tk.Toplevel(root)
    editor_root.title(f"Editor Macro: {macro_name}")
    editor_app = macro_editor.MacroEditorApp(editor_root, macro_name)
    editor_root.wait_window() # Attendi che la finestra dell'editor si chiuda

    # Dopo che l'editor si è chiuso, ricarica la lista delle macro per riflettere eventuali modifiche
    logger.info("Editor chiuso, refresh lista macro")
    refresh_macro_ui_state()


def configure_launch_game_system_macro(macro_metadata):
    existing_local_variant = get_local_launch_game_variant_for_current_context()
    source_payload = macro_metadata.get("system_payload") or {}
    prefill_shortcut = (
        (existing_local_variant or {}).get("system_payload", {}).get("shortcut_path")
        or source_payload.get("shortcut_path")
        or ""
    )

    dialog = tk.Toplevel(root)
    dialog.title("Collegamento Locale Gioco")
    dialog.transient(root)
    dialog.grab_set()
    dialog.resizable(False, False)

    ttk.Label(
        dialog,
        text=(
            "Incolla il collegamento o il percorso che usi su questa postazione per avviare il gioco.\n"
            "La macro di sistema base non verrà sovrascritta: salvo una variante locale ricordata."
        ),
        justify="left",
        wraplength=520,
    ).pack(fill="x", padx=16, pady=(16, 10))

    entry_var = tk.StringVar(value=prefill_shortcut)
    shortcut_entry = ttk.Entry(dialog, textvariable=entry_var, width=80)
    shortcut_entry.pack(fill="x", padx=16)
    shortcut_entry.focus_set()
    shortcut_entry.selection_range(0, tk.END)

    status_var = tk.StringVar()
    if existing_local_variant:
        status_var.set(f"Variante locale trovata: {existing_local_variant.get('nome')}")
    else:
        status_var.set("Nessuna variante locale salvata finora per questa postazione.")
    ttk.Label(dialog, textvariable=status_var, justify="left", wraplength=520).pack(fill="x", padx=16, pady=(10, 0))

    button_row = ttk.Frame(dialog)
    button_row.pack(fill="x", padx=16, pady=16)

    def browse_shortcut():
        selected = filedialog.askopenfilename(
            parent=dialog,
            title="Seleziona il collegamento o l'eseguibile del gioco",
            filetypes=[
                ("Collegamenti ed eseguibili", "*.lnk *.exe"),
                ("Tutti i file", "*.*"),
            ],
        )
        if selected:
            entry_var.set(selected)

    def save_local_variant():
        shortcut_path = entry_var.get().strip()
        try:
            macro_id, macro_name, created = save_launch_game_local_variant(shortcut_path, source_macro_metadata=macro_metadata)
        except Exception as exc:
            messagebox.showerror("Collegamento locale", f"Non sono riuscito a salvare il collegamento:\n{exc}", parent=dialog)
            return

        console_log(
            (
                f"✅ Variante locale {'creata' if created else 'aggiornata'} per l'avvio del gioco: "
                f"'{macro_name}' -> {shortcut_path}"
            ),
            level="INFO",
        )
        refresh_macro_ui_state()
        if macro_list_tree and macro_list_tree.winfo_exists():
            macro_list_tree.selection_set(str(macro_id))
            macro_list_tree.focus(str(macro_id))
            macro_list_tree.see(str(macro_id))
        update_macro_details()
        update_button_states()
        dialog.destroy()

    ttk.Button(button_row, text="Sfoglia", command=browse_shortcut).pack(side="left")
    ttk.Button(button_row, text="Annulla", command=dialog.destroy).pack(side="right")
    ttk.Button(button_row, text="Salva Variante Locale", command=save_local_variant).pack(side="right", padx=(0, 8))

    dialog.bind("<Return>", lambda event: save_local_variant())
    dialog.wait_window()


def open_selected_macro_action():
    selected_macro = get_selected_macro_metadata(
        action_label="Apertura",
        missing_selection_message="Seleziona una macro.",
        invalid_selection_message="ID macro non valido selezionato.",
        missing_metadata_message="Metadati macro non trovati per ID: {macro_id}",
        parent=root,
    )
    if not selected_macro:
        return

    _macro_id, macro_metadata = selected_macro
    if macro_metadata.get("system_key") == LAUNCH_GAME_SYSTEM_KEY:
        configure_launch_game_system_macro(macro_metadata)
        return

    edit_selected_macro()


def delete_selected_macro():
    selected_macro = get_selected_macro_metadata(
        action_label="Eliminazione",
        missing_selection_message="Seleziona una macro da eliminare.",
        invalid_selection_message="ID macro non valido selezionato.",
        missing_metadata_message="Metadati macro non trovati per ID: {macro_id}",
        parent=root,
    )
    if not selected_macro:
        return
    _macro_id, macro_metadata = selected_macro
    if macro_metadata.get("is_protected"):
        messagebox.showwarning(
            "Macro di sistema",
            "Questa macro di sistema è protetta e non può essere cancellata.",
            parent=root,
        )
        return
    macro_name_to_delete = macro_metadata["nome"]

    confirm = messagebox.askyesno(
        "Conferma Eliminazione",
        f"Sei sicuro di voler eliminare la macro '{macro_name_to_delete}'?\n"
        "Questa azione è irreversibile e include tutti i suoi eventi e backup.",
        parent=root
    )
    if confirm:
        try:
            delete_macro(macro_name_to_delete)
            console_log(f"✅ Macro '{macro_name_to_delete}' eliminata con successo.")
            refresh_macro_ui_state()
        except ValueError as e:
            console_log(f"❌ Errore durante l'eliminazione: {e}", level="ERROR")
            messagebox.showerror("Errore Eliminazione", f"Errore: {e}", parent=root)
        except Exception as e:
            console_log(f"❌ Errore generico durante l'eliminazione: {e}", level="ERROR")
            messagebox.showerror("Errore Eliminazione", f"Errore generico durante l'eliminazione: {e}", parent=root)

def duplicate_selected_macro():
    """Duplica la macro selezionata con un nuovo nome che include la data e ora corrente."""
    selected_macro = get_selected_macro_metadata(
        action_label="Duplicazione",
        missing_selection_message="Seleziona una macro da duplicare.",
        invalid_selection_message="ID macro non valido selezionato.",
        missing_metadata_message="Metadati macro non trovati per ID: {macro_id}",
        parent=root,
        log_missing_selection="⚠️ Seleziona una macro da duplicare.",
        log_invalid_selection="❌ Errore Duplicazione: ID macro non valido selezionato.",
        log_missing_metadata="❌ Errore Duplicazione: Metadati macro non trovati per ID: {macro_id}",
    )
    if not selected_macro:
        return
    macro_id, macro_metadata = selected_macro

    macro_name = macro_metadata['nome']
    
    console_log(f"🔄 Avvio duplicazione macro '{macro_name}'...")

    try:
        new_macro_id, new_macro_name = duplicate_macro(macro_id)
        console_log(f"✅ Macro '{macro_name}' duplicata con successo come '{new_macro_name}' (ID: {new_macro_id}).")
        refresh_macro_ui_state()
    except Exception as e:
        console_log(f"❌ Errore durante la duplicazione della macro '{macro_name}': {e}", level="ERROR")


def concat_macros_dialog():
    """Dialog per concatenare due macro selezionate"""
    dialog = tk.Toplevel(root)
    dialog.title("Concatena Macro")
    dialog.transient(root)
    dialog.grab_set()
    
    # Carica posizione/dimensione salvata per questa finestra
    dialog.geometry("500x300")
    try:
        restore_saved_window_geometry(dialog, "concat_macros_dialog_window", "concat macros dialog")
    except Exception as e:
        dialog.geometry("500x300")
    
    # Salva posizione/dimensione alla chiusura
    def save_dialog_geometry():
        save_window_geometry_config(dialog, "concat_macros_dialog_window", "concat macros dialog")
    
    def on_dialog_close():
        save_dialog_geometry()
        dialog.destroy()
    
    dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)
    apply_dialog_styles(dialog)
    
    # Variabili
    macro1_var = tk.StringVar()
    macro2_var = tk.StringVar()
    nome_var = tk.StringVar()
    
    # Label e combobox per la prima macro
    ttk.Label(dialog, text="Prima Macro:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    macro_options = []
    for macro in get_all_macros():
        macro_options.append(f"{macro['id']} - {macro['nome']} ({macro['eseguibile']})")
    
    macro1_combobox = ttk.Combobox(dialog, values=macro_options, textvariable=macro1_var, width=40, state="readonly")
    macro1_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
    # Salva il valore quando cambia per evitare reset
    def on_macro1_change(event=None):
        # Mantieni il valore corrente della seconda macro quando cambia la prima
        pass
    
    macro1_combobox.bind("<<ComboboxSelected>>", on_macro1_change)
    
    # Label e combobox per la seconda macro
    ttk.Label(dialog, text="Seconda Macro:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
    macro2_combobox = ttk.Combobox(dialog, values=macro_options, textvariable=macro2_var, width=40, state="readonly")
    macro2_combobox.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
    
    # Salva il valore quando cambia per evitare reset
    def on_macro2_change(event=None):
        # Mantieni il valore corrente della prima macro quando cambia la seconda
        pass
    
    macro2_combobox.bind("<<ComboboxSelected>>", on_macro2_change)
    
    # Label e entry per il nome della nuova macro
    ttk.Label(dialog, text="Nome Nuova Macro:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
    nome_entry = ttk.Entry(dialog, textvariable=nome_var, width=40)
    nome_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
    
    # Label informativa
    info_label = ttk.Label(dialog, text="La nuova macro sarà composta dalla sequenza delle due macro senza interruzioni.\nLa durata sarà la somma delle durate delle due macro.", 
                          foreground=config['theme']['text_color'], justify="left")
    info_label.grid(row=3, column=0, columnspan=2, padx=5, pady=10, sticky="w")
    
    def validate_and_concat():
        nome = nome_var.get().strip()
        macro1_str = macro1_var.get()
        macro2_str = macro2_var.get()
        
        if not nome:
            messagebox.showwarning("Input Errato", "Inserisci un nome per la nuova macro.", parent=dialog)
            return
        
        if not macro1_str or not macro2_str:
            messagebox.showwarning("Input Errato", "Seleziona entrambe le macro da concatenare.", parent=dialog)
            return
        
        try:
            macro1_id = int(macro1_str.split(" - ")[0])
            macro2_id = int(macro2_str.split(" - ")[0])
            
            if macro1_id == macro2_id:
                messagebox.showwarning("Input Errato", "Seleziona due macro diverse.", parent=dialog)
                return
            
            # Ottieni i metadati delle macro
            macro1_metadata = get_macro_metadata_by_id(macro1_id)
            macro2_metadata = get_macro_metadata_by_id(macro2_id)
            
            if not macro1_metadata or not macro2_metadata:
                messagebox.showerror("Errore", "Una o entrambe le macro selezionate non esistono.", parent=dialog)
                return
            
            # Carica gli eventi delle due macro
            macro1_events = load_macro_events(macro1_id)
            macro2_events = load_macro_events(macro2_id)
            
            if not macro1_events or not macro2_events:
                messagebox.showerror("Errore", "Una o entrambe le macro non hanno eventi.", parent=dialog)
                return
            
            # Calcola la durata totale della prima macro
            durata_totale_macro1 = macro1_metadata['durata_sec']
            
            # Aggiusta i tempi della seconda macro aggiungendo la durata totale della prima
            macro2_events_adjusted = []
            for event in macro2_events:
                new_event = event.copy()
                new_event['time'] = event['time'] + (durata_totale_macro1 * 1000)  # Converti secondi in millisecondi
                macro2_events_adjusted.append(new_event)
            
            # Concatena gli eventi
            concatenated_events = macro1_events + macro2_events_adjusted
            
            # Calcola la durata totale (somma delle due durate)
            durata_totale = macro1_metadata['durata_sec'] + macro2_metadata['durata_sec']
            
            # Usa l'eseguibile della prima macro (o chiedi all'utente se sono diversi)
            eseguibile = macro1_metadata['eseguibile']
            if macro1_metadata['eseguibile'] != macro2_metadata['eseguibile']:
                console_log(f"⚠️ Le due macro hanno eseguibili diversi: '{macro1_metadata['eseguibile']}' e '{macro2_metadata['eseguibile']}'. Verrà usato '{eseguibile}'.", level="WARNING")
            
            # Crea la descrizione
            descrizione = f"Macro concatenata da '{macro1_metadata['nome']}' e '{macro2_metadata['nome']}'"
            
            # Salva la nuova macro
            try:
                new_macro_id = salva_macro_test(nome, descrizione, durata_totale, eseguibile, concatenated_events, log_callback=console_log)
                console_log(f"✅ Macro concatenata '{nome}' creata con successo (ID: {new_macro_id}). Durata totale: {durata_totale} secondi.")
                save_dialog_geometry()  # Salva la geometria prima di chiudere
                dialog.destroy()
                refresh_macro_list()
                update_macro_details()
            except ValueError as e:
                messagebox.showerror("Errore Creazione", f"Errore: {e}", parent=dialog)
            except Exception as e:
                messagebox.showerror("Errore Creazione", f"Errore generico: {e}", parent=dialog)
                
        except (ValueError, IndexError) as e:
            messagebox.showerror("Errore", f"Errore nella selezione delle macro: {e}", parent=dialog)
        except Exception as e:
            messagebox.showerror("Errore", f"Errore generico: {e}", parent=dialog)
    
    # Frame per i pulsanti
    buttons_frame = ttk.Frame(dialog)
    buttons_frame.grid(row=4, column=0, columnspan=2, pady=10)
    
    ttk.Button(buttons_frame, text="Concatena", command=validate_and_concat).pack(side="left", padx=5)
    ttk.Button(buttons_frame, text="Annulla", command=dialog.destroy).pack(side="left", padx=5)
    
    # Configure grid weights
    dialog.columnconfigure(1, weight=1)

def setup_execution_visualizer(parent):
    """Crea il widget per visualizzare la sequenza di operazioni durante l'esecuzione"""
    global execution_visualizer_events_list, execution_visualizer_canvas, execution_visualizer_status_label
    global execution_visualizer_reference_image_label, execution_visualizer_candidate_image_label
    global execution_visualizer_reference_caption_label, execution_visualizer_candidate_caption_label
    
    main_frame = ttk.Frame(parent)
    main_frame.pack(fill="both", expand=True, padx=5, pady=5)
    main_frame.columnconfigure(0, weight=1)
    main_frame.rowconfigure(2, weight=1)

    execution_visualizer_status_label = ttk.Label(
        main_frame,
        text="Pronto all'esecuzione...",
        font=(config['theme']['font_family'], config['theme']['font_size_medium'], 'bold'),
    )
    execution_visualizer_status_label.grid(row=0, column=0, sticky="ew", pady=(0, 6))

    context_frame = ttk.LabelFrame(main_frame, text="Ritagli controllo click", padding="6")
    context_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
    context_frame.columnconfigure(0, weight=1)

    previews_frame = ttk.Frame(context_frame)
    previews_frame.pack(fill="x", expand=True)

    reference_frame = ttk.Frame(previews_frame)
    reference_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))
    execution_visualizer_reference_caption_label = ttk.Label(
        reference_frame,
        text="Primo riferimento click",
        foreground=config['theme']['text_color'],
        font=(config['theme']['font_family'], config['theme']['font_size_small']),
    )
    execution_visualizer_reference_caption_label.pack(fill="x", pady=(0, 4))
    execution_reference_holder = tk.Frame(
        reference_frame,
        background=config['theme']['border_color'],
        highlightthickness=1,
        highlightbackground=config['theme']['text_color'],
        width=220,
        height=140,
    )
    execution_reference_holder.pack(fill="both", expand=True)
    execution_reference_holder.pack_propagate(False)
    execution_visualizer_reference_image_label = tk.Label(
        execution_reference_holder,
        text="Anteprima non disponibile",
        background=config['theme']['border_color'],
        anchor="center",
    )
    execution_visualizer_reference_image_label.pack(fill="both", expand=True)

    candidate_frame = ttk.Frame(previews_frame)
    candidate_frame.pack(side="left", fill="both", expand=True, padx=(4, 0))
    execution_visualizer_candidate_caption_label = ttk.Label(
        candidate_frame,
        text="Controllo corrente",
        foreground=config['theme']['text_color'],
        font=(config['theme']['font_family'], config['theme']['font_size_small']),
    )
    execution_visualizer_candidate_caption_label.pack(fill="x", pady=(0, 4))
    execution_candidate_holder = tk.Frame(
        candidate_frame,
        background=config['theme']['border_color'],
        highlightthickness=1,
        highlightbackground=config['theme']['text_color'],
        width=220,
        height=140,
    )
    execution_candidate_holder.pack(fill="both", expand=True)
    execution_candidate_holder.pack_propagate(False)
    execution_visualizer_candidate_image_label = tk.Label(
        execution_candidate_holder,
        text="Anteprima non disponibile",
        background=config['theme']['border_color'],
        anchor="center",
    )
    execution_visualizer_candidate_image_label.pack(fill="both", expand=True)

    content_frame = ttk.Frame(main_frame)
    content_frame.grid(row=2, column=0, sticky="nsew")
    content_frame.columnconfigure(0, weight=1)
    content_frame.rowconfigure(0, weight=3)
    content_frame.rowconfigure(1, weight=2)

    canvas_frame = ttk.LabelFrame(content_frame, text="Posizioni Click", padding="6")
    canvas_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
    canvas_frame.columnconfigure(0, weight=1)
    canvas_frame.rowconfigure(0, weight=1)

    execution_visualizer_canvas = tk.Canvas(
        canvas_frame,
        width=460,
        height=260,
        bg="#1f2230",
        highlightthickness=1,
        highlightbackground=config['theme']['text_color'],
    )
    execution_visualizer_canvas.grid(row=0, column=0, sticky="nsew")
    execution_visualizer_canvas.bind("<Configure>", lambda event: redraw_execution_click_history())

    canvas_info_label = ttk.Label(
        canvas_frame,
        text="I click restano tracciati in sequenza: linea, numero progressivo e colore del pulsante.",
        foreground=config['theme']['text_color'],
        font=(config['theme']['font_family'], config['theme']['font_size_small']),
    )
    canvas_info_label.grid(row=1, column=0, sticky="w", pady=(6, 0))

    events_frame = ttk.LabelFrame(content_frame, text="Sequenza Operazioni", padding="6")
    events_frame.grid(row=1, column=0, sticky="nsew")
    events_frame.columnconfigure(0, weight=1)
    events_frame.rowconfigure(0, weight=1)

    listbox_frame = ttk.Frame(events_frame)
    listbox_frame.grid(row=0, column=0, sticky="nsew")
    listbox_frame.columnconfigure(0, weight=1)
    listbox_frame.rowconfigure(0, weight=1)

    execution_visualizer_events_list = tk.Listbox(
        listbox_frame,
        bg=config['theme']['border_color'],
        fg=config['theme']['text_color'],
        font=(config['theme']['font_family'], config['theme']['font_size_small']),
        selectbackground=config['theme']['button_bg_color'],
        selectforeground=config['theme']['button_fg_color'],
        width=80,
    )
    execution_visualizer_events_list.grid(row=0, column=0, sticky="nsew")

    events_scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=execution_visualizer_events_list.yview)
    events_scrollbar.grid(row=0, column=1, sticky="ns")
    execution_visualizer_events_list.configure(yscrollcommand=events_scrollbar.set)

    clear_button = ttk.Button(events_frame, text="🗑️ Pulisci", command=reset_execution_visualizer)
    clear_button.grid(row=1, column=0, sticky="e", pady=(6, 0))
    clear_execution_visualizer_context_preview()

def draw_mouse_position(canvas, x, y, button_name):
    """Disegna la posizione del mouse sul canvas"""
    global execution_click_history

    execution_click_history.append((x, y, (button_name or "").lower()))
    _draw_execution_click_history(canvas, execution_click_history[-50:])


def _draw_execution_click_history(canvas, points):
    """Disegna la traccia dei click adattandola alla dimensione corrente del canvas."""
    if not points:
        return

    canvas.delete("all")

    canvas_width = max(canvas.winfo_width(), 240)
    canvas_height = max(canvas.winfo_height(), 180)
    margin = 24

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)

    span_x = max(max_x - min_x, 1)
    span_y = max(max_y - min_y, 1)

    def scale_point(px, py):
        scaled_x = margin + ((px - min_x) / span_x) * max(canvas_width - (margin * 2), 1)
        scaled_y = margin + ((py - min_y) / span_y) * max(canvas_height - (margin * 2), 1)
        return scaled_x, scaled_y

    canvas.create_rectangle(
        margin // 2,
        margin // 2,
        canvas_width - (margin // 2),
        canvas_height - (margin // 2),
        outline="#5c6370",
        dash=(4, 3),
    )

    button_colors = {
        'left': '#ff6e6e',
        'right': '#61afef',
        'middle': '#50fa7b',
    }
    scaled_points = [(*scale_point(px, py), btn, px, py) for px, py, btn in points]

    for index in range(1, len(scaled_points)):
        prev_x, prev_y, *_ = scaled_points[index - 1]
        curr_x, curr_y, *_ = scaled_points[index]
        canvas.create_line(prev_x, prev_y, curr_x, curr_y, fill="#8fbcff", width=2, smooth=True)

    for index, (scaled_x, scaled_y, btn, px, py) in enumerate(scaled_points, start=1):
        color = button_colors.get(btn, '#abb2bf')
        radius = 8 if index == len(scaled_points) else 6
        outline_width = 3 if index == len(scaled_points) else 2
        canvas.create_oval(
            scaled_x - radius,
            scaled_y - radius,
            scaled_x + radius,
            scaled_y + radius,
            fill=color,
            outline="#f8f8f2",
            width=outline_width,
        )
        canvas.create_text(
            scaled_x,
            scaled_y - 16,
            text=str(index),
            fill="#f8f8f2",
            font=(config['theme']['font_family'], config['theme']['font_size_small'], 'bold'),
        )

    last_scaled_x, last_scaled_y, _, last_abs_x, last_abs_y = scaled_points[-1]
    canvas.create_text(
        last_scaled_x,
        min(canvas_height - 12, last_scaled_y + 18),
        text=f"Ultimo click: ({last_abs_x},{last_abs_y})",
        fill=config['theme']['text_color'],
        font=(config['theme']['font_family'], config['theme']['font_size_small']),
    )

def setup_ui_graph_browser_interface(parent):
    """Configura una tab dedicata alla consultazione del grafo semantico UI."""
    global ui_graph_tree, ui_graph_details_text, ui_graph_relations_text, ui_graph_macros_text, current_ui_graph_definition

    current_ui_graph_definition = build_default_doomsday_ui_graph()

    main_frame = ttk.Frame(parent)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    main_frame.columnconfigure(0, weight=2)
    main_frame.columnconfigure(1, weight=3)
    main_frame.rowconfigure(1, weight=1)

    header_frame = ttk.Frame(main_frame)
    header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    header_frame.columnconfigure(0, weight=1)

    ttk.Label(
        header_frame,
        text="Browser del grafo semantico UI di Doomsday",
        font=(config['theme']['font_family'], config['theme']['font_size_large'], "bold"),
    ).grid(row=0, column=0, sticky="w")
    ttk.Button(header_frame, text="🔄 Aggiorna", command=refresh_ui_graph_browser).grid(row=0, column=1, padx=(8, 0))
    ttk.Label(
        header_frame,
        text="Esplora viste, pannelli, popup, controlli e macro candidate collegate al grafo del gioco.",
        wraplength=900,
        justify="left",
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

    left_frame = ttk.LabelFrame(main_frame, text="Mappa Gerarchica", padding="10")
    left_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
    left_frame.rowconfigure(0, weight=1)
    left_frame.columnconfigure(0, weight=1)

    ui_graph_tree = ttk.Treeview(left_frame, columns=("kind",), show="tree headings", height=22)
    ui_graph_tree.heading("#0", text="Nodo")
    ui_graph_tree.heading("kind", text="Tipo")
    ui_graph_tree.column("#0", width=280, anchor="w")
    ui_graph_tree.column("kind", width=110, anchor="center")
    ui_graph_tree.grid(row=0, column=0, sticky="nsew")
    ui_graph_tree.bind("<<TreeviewSelect>>", on_ui_graph_node_selected)

    tree_scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=ui_graph_tree.yview)
    tree_scrollbar.grid(row=0, column=1, sticky="ns")
    ui_graph_tree.configure(yscrollcommand=tree_scrollbar.set)

    right_frame = ttk.Frame(main_frame)
    right_frame.grid(row=1, column=1, sticky="nsew")
    right_frame.rowconfigure(0, weight=2)
    right_frame.rowconfigure(1, weight=1)
    right_frame.rowconfigure(2, weight=1)
    right_frame.columnconfigure(0, weight=1)

    details_frame = ttk.LabelFrame(right_frame, text="Dettagli Nodo", padding="10")
    details_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
    details_frame.rowconfigure(0, weight=1)
    details_frame.columnconfigure(0, weight=1)

    ui_graph_details_text = scrolledtext.ScrolledText(
        details_frame,
        wrap="word",
        height=12,
        font=(config['theme']['font_family'], config['theme']['font_size_small']),
        bg=config['theme']['border_color'],
        fg=config['theme']['text_color'],
        insertbackground=config['theme']['text_color'],
    )
    ui_graph_details_text.grid(row=0, column=0, sticky="nsew")
    ui_graph_details_text.config(state=tk.DISABLED)

    relations_frame = ttk.LabelFrame(right_frame, text="Relazioni E Trigger", padding="10")
    relations_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 6))
    relations_frame.rowconfigure(0, weight=1)
    relations_frame.columnconfigure(0, weight=1)

    ui_graph_relations_text = scrolledtext.ScrolledText(
        relations_frame,
        wrap="word",
        height=8,
        font=(config['theme']['font_family'], config['theme']['font_size_small']),
        bg=config['theme']['border_color'],
        fg=config['theme']['text_color'],
        insertbackground=config['theme']['text_color'],
    )
    ui_graph_relations_text.grid(row=0, column=0, sticky="nsew")
    ui_graph_relations_text.config(state=tk.DISABLED)

    macros_frame = ttk.LabelFrame(right_frame, text="Macro Candidate Collegate", padding="10")
    macros_frame.grid(row=2, column=0, sticky="nsew")
    macros_frame.rowconfigure(0, weight=1)
    macros_frame.columnconfigure(0, weight=1)

    ui_graph_macros_text = scrolledtext.ScrolledText(
        macros_frame,
        wrap="word",
        height=8,
        font=(config['theme']['font_family'], config['theme']['font_size_small']),
        bg=config['theme']['border_color'],
        fg=config['theme']['text_color'],
        insertbackground=config['theme']['text_color'],
    )
    ui_graph_macros_text.grid(row=0, column=0, sticky="nsew")
    ui_graph_macros_text.config(state=tk.DISABLED)

    refresh_ui_graph_browser()


def _set_ui_graph_text(widget, content):
    if widget is None:
        return
    widget.config(state=tk.NORMAL)
    widget.delete("1.0", tk.END)
    widget.insert(tk.END, content)
    widget.config(state=tk.DISABLED)


def refresh_ui_graph_browser():
    """Ricarica il browser del grafo UI nella tab dedicata."""
    global current_ui_graph_definition
    if ui_graph_tree is None:
        return

    current_ui_graph_definition = build_default_doomsday_ui_graph()

    for item_id in ui_graph_tree.get_children():
        ui_graph_tree.delete(item_id)

    nodes_by_parent = {}
    for node in current_ui_graph_definition.nodes:
        nodes_by_parent.setdefault(node.parent_node_id, []).append(node)

    for children in nodes_by_parent.values():
        children.sort(key=lambda item: (item.kind, item.label.lower()))

    def insert_children(parent_node_id, tree_parent=""):
        for node in nodes_by_parent.get(parent_node_id, []):
            ui_graph_tree.insert(
                tree_parent,
                "end",
                iid=node.node_id,
                text=node.label,
                values=(node.kind,),
                open=True,
            )
            insert_children(node.node_id, node.node_id)

    insert_children(None, "")

    root_nodes = ui_graph_tree.get_children()
    if root_nodes:
        ui_graph_tree.selection_set(root_nodes[0])
        ui_graph_tree.focus(root_nodes[0])
        on_ui_graph_node_selected()


def on_ui_graph_node_selected(event=None):
    """Aggiorna i dettagli del nodo selezionato nel browser del grafo UI."""
    if ui_graph_tree is None or current_ui_graph_definition is None:
        return

    selection = ui_graph_tree.selection()
    if not selection:
        return

    node_id = selection[0]
    node = current_ui_graph_definition.get_node(node_id)
    if node is None:
        return

    condition_lines = []
    if node.conditions:
        for condition in node.conditions:
            expected_text = "presenza" if condition.expected_presence else "assenza"
            condition_lines.append(
                f"- {condition.condition_id}: {expected_text} | soglia {condition.threshold} | elementi {', '.join(condition.element_names)}"
            )
            if condition.description:
                condition_lines.append(f"  {condition.description}")
    else:
        condition_lines.append("- Nessuna condizione grafica rigida definita")

    details_text = "\n".join(
        [
            f"ID: {node.node_id}",
            f"Titolo: {node.label}",
            f"Tipo: {node.kind}",
            f"Padre: {node.parent_node_id or '-'}",
            f"Ruolo layout: {node.layout_role}",
            f"Recovery action: {node.recovery_action or '-'}",
            f"Tag: {', '.join(node.tags) if node.tags else '-'}",
            "",
            "Condizioni:",
            *condition_lines,
            "",
            "Note:",
            node.notes or "-",
        ]
    )
    _set_ui_graph_text(ui_graph_details_text, details_text)

    relation_lines = []
    outgoing = [edge for edge in current_ui_graph_definition.edges if edge.from_node_id == node_id]
    incoming = [edge for edge in current_ui_graph_definition.edges if edge.to_node_id == node_id]

    if outgoing:
        relation_lines.append("Uscite:")
        for edge in outgoing:
            relation_lines.append(f"- -> {edge.to_node_id} | trigger: {edge.trigger} | azione: {edge.action_name or '-'}")
            if edge.description:
                relation_lines.append(f"  {edge.description}")
    if incoming:
        if relation_lines:
            relation_lines.append("")
        relation_lines.append("Ingressi:")
        for edge in incoming:
            relation_lines.append(f"- <- {edge.from_node_id} | trigger: {edge.trigger} | azione: {edge.action_name or '-'}")
            if edge.description:
                relation_lines.append(f"  {edge.description}")
    if not relation_lines:
        relation_lines.append("Nessuna relazione registrata per questo nodo.")
    _set_ui_graph_text(ui_graph_relations_text, "\n".join(relation_lines))

    try:
        macro_plan = get_macro_plan_for_ui_node(
            graph_id=current_ui_graph_definition.graph_id,
            node_id=node_id,
            intent_key=None,
        )
        if macro_plan.candidate_links:
            macro_lines = []
            for link in macro_plan.candidate_links:
                macro_lines.append(
                    f"- {link.macro_name or 'Macro senza nome'} | relazione: {link.relation_type} | priorita': {link.priority}"
                )
                if link.intent_key:
                    macro_lines.append(f"  intento: {link.intent_key}")
                if link.notes:
                    macro_lines.append(f"  note: {link.notes}")
        else:
            macro_lines = ["Nessuna macro collegata ancora a questo nodo."]
    except Exception as exc:
        macro_lines = [f"Errore lettura collegamenti macro: {exc}"]
    _set_ui_graph_text(ui_graph_macros_text, "\n".join(macro_lines))

# === FUNZIONI PER ELEMENTI GRAFICI DEL GIOCO ===
# Variabili globali per la GUI elementi grafici
game_elements_gallery_canvas = None
game_elements_gallery_frame = None
game_elements_cards = {}
game_elements_card_photos = {}
game_elements_selected_id = None
game_elements_image_label = None
game_elements_details_label = None
game_elements_preview_canvas = None
game_elements_preview_size_label = None
ui_graph_tree = None
ui_graph_details_text = None
ui_graph_relations_text = None
ui_graph_macros_text = None
current_ui_graph_definition = None
knowledge_graph_tree = None
knowledge_graph_details_text = None
knowledge_graph_linked_tree = None
knowledge_graph_model = None
knowledge_graph_items_by_iid = {}


def setup_knowledge_graph_interface(parent):
    """Configura la tab di navigazione del grafo di conoscenza condiviso."""
    global knowledge_graph_tree, knowledge_graph_details_text, knowledge_graph_linked_tree
    refs = build_knowledge_graph_tab(
        parent=parent,
        theme=config["theme"],
        refresh_knowledge_graph=refresh_knowledge_graph_view,
        on_knowledge_graph_select=on_knowledge_graph_selected,
    )
    knowledge_graph_tree = refs["knowledge_tree"]
    knowledge_graph_details_text = refs["details_text"]
    knowledge_graph_linked_tree = refs["linked_tree"]
    refresh_knowledge_graph_view()


def refresh_knowledge_graph_view():
    """Ricarica il grafo condiviso e popola la TreeView multilivello."""
    global knowledge_graph_model, knowledge_graph_items_by_iid
    if not knowledge_graph_tree:
        return
    try:
        knowledge_graph_model = load_knowledge_graph_model()
    except Exception as exc:
        console_log(f"Errore caricamento grafo conoscenza: {exc}", level="ERROR")
        return

    knowledge_graph_items_by_iid = {}
    for item in knowledge_graph_tree.get_children():
        knowledge_graph_tree.delete(item)

    graph = knowledge_graph_model["graph"]
    graph_iid = f"graph:{graph.get('graph_id', 'shared')}"
    knowledge_graph_tree.insert(
        "",
        "end",
        iid=graph_iid,
        text=graph.get("name") or graph.get("graph_id") or "Grafo conoscenza",
        values=("graph", f"{len(knowledge_graph_model['nodes'])} nodi"),
        open=True,
    )
    knowledge_graph_items_by_iid[graph_iid] = ("graph", graph)

    for node in knowledge_graph_model["children_by_parent"].get("__root__", []):
        _insert_knowledge_node(graph_iid, node)

    _set_knowledge_details("graph", graph)


def _insert_knowledge_node(parent_iid, node):
    node_id = node.get("node_id")
    iid = f"node:{node_id}"
    linked_count = len(knowledge_graph_model["elements_by_node"].get(node_id, []))
    click_count = len(knowledge_graph_model["clicks_by_node"].get(node_id, []))
    agganci = linked_count + click_count
    knowledge_graph_tree.insert(
        parent_iid,
        "end",
        iid=iid,
        text=node.get("label") or node_id,
        values=(node.get("kind", "node"), agganci),
        open=node.get("parent_node_id") is None,
    )
    knowledge_graph_items_by_iid[iid] = ("node", node)

    for child in knowledge_graph_model["children_by_parent"].get(node_id, []):
        _insert_knowledge_node(iid, child)

    _insert_knowledge_elements(iid, node_id)
    _insert_knowledge_edges(iid, node_id)
    _insert_knowledge_clicks(iid, node_id)


def _insert_knowledge_elements(parent_iid, node_id):
    elements = knowledge_graph_model["elements_by_node"].get(node_id, [])
    if not elements:
        return
    group_iid = f"elements:{node_id}"
    knowledge_graph_tree.insert(parent_iid, "end", iid=group_iid, text="Elementi censiti", values=("group", len(elements)))
    knowledge_graph_items_by_iid[group_iid] = ("group", {"label": "Elementi censiti", "node_id": node_id})
    for element in elements:
        element_iid = f"element:{node_id}:{element.get('id')}"
        knowledge_graph_tree.insert(
            group_iid,
            "end",
            iid=element_iid,
            text=element.get("name") or f"Elemento {element.get('id')}",
            values=("element", element.get("id")),
        )
        knowledge_graph_items_by_iid[element_iid] = ("element", element)


def _insert_knowledge_edges(parent_iid, node_id):
    edges = knowledge_graph_model["edges_by_source"].get(node_id, [])
    if not edges:
        return
    group_iid = f"edges:{node_id}"
    knowledge_graph_tree.insert(parent_iid, "end", iid=group_iid, text="Transizioni", values=("group", len(edges)))
    knowledge_graph_items_by_iid[group_iid] = ("group", {"label": "Transizioni", "node_id": node_id})
    for index, edge in enumerate(edges):
        edge_iid = f"edge:{node_id}:{index}"
        knowledge_graph_tree.insert(
            group_iid,
            "end",
            iid=edge_iid,
            text=f"{edge.get('trigger')} -> {edge.get('to_node_id')}",
            values=("edge", edge.get("action_name") or ""),
        )
        knowledge_graph_items_by_iid[edge_iid] = ("edge", edge)


def _insert_knowledge_clicks(parent_iid, node_id):
    clicks = knowledge_graph_model["clicks_by_node"].get(node_id, [])
    if not clicks:
        return
    group_iid = f"clicks:{node_id}"
    knowledge_graph_tree.insert(parent_iid, "end", iid=group_iid, text="Click osservati", values=("group", len(clicks)))
    knowledge_graph_items_by_iid[group_iid] = ("group", {"label": "Click osservati", "node_id": node_id})
    for index, click in enumerate(clicks):
        click_iid = f"click:{node_id}:{index}"
        knowledge_graph_tree.insert(
            group_iid,
            "end",
            iid=click_iid,
            text=f"{click.get('macro_name')} #{index + 1}",
            values=("click", click.get("game_element_id") or ""),
        )
        knowledge_graph_items_by_iid[click_iid] = ("click", click)


def on_knowledge_graph_selected():
    """Aggiorna dettaglio e lista agganci quando l'utente seleziona un nodo."""
    if not knowledge_graph_tree:
        return
    selected = knowledge_graph_tree.selection()
    if not selected:
        return
    item_kind, item = knowledge_graph_items_by_iid.get(selected[0], ("unknown", {}))
    _set_knowledge_details(item_kind, item)


def _set_knowledge_details(item_kind, item):
    if not knowledge_graph_details_text or knowledge_graph_model is None:
        return
    details = format_knowledge_graph_details(item_kind, item, knowledge_graph_model)
    knowledge_graph_details_text.configure(state="normal")
    knowledge_graph_details_text.delete("1.0", "end")
    knowledge_graph_details_text.insert("1.0", details)
    knowledge_graph_details_text.configure(state="disabled")
    _refresh_knowledge_linked_items(item_kind, item)


def _refresh_knowledge_linked_items(item_kind, item):
    if not knowledge_graph_linked_tree or knowledge_graph_model is None:
        return
    for row in knowledge_graph_linked_tree.get_children():
        knowledge_graph_linked_tree.delete(row)
    if item_kind != "node":
        return
    node_id = item.get("node_id")
    for element in knowledge_graph_model["elements_by_node"].get(node_id, []):
        knowledge_graph_linked_tree.insert(
            "",
            "end",
            values=(element.get("id"), "elemento", element.get("name")),
        )
    for click in knowledge_graph_model["clicks_by_node"].get(node_id, []):
        knowledge_graph_linked_tree.insert(
            "",
            "end",
            values=(click.get("macro_id"), "click", click.get("macro_name")),
        )

def setup_game_elements_interface(parent):
    """Configura l'interfaccia per gli elementi grafici del gioco"""
    global game_elements_gallery_canvas, game_elements_gallery_frame
    global game_elements_image_label, game_elements_details_label
    global game_elements_preview_canvas, game_elements_preview_size_label
    
    main_frame = ttk.Frame(parent)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Frame principale con layout a due colonne
    content_frame = ttk.Frame(main_frame)
    content_frame.pack(fill="both", expand=True)
    
    # --- Colonna sinistra: Lista elementi ---
    left_frame = ttk.LabelFrame(content_frame, text="Galleria Elementi", padding="10")
    left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
    
    # Frame per i pulsanti di azione
    buttons_frame = ttk.Frame(left_frame)
    buttons_frame.pack(fill="x", pady=(0, 10))
    
    ttk.Button(buttons_frame, text="➕ Nuovo Elemento", command=create_new_game_element_dialog).pack(side="left", padx=5)
    ttk.Button(buttons_frame, text="✏️ Modifica", command=edit_selected_game_element).pack(side="left", padx=5)
    ttk.Button(buttons_frame, text="✂️ Ritaglia", command=crop_selected_game_element).pack(side="left", padx=5)
    ttk.Button(buttons_frame, text="🗑️ Elimina", command=delete_selected_game_element).pack(side="left", padx=5)
    ttk.Button(buttons_frame, text="🔄 Aggiorna", command=refresh_game_elements_list).pack(side="left", padx=5)
    
    gallery_frame = ttk.Frame(left_frame)
    gallery_frame.pack(fill="both", expand=True)

    game_elements_gallery_canvas = tk.Canvas(
        gallery_frame,
        background=config['theme']['background_color'],
        highlightthickness=0,
        bd=0,
    )
    gallery_scrollbar = ttk.Scrollbar(gallery_frame, orient="vertical", command=game_elements_gallery_canvas.yview)
    game_elements_gallery_canvas.configure(yscrollcommand=gallery_scrollbar.set)
    game_elements_gallery_canvas.pack(side="left", fill="both", expand=True)
    gallery_scrollbar.pack(side="right", fill="y")

    game_elements_gallery_frame = ttk.Frame(game_elements_gallery_canvas)
    gallery_window = game_elements_gallery_canvas.create_window((0, 0), window=game_elements_gallery_frame, anchor="nw")

    def update_gallery_scroll_region(event=None):
        if game_elements_gallery_canvas and game_elements_gallery_frame:
            game_elements_gallery_canvas.configure(scrollregion=game_elements_gallery_canvas.bbox("all"))

    def update_gallery_width(event):
        if game_elements_gallery_canvas:
            game_elements_gallery_canvas.itemconfigure(gallery_window, width=event.width)

    game_elements_gallery_frame.bind("<Configure>", update_gallery_scroll_region)
    game_elements_gallery_canvas.bind("<Configure>", update_gallery_width)
    
    # --- Colonna destra: Anteprima immagine ---
    right_frame = ttk.LabelFrame(content_frame, text="Anteprima Elemento", padding="10")
    right_frame.pack(side="right", fill="both", expand=False, padx=(5, 0))
    right_frame.configure(width=400)
    
    preview_hint_label = ttk.Label(
        right_frame,
        text="Anteprima 1:1 senza ridimensionamento. Usa le barre per scorrere.",
        justify="left",
        wraplength=360,
    )
    preview_hint_label.pack(fill="x", pady=(0, 6))

    preview_canvas_frame = ttk.Frame(right_frame)
    preview_canvas_frame.pack(fill="both", expand=True, pady=(0, 8))

    game_elements_preview_canvas = tk.Canvas(
        preview_canvas_frame,
        bg=config['theme']['border_color'],
        highlightthickness=1,
        highlightbackground=config['theme']['border_color'],
    )
    preview_v_scroll = ttk.Scrollbar(preview_canvas_frame, orient="vertical", command=game_elements_preview_canvas.yview)
    preview_h_scroll = ttk.Scrollbar(preview_canvas_frame, orient="horizontal", command=game_elements_preview_canvas.xview)
    game_elements_preview_canvas.configure(
        yscrollcommand=preview_v_scroll.set,
        xscrollcommand=preview_h_scroll.set,
    )

    preview_canvas_frame.rowconfigure(0, weight=1)
    preview_canvas_frame.columnconfigure(0, weight=1)
    game_elements_preview_canvas.grid(row=0, column=0, sticky="nsew")
    preview_v_scroll.grid(row=0, column=1, sticky="ns")
    preview_h_scroll.grid(row=1, column=0, sticky="ew")

    game_elements_image_label = None
    game_elements_preview_size_label = ttk.Label(
        right_frame,
        text="Seleziona un elemento per vedere l'anteprima 1:1.",
        justify="left",
    )
    game_elements_preview_size_label.pack(fill="x", pady=(0, 6))
    
    # Label per i dettagli
    game_elements_details_label = ttk.Label(right_frame, text="", foreground=config['theme']['text_color'], wraplength=360)
    game_elements_details_label.pack(fill="x", pady=5)
    
    # Carica la lista iniziale
    refresh_game_elements_list()

def refresh_game_elements_list():
    """Aggiorna la galleria degli elementi grafici"""
    global game_elements_cards, game_elements_card_photos, game_elements_selected_id
    if not game_elements_gallery_frame:
        return

    for child in game_elements_gallery_frame.winfo_children():
        child.destroy()
    game_elements_cards = {}
    game_elements_card_photos = {}

    try:
        elements = get_all_game_elements()
        if not elements:
            empty_label = ttk.Label(
                game_elements_gallery_frame,
                text="Nessun elemento registrato.\nUsa 'Nuovo Elemento' per iniziare una libreria visiva pulita.",
                justify="center",
            )
            empty_label.grid(row=0, column=0, padx=12, pady=20, sticky="nsew")
        else:
            columns = 3
            for index, element in enumerate(elements):
                row = index // columns
                column = index % columns
                card = build_game_element_gallery_card(game_elements_gallery_frame, element)
                card.grid(row=row, column=column, padx=8, pady=8, sticky="n")
                game_elements_cards[element["id"]] = card

            for column in range(columns):
                game_elements_gallery_frame.columnconfigure(column, weight=1)

            if game_elements_selected_id in game_elements_cards:
                select_game_element_by_id(game_elements_selected_id)
            else:
                game_elements_selected_id = None
                clear_game_element_preview()
    except Exception as e:
        console_log(f"❌ Errore nel caricamento degli elementi: {e}", level="ERROR")

def build_game_element_gallery_card(parent, element):
    """Crea una card grafica selezionabile per la galleria elementi."""
    card = tk.Frame(
        parent,
        bg=config['theme']['background_color'],
        highlightbackground=config['theme']['border_color'],
        highlightcolor=config['theme']['button_bg_color'],
        highlightthickness=1,
        bd=0,
        cursor="hand2",
        padx=6,
        pady=6,
    )
    card.element_id = element["id"]

    preview_label = tk.Label(
        card,
        bg=config['theme']['border_color'],
        fg=config['theme']['text_color'],
        text="Anteprima",
        width=18,
        height=8,
        cursor="hand2",
    )
    preview_label.pack(fill="both", expand=True)

    title_label = tk.Label(
        card,
        text=element["nome"],
        bg=config['theme']['background_color'],
        fg=config['theme']['text_color'],
        font=(config['theme']['font_family'], config['theme']['font_size_medium'], "bold"),
        wraplength=170,
        justify="center",
        cursor="hand2",
    )
    title_label.pack(fill="x", pady=(6, 2))

    meta_label = tk.Label(
        card,
        text=f"{element['formato_immagine']}  •  ID {element['id']}",
        bg=config['theme']['background_color'],
        fg=config['theme']['text_color'],
        font=(config['theme']['font_family'], config['theme']['font_size_small']),
        cursor="hand2",
    )
    meta_label.pack(fill="x")

    try:
        full_element = get_game_element_by_id(element["id"])
        if full_element:
            image = blob_to_image(full_element['immagine'], full_element['formato_immagine'])
            photo = render_preview_image(image, preview_label, max_size=(160, 120))
            game_elements_card_photos[element["id"]] = photo
    except Exception as exc:
        preview_label.configure(text=f"Errore anteprima\n{exc}")

    for widget in (card, preview_label, title_label, meta_label):
        widget.bind("<Button-1>", lambda event, element_id=element["id"]: select_game_element_by_id(element_id))
        widget.bind("<Double-Button-1>", lambda event, element_id=element["id"]: open_game_element_from_gallery(element_id))

    return card

def clear_game_element_preview():
    """Svuota anteprima e dettagli dopo cancellazione o refresh."""
    global game_elements_selected_id
    game_elements_selected_id = None
    if game_elements_preview_canvas:
        game_elements_preview_canvas.delete("all")
        game_elements_preview_canvas.configure(scrollregion=(0, 0, 1, 1))
        game_elements_preview_canvas.image = None
    if game_elements_preview_size_label:
        game_elements_preview_size_label.configure(text="Seleziona un elemento per vedere l'anteprima 1:1.")
    if game_elements_details_label:
        game_elements_details_label.configure(text="")

def update_game_element_card_selection():
    """Aggiorna l'evidenza visiva della card selezionata."""
    for element_id, card in game_elements_cards.items():
        selected = element_id == game_elements_selected_id
        card.configure(
            highlightthickness=3 if selected else 1,
            highlightbackground=config['theme']['button_bg_color'] if selected else config['theme']['border_color'],
        )

def select_game_element_by_id(element_id):
    """Seleziona un elemento della galleria e aggiorna anteprima e dettagli."""
    global game_elements_selected_id
    if not element_id:
        return

    try:
        element_id = int(element_id)
        game_elements_selected_id = element_id
        update_game_element_card_selection()
        element = get_game_element_by_id(element_id)
        if element:
            image = blob_to_image(element['immagine'], element['formato_immagine'])
            render_fullsize_image_on_canvas(
                image,
                game_elements_preview_canvas,
                background=config['theme']['border_color'],
            )
            if game_elements_preview_size_label:
                game_elements_preview_size_label.configure(
                    text=f"Dimensione reale: {image.width}x{image.height}px"
                )
            details_text = build_game_element_details_text(element)
            if game_elements_details_label:
                game_elements_details_label.configure(text=details_text)
    except Exception as e:
        console_log(f"❌ Errore nel caricamento dell'anteprima: {e}", level="ERROR")

def open_game_element_from_gallery(element_id):
    """Apre l'editor dell'elemento selezionato dalla galleria."""
    select_game_element_by_id(element_id)
    edit_selected_game_element()


def open_game_element_crop_dialog(source_image, *, title):
    """Apre un piccolo editor per ritagliare meglio un elemento senza deformarlo."""
    if source_image is None:
        return None

    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.transient(root)
    dialog.grab_set()
    dialog.geometry("920x760")
    apply_dialog_styles(dialog)

    ttk.Label(
        dialog,
        text=(
            "Seleziona il riquadro da tenere. La vista qui sotto serve solo per lavorare meglio: "
            "il salvataggio usera' sempre i pixel originali senza ridimensionare l'elemento."
        ),
        wraplength=860,
        justify="left",
    ).pack(fill="x", padx=12, pady=(12, 6))

    original_image = source_image.copy()
    display_size = compute_crop_display_size(original_image.size, (860, 560))
    display_image = original_image.copy()
    if display_image.size != display_size:
        display_image = display_image.resize(display_size, game_elements.Image.Resampling.LANCZOS)

    photo = game_elements.ImageTk.PhotoImage(display_image)
    canvas_frame = ttk.Frame(dialog)
    canvas_frame.pack(fill="both", expand=True, padx=12, pady=8)
    canvas = tk.Canvas(
        canvas_frame,
        width=display_size[0],
        height=display_size[1],
        bg=config['theme']['border_color'],
        highlightthickness=1,
        highlightbackground=config['theme']['border_color'],
    )
    canvas.pack(fill="both", expand=True)
    canvas.create_image(0, 0, image=photo, anchor="nw")
    canvas.image = photo

    info_var = tk.StringVar(
        value=(
            f"Originale: {original_image.width}x{original_image.height}px  |  "
            f"Vista di lavoro: {display_size[0]}x{display_size[1]}px"
        )
    )
    ttk.Label(dialog, textvariable=info_var, justify="left").pack(fill="x", padx=12, pady=(0, 6))

    result = {"image": None}
    selection_state = {
        "start": None,
        "box": None,
        "rect": None,
    }

    def clamp_point(x, y):
        return (
            max(0, min(display_size[0], int(round(x)))),
            max(0, min(display_size[1], int(round(y)))),
        )

    def update_selection_box(x1, y1, x2, y2):
        left, top = clamp_point(min(x1, x2), min(y1, y2))
        right, bottom = clamp_point(max(x1, x2), max(y1, y2))
        selection_state["box"] = (left, top, right, bottom)
        if selection_state["rect"] is None:
            selection_state["rect"] = canvas.create_rectangle(
                left,
                top,
                right,
                bottom,
                outline="#00E0FF",
                width=2,
                dash=(5, 3),
            )
        else:
            canvas.coords(selection_state["rect"], left, top, right, bottom)

        width = max(0, right - left)
        height = max(0, bottom - top)
        info_var.set(
            f"Originale: {original_image.width}x{original_image.height}px  |  "
            f"Selezione vista: {width}x{height}px"
        )

    def start_selection(event):
        selection_state["start"] = clamp_point(event.x, event.y)
        update_selection_box(*selection_state["start"], *selection_state["start"])

    def drag_selection(event):
        if not selection_state["start"]:
            return
        update_selection_box(*selection_state["start"], event.x, event.y)

    def end_selection(event):
        if not selection_state["start"]:
            return
        update_selection_box(*selection_state["start"], event.x, event.y)
        selection_state["start"] = None

    def reset_selection():
        selection_state["start"] = None
        selection_state["box"] = None
        if selection_state["rect"] is not None:
            canvas.delete(selection_state["rect"])
            selection_state["rect"] = None
        info_var.set(
            f"Originale: {original_image.width}x{original_image.height}px  |  "
            f"Vista di lavoro: {display_size[0]}x{display_size[1]}px"
        )

    def use_entire_image():
        result["image"] = original_image.copy()
        dialog.destroy()

    def apply_crop():
        selection_box = selection_state["box"]
        if not selection_box:
            messagebox.showwarning("Ritaglio elemento", "Disegna prima il riquadro da tenere.", parent=dialog)
            return
        try:
            crop_bounds = map_display_selection_to_original(
                selection_box,
                original_size=original_image.size,
                display_size=display_size,
            )
        except ValueError as exc:
            messagebox.showwarning("Ritaglio elemento", str(exc), parent=dialog)
            return

        if (crop_bounds[2] - crop_bounds[0]) < 8 or (crop_bounds[3] - crop_bounds[1]) < 8:
            messagebox.showwarning(
                "Ritaglio elemento",
                "Il ritaglio e' troppo piccolo. Allarga un po' la selezione.",
                parent=dialog,
            )
            return
        result["image"] = original_image.crop(crop_bounds)
        dialog.destroy()

    canvas.bind("<ButtonPress-1>", start_selection)
    canvas.bind("<B1-Motion>", drag_selection)
    canvas.bind("<ButtonRelease-1>", end_selection)

    buttons_frame = ttk.Frame(dialog)
    buttons_frame.pack(fill="x", padx=12, pady=(4, 12))
    ttk.Button(buttons_frame, text="✂️ Applica Ritaglio", command=apply_crop).pack(side="left", padx=4)
    ttk.Button(buttons_frame, text="🧹 Reset", command=reset_selection).pack(side="left", padx=4)
    ttk.Button(buttons_frame, text="🖼️ Tieni Immagine Intera", command=use_entire_image).pack(side="left", padx=4)
    ttk.Button(buttons_frame, text="Annulla", command=dialog.destroy).pack(side="right", padx=4)

    dialog.wait_window()
    return result["image"]


def save_cropped_game_element_image(element_id, *, nome, descrizione, source_image, source_format):
    """Salva un ritaglio aggiornando l'elemento o riusando un duplicato gia' noto."""
    semantic_hint = ""
    if "[semantic_hint]" in (descrizione or ""):
        _, semantic_hint = (descrizione or "").split("[semantic_hint]", 1)
        semantic_hint = semantic_hint.strip()

    prepared_asset = prepare_game_element_asset(
        source_image,
        source_format=source_format,
        semantic_hint=semantic_hint,
    )
    matched_element = find_matching_game_element(
        prepared_asset.image,
        ignore_element_id=element_id,
    )
    if matched_element is not None:
        messagebox.showinfo(
            "Elemento gia' presente",
            (
                "Questo ritaglio corrisponde a un elemento gia' censito.\n\n"
                f"Sara' riusato: {matched_element['nome']} (ID: {matched_element['id']})."
            ),
            parent=root,
        )
        refresh_game_elements_list()
        select_game_element_by_id(int(matched_element["id"]))
        return

    image_blob = image_to_blob(prepared_asset.image, prepared_asset.storage_format)
    update_game_element(
        element_id,
        nome=nome,
        descrizione=descrizione,
        immagine_blob=image_blob,
        formato_immagine=prepared_asset.storage_format,
    )
    console_log(f"✅ Ritaglio aggiornato per '{nome}'.")
    refresh_game_elements_list()
    select_game_element_by_id(element_id)


def crop_selected_game_element():
    """Permette di rifinire il ritaglio di un elemento senza eliminarlo."""
    global game_elements_selected_id
    if not game_elements_selected_id:
        messagebox.showwarning("Ritaglia Elemento", "Seleziona un elemento da ritagliare.")
        return

    try:
        element_id = int(game_elements_selected_id)
        element = get_game_element_by_id(element_id)
        if not element:
            messagebox.showerror("Ritaglia Elemento", "Elemento non trovato.")
            return

        current_image = blob_to_image(element['immagine'], element['formato_immagine'])
        cropped_image = open_game_element_crop_dialog(
            current_image,
            title=f"Ritaglia Elemento: {element['nome']}",
        )
        if cropped_image is None:
            return

        save_cropped_game_element_image(
            element_id,
            nome=element['nome'],
            descrizione=element.get('descrizione') or "",
            source_image=cropped_image,
            source_format=element['formato_immagine'] or "PNG",
        )
    except Exception as e:
        messagebox.showerror("Ritaglia Elemento", f"Errore: {e}")

def create_new_game_element_dialog():
    """Dialog per creare un nuovo elemento grafico"""
    dialog = tk.Toplevel(root)
    dialog.title("Nuovo Elemento Grafico")
    dialog.transient(root)
    dialog.grab_set()
    dialog.geometry("500x400")
    apply_dialog_styles(dialog)
    
    # Variabili
    nome_var = tk.StringVar()
    descrizione_var = tk.StringVar()
    semantic_hint_var = tk.StringVar()
    current_image = None
    current_formato = None
    prepared_asset = None
    
    # Nome elemento
    ttk.Label(dialog, text="Nome Elemento:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    nome_entry = ttk.Entry(dialog, textvariable=nome_var, width=40)
    nome_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
    # Descrizione
    ttk.Label(dialog, text="Descrizione / contesto:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
    descrizione_entry = ttk.Entry(dialog, textvariable=descrizione_var, width=40)
    descrizione_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

    ttk.Label(dialog, text="Ruolo semantico:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
    semantic_hint_entry = ttk.Entry(dialog, textvariable=semantic_hint_var, width=40)
    semantic_hint_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

    procedure_frame = ttk.LabelFrame(dialog, text="Procedura Consigliata", padding="8")
    procedure_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=(8, 4))
    procedure_text = "\n".join(f"• {line}" for line in build_game_element_ingestion_guidelines())
    ttk.Label(procedure_frame, text=procedure_text, justify="left", wraplength=440).pack(fill="x")
    
    # Frame per i pulsanti di upload
    upload_frame = ttk.LabelFrame(dialog, text="Carica Immagine", padding="10")
    upload_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=5, pady=10)
    
    image_preview_label = ttk.Label(upload_frame, text="Nessuna immagine caricata", 
                                   background=config['theme']['border_color'], width=40)
    image_preview_label.pack(pady=10)
    asset_summary_var = tk.StringVar(value="Nessun elemento preparato.")
    ttk.Label(upload_frame, textvariable=asset_summary_var, justify="left", wraplength=420).pack(fill="x", pady=(0, 8))
    
    buttons_upload_frame = ttk.Frame(upload_frame)
    buttons_upload_frame.pack(fill="x", pady=5)
    
    def refresh_prepared_asset(image, formato):
        nonlocal current_image, current_formato, prepared_asset
        prepared_asset = prepare_game_element_asset(
            image,
            source_format=formato,
            semantic_hint=semantic_hint_var.get(),
        )
        current_image = prepared_asset.image
        current_formato = prepared_asset.storage_format
        render_preview_image(current_image, image_preview_label, max_size=(200, 200))
        asset_summary_var.set(build_prepared_asset_summary(prepared_asset))

    def load_from_file():
        image, formato = load_image_from_file()
        if image:
            refresh_prepared_asset(image, formato)

    def paste_from_clipboard():
        image, formato = paste_image_from_clipboard()
        if image:
            refresh_prepared_asset(image, formato)

    def crop_current_image():
        nonlocal current_image, current_formato
        if not current_image:
            messagebox.showwarning("Ritaglia Elemento", "Carica prima un'immagine.", parent=dialog)
            return
        cropped_image = open_game_element_crop_dialog(
            current_image,
            title="Ritaglia Nuovo Elemento",
        )
        if cropped_image is not None:
            refresh_prepared_asset(cropped_image, current_formato or "PNG")
    
    ttk.Button(buttons_upload_frame, text="📁 Carica da File", command=load_from_file).pack(side="left", padx=5)
    ttk.Button(buttons_upload_frame, text="📋 Incolla da Clipboard", command=paste_from_clipboard).pack(side="left", padx=5)
    ttk.Button(buttons_upload_frame, text="✂️ Ritaglia", command=crop_current_image).pack(side="left", padx=5)
    
    def validate_and_create():
        nome = nome_var.get().strip()
        descrizione = descrizione_var.get().strip()
        
        if not nome:
            messagebox.showwarning("Input Errato", "Il nome dell'elemento non può essere vuoto.", parent=dialog)
            return
        
        if not current_image:
            messagebox.showwarning("Input Errato", "Devi caricare un'immagine.", parent=dialog)
            return
        
        try:
            semantic_hint = semantic_hint_var.get().strip()
            full_description = build_game_element_description(descrizione, semantic_hint)
            upsert_result = create_or_merge_game_element(
                nome,
                full_description,
                current_image,
                current_formato or 'PNG',
            )
            if upsert_result.reused_existing:
                console_log(
                    f"♻️ Elemento gia' censito: riusato '{upsert_result.element_name}' (ID: {upsert_result.element_id})."
                )
            else:
                console_log(f"✅ Elemento '{upsert_result.element_name}' creato con successo (ID: {upsert_result.element_id}).")
            dialog.destroy()
            refresh_game_elements_list()
            select_game_element_by_id(upsert_result.element_id)
        except ValueError as e:
            messagebox.showerror("Errore Creazione", f"Errore: {e}", parent=dialog)
        except Exception as e:
            messagebox.showerror("Errore Creazione", f"Errore generico: {e}", parent=dialog)
    
    semantic_hint_entry.bind(
        "<FocusOut>",
        lambda event: asset_summary_var.set(build_prepared_asset_summary(
            prepare_game_element_asset(current_image, source_format=current_formato, semantic_hint=semantic_hint_var.get())
        )) if current_image else None,
    )

    ttk.Button(dialog, text="Crea Elemento", command=validate_and_create).grid(row=5, column=0, columnspan=2, pady=10)
    dialog.columnconfigure(1, weight=1)

def edit_selected_game_element():
    """Modifica l'elemento grafico selezionato"""
    global game_elements_selected_id
    if not game_elements_selected_id:
        messagebox.showwarning("Modifica Elemento", "Seleziona un elemento da modificare.")
        return
    
    try:
        element_id = int(game_elements_selected_id)
        element = get_game_element_by_id(element_id)
        if not element:
            messagebox.showerror("Errore Modifica", "Elemento non trovato.")
            return
        
        # Dialog di modifica (simile a creazione)
        dialog = tk.Toplevel(root)
        dialog.title(f"Modifica Elemento: {element['nome']}")
        dialog.transient(root)
        dialog.grab_set()
        dialog.geometry("500x400")
        apply_dialog_styles(dialog)
        
        # Variabili precompilate
        nome_var = tk.StringVar(value=element['nome'])
        raw_description = element['descrizione'] or ""
        semantic_hint_value = ""
        if "[semantic_hint]" in raw_description:
            parts = raw_description.split("[semantic_hint]", 1)
            raw_description = parts[0].strip()
            semantic_hint_value = parts[1].strip()
        descrizione_var = tk.StringVar(value=raw_description)
        semantic_hint_var = tk.StringVar(value=semantic_hint_value)
        current_image = blob_to_image(element['immagine'], element['formato_immagine'])
        current_formato = element['formato_immagine']
        prepared_asset = prepare_game_element_asset(current_image, source_format=current_formato, semantic_hint=semantic_hint_value)
        current_image = prepared_asset.image
        current_formato = prepared_asset.storage_format
        
        # Nome elemento
        ttk.Label(dialog, text="Nome Elemento:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        nome_entry = ttk.Entry(dialog, textvariable=nome_var, width=40)
        nome_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Descrizione
        ttk.Label(dialog, text="Descrizione / contesto:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        descrizione_entry = ttk.Entry(dialog, textvariable=descrizione_var, width=40)
        descrizione_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(dialog, text="Ruolo semantico:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        semantic_hint_entry = ttk.Entry(dialog, textvariable=semantic_hint_var, width=40)
        semantic_hint_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        procedure_frame = ttk.LabelFrame(dialog, text="Procedura Consigliata", padding="8")
        procedure_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=(8, 4))
        procedure_text = "\n".join(f"• {line}" for line in build_game_element_ingestion_guidelines())
        ttk.Label(procedure_frame, text=procedure_text, justify="left", wraplength=440).pack(fill="x")
        
        # Frame per i pulsanti di upload
        upload_frame = ttk.LabelFrame(dialog, text="Immagine", padding="10")
        upload_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=5, pady=10)
        
        image_preview_label = ttk.Label(upload_frame, background=config['theme']['border_color'], width=40)
        image_preview_label.pack(pady=10)
        asset_summary_var = tk.StringVar(value=build_prepared_asset_summary(prepared_asset))
        ttk.Label(upload_frame, textvariable=asset_summary_var, justify="left", wraplength=420).pack(fill="x", pady=(0, 8))
        
        # Mostra anteprima corrente
        render_preview_image(current_image, image_preview_label, max_size=(200, 200), clear_text=False)
        
        buttons_upload_frame = ttk.Frame(upload_frame)
        buttons_upload_frame.pack(fill="x", pady=5)
        
        def refresh_prepared_asset(image, formato):
            nonlocal current_image, current_formato, prepared_asset
            prepared_asset = prepare_game_element_asset(
                image,
                source_format=formato,
                semantic_hint=semantic_hint_var.get(),
            )
            current_image = prepared_asset.image
            current_formato = prepared_asset.storage_format
            render_preview_image(current_image, image_preview_label, max_size=(200, 200), clear_text=False)
            asset_summary_var.set(build_prepared_asset_summary(prepared_asset))

        def load_from_file():
            image, formato = load_image_from_file()
            if image:
                refresh_prepared_asset(image, formato)
        
        def paste_from_clipboard():
            image, formato = paste_image_from_clipboard()
            if image:
                refresh_prepared_asset(image, formato)

        def crop_current_image():
            nonlocal current_image, current_formato
            if not current_image:
                messagebox.showwarning("Ritaglia Elemento", "Nessuna immagine disponibile.", parent=dialog)
                return
            cropped_image = open_game_element_crop_dialog(
                current_image,
                title=f"Ritaglia Elemento: {element['nome']}",
            )
            if cropped_image is not None:
                refresh_prepared_asset(cropped_image, current_formato or "PNG")
        
        ttk.Button(buttons_upload_frame, text="📁 Carica da File", command=load_from_file).pack(side="left", padx=5)
        ttk.Button(buttons_upload_frame, text="📋 Incolla da Clipboard", command=paste_from_clipboard).pack(side="left", padx=5)
        ttk.Button(buttons_upload_frame, text="✂️ Ritaglia", command=crop_current_image).pack(side="left", padx=5)
        
        def validate_and_update():
            nome = nome_var.get().strip()
            descrizione = descrizione_var.get().strip()
            
            if not nome:
                messagebox.showwarning("Input Errato", "Il nome dell'elemento non può essere vuoto.", parent=dialog)
                return
            
            try:
                # Prepara i parametri di update
                semantic_hint = semantic_hint_var.get().strip()
                full_description = build_game_element_description(descrizione, semantic_hint)
                update_params = {'nome': nome, 'descrizione': full_description}
                
                # Se l'immagine è cambiata, aggiorna anche quella
                if current_image:
                    matched_element = create_or_merge_game_element(
                        nome,
                        full_description,
                        current_image,
                        current_formato or 'PNG',
                        ignore_element_id=element_id,
                    )
                    if matched_element.reused_existing:
                        messagebox.showinfo(
                            "Elemento gia' presente",
                            (
                                "L'immagine caricata corrisponde a un elemento gia' censito.\n\n"
                                f"Sara' riusato: {matched_element.element_name} (ID: {matched_element.element_id})."
                            ),
                            parent=dialog,
                        )
                        dialog.destroy()
                        refresh_game_elements_list()
                        select_game_element_by_id(matched_element.element_id)
                        return
                    immagine_blob = image_to_blob(current_image, current_formato or 'PNG')
                    update_params['immagine_blob'] = immagine_blob
                    update_params['formato_immagine'] = current_formato or 'PNG'
                
                update_game_element(element_id, **update_params)
                console_log(f"✅ Elemento '{nome}' aggiornato con successo.")
                dialog.destroy()
                refresh_game_elements_list()
                select_game_element_by_id(element_id)
            except ValueError as e:
                messagebox.showerror("Errore Modifica", f"Errore: {e}", parent=dialog)
            except Exception as e:
                messagebox.showerror("Errore Modifica", f"Errore generico: {e}", parent=dialog)
        
        semantic_hint_entry.bind(
            "<FocusOut>",
            lambda event: asset_summary_var.set(build_prepared_asset_summary(
                prepare_game_element_asset(current_image, source_format=current_formato, semantic_hint=semantic_hint_var.get())
            )) if current_image else None,
        )

        ttk.Button(dialog, text="Salva Modifiche", command=validate_and_update).grid(row=5, column=0, columnspan=2, pady=10)
        dialog.columnconfigure(1, weight=1)
        
    except Exception as e:
        messagebox.showerror("Errore Modifica", f"Errore: {e}")

def delete_selected_game_element():
    """Elimina l'elemento grafico selezionato"""
    global game_elements_selected_id
    if not game_elements_selected_id:
        messagebox.showwarning("Elimina Elemento", "Seleziona un elemento da eliminare.")
        return
    
    try:
        element_id = int(game_elements_selected_id)
        element = get_game_element_by_id(element_id)
        if not element:
            messagebox.showerror("Errore Eliminazione", "Elemento non trovato.")
            return
        references = get_game_element_event_references(element_id)
        reference_count = sum(item["count"] for item in references)
        reference_note = ""
        if reference_count:
            reference_note = (
                f"\n\nNota: questo elemento e' citato da {reference_count} evento/i macro. "
                "La cancellazione rimuove solo l'immagine dal catalogo: gli eventi restano salvati, "
                "ma non avranno piu' l'anteprima collegata."
            )

        confirm_message = (
            f"Eliminare l'elemento grafico?\n\n"
            f"ID: {element['id']}\n"
            f"Nome: {element['nome']}\n"
            f"Formato: {element['formato_immagine']}"
            f"{reference_note}\n\n"
            "Usa questa azione per ripulire crop inutili o sbagliati."
        )

        if messagebox.askyesno("Conferma Eliminazione Elemento", confirm_message):
            delete_game_element(element_id)
            console_log(f"✅ Elemento '{element['nome']}' eliminato con successo.")
            refresh_game_elements_list()
            clear_game_element_preview()
    except Exception as e:
        messagebox.showerror("Errore Eliminazione", f"Errore: {e}")

# === FUNZIONI PER SCHEDULED TASKS ===
# Variabili globali per la GUI scheduled tasks
def setup_scheduled_tasks_interface(parent):
    """Configura l'interfaccia per gli scheduled tasks"""
    global scheduled_tasks_list_tree, scheduled_task_buttons_frame, next_tasks_countdown_frame, next_tasks_countdown_text
    
    # --- Sezione principale Scheduled Tasks ---
    main_frame = ttk.Frame(parent)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Frame per i pulsanti di azione
    scheduled_task_buttons_frame = ttk.Frame(main_frame)
    scheduled_task_buttons_frame.pack(fill="x", pady=(0, 10))
    
    # Pulsanti di gestione scheduled tasks
    new_task_button = ttk.Button(scheduled_task_buttons_frame, text="➕ Nuovo Task", command=create_new_scheduled_task_dialog, style='TButton')
    new_task_button.pack(side="left", padx=5)
    
    edit_scheduled_task_button = ttk.Button(scheduled_task_buttons_frame, text="✏️ Modifica", command=edit_selected_scheduled_task, style='TButton')
    edit_scheduled_task_button.pack(side="left", padx=5)
    
    delete_scheduled_task_button = ttk.Button(scheduled_task_buttons_frame, text="🗑️ Elimina", command=delete_selected_scheduled_task, style='TButton')
    delete_scheduled_task_button.pack(side="left", padx=5)
    
    duplicate_scheduled_task_button = ttk.Button(scheduled_task_buttons_frame, text="📋 Duplica", command=duplicate_selected_scheduled_task, style='TButton')
    duplicate_scheduled_task_button.pack(side="left", padx=5)
    
    toggle_scheduled_task_button = ttk.Button(scheduled_task_buttons_frame, text="⚡ Attiva/Disattiva", command=toggle_selected_scheduled_task, style='TButton')
    toggle_scheduled_task_button.pack(side="left", padx=5)
    
    stop_scheduled_task_button = ttk.Button(scheduled_task_buttons_frame, text="⏹️ Ferma Task", command=stop_selected_scheduled_task, style='TButton')
    stop_scheduled_task_button.pack(side="left", padx=5)
    
    refresh_scheduled_button = ttk.Button(scheduled_task_buttons_frame, text="🔄 Aggiorna", command=refresh_scheduled_task_list, style='TButton')
    refresh_scheduled_button.pack(side="left", padx=5)
    
    # --- Frame contenitore per lista e countdown (side by side) ---
    content_frame = ttk.Frame(main_frame)
    content_frame.pack(fill="both", expand=True)
    
    # --- Frame per la lista degli scheduled tasks ---
    scheduled_tasks_list_frame = ttk.LabelFrame(content_frame, text="Scheduled Tasks", padding="10")
    scheduled_tasks_list_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
    
    # TreeView per gli scheduled tasks
    columns = ("Nome", "Macro", "Tipo", "Prossima Esecuzione", "Stato", "Ultima Esecuzione")
    scheduled_tasks_list_tree = ttk.Treeview(scheduled_tasks_list_frame, columns=columns, show="headings", height=8)
    
    # Headings
    scheduled_tasks_list_tree.heading("Nome", text="Nome Task")
    scheduled_tasks_list_tree.heading("Macro", text="Macro Assegnata")
    scheduled_tasks_list_tree.heading("Tipo", text="Tipo Schedulazione")
    scheduled_tasks_list_tree.heading("Prossima Esecuzione", text="Prossima Esecuzione")
    scheduled_tasks_list_tree.heading("Stato", text="Stato")
    scheduled_tasks_list_tree.heading("Ultima Esecuzione", text="Ultima Esecuzione")
    
    # Column widths
    scheduled_tasks_list_tree.column("Nome", width=150)
    scheduled_tasks_list_tree.column("Macro", width=150)
    scheduled_tasks_list_tree.column("Tipo", width=120)
    scheduled_tasks_list_tree.column("Prossima Esecuzione", width=180)
    scheduled_tasks_list_tree.column("Stato", width=100)
    scheduled_tasks_list_tree.column("Ultima Esecuzione", width=180)
    
    scheduled_tasks_list_tree.pack(side="left", fill="both", expand=True)
    
    # Scrollbar per la TreeView
    scheduled_tasks_scrollbar = ttk.Scrollbar(scheduled_tasks_list_frame, orient="vertical", command=scheduled_tasks_list_tree.yview)
    scheduled_tasks_scrollbar.pack(side="right", fill="y")
    scheduled_tasks_list_tree.configure(yscrollcommand=scheduled_tasks_scrollbar.set)
    
    # Binding per la selezione
    scheduled_tasks_list_tree.bind("<<TreeviewSelect>>", lambda event: update_scheduled_task_button_states())
    
    # --- Riquadro per i prossimi task con countdown ---
    next_tasks_countdown_frame = ttk.LabelFrame(content_frame, text="⏰ Prossimi Task da Eseguire", padding="10")
    next_tasks_countdown_frame.pack(side="right", fill="both", expand=False, padx=(10, 0))
    next_tasks_countdown_frame.config(width=350)
    
    # Text widget per mostrare i prossimi task con countdown
    next_tasks_countdown_text = scrolledtext.ScrolledText(next_tasks_countdown_frame, 
                                                          wrap=tk.WORD, 
                                                          width=40, 
                                                          height=20,
                                                          font=("Consolas", 9),
                                                          state=tk.DISABLED)
    next_tasks_countdown_text.pack(fill="both", expand=True)
    
    # Inizializza la lista
    refresh_scheduled_task_list()
    
    # Avvia l'aggiornamento del countdown
    update_next_tasks_countdown()

def refresh_scheduled_task_list():
    """Aggiorna la lista degli scheduled tasks"""
    try:
        if scheduled_tasks_list_tree and scheduled_tasks_list_tree.winfo_exists():
            for iid in scheduled_tasks_list_tree.get_children():
                scheduled_tasks_list_tree.delete(iid)
            
            tasks = get_all_scheduled_tasks()
            for task in tasks:
                scheduled_tasks_list_tree.insert("", "end", iid=task['id'], values=build_scheduled_task_row(task))
            
            # Aggiorna anche il countdown
            if next_tasks_countdown_text and next_tasks_countdown_text.winfo_exists():
                update_next_tasks_countdown()
    except Exception as e:
        console_log(f"Errore durante il refresh della lista scheduled tasks: {e}", level="ERROR")

def update_scheduled_task_button_states():
    """Aggiorna lo stato dei pulsanti per gli scheduled tasks"""
    try:
        if not scheduled_tasks_list_tree:
            return
        
        selected_item = scheduled_tasks_list_tree.selection()
        has_selection = bool(selected_item)
        
        # Riferimenti ai pulsanti tramite parent
        buttons_parent = scheduled_tasks_list_tree.master.master
        update_action_buttons_state(buttons_parent, has_selection)
    except Exception as e:
        console_log(f"Errore nell'aggiornamento dei pulsanti scheduled tasks: {e}", level="ERROR")

def format_countdown(seconds):
    """Formatta i secondi in un countdown leggibile (giorni, ore, minuti, secondi)"""
    return format_scheduled_task_countdown(seconds)

def update_next_tasks_countdown():
    """Aggiorna il riquadro con i prossimi task da eseguire e il loro countdown"""
    global next_tasks_countdown_text, countdown_update_job
    
    try:
        if not next_tasks_countdown_text or not next_tasks_countdown_text.winfo_exists():
            return
        
        # Ottieni i task attivi ordinati per prossima esecuzione
        active_tasks = get_active_tasks_ordered_by_next_execution()
        
        # Abilita il text widget per la modifica
        next_tasks_countdown_text.config(state=tk.NORMAL)
        next_tasks_countdown_text.delete(1.0, tk.END)
        
        entries = build_countdown_entries(
            active_tasks,
            get_task_macro_sequence,
            now=datetime.datetime.now(),
            error_callback=lambda task, error: console_log(
                f"Errore nel calcolo del countdown per task {task['nome']}: {error}",
                level="ERROR",
            ),
            runtime_status=task_controller.get_scheduler_runtime_status(),
        )
        for text, tag in entries:
            if tag:
                next_tasks_countdown_text.insert(tk.END, text, tag)
            else:
                next_tasks_countdown_text.insert(tk.END, text)
        
        # Configura i tag per lo styling
        next_tasks_countdown_text.tag_config("task_name", font=("Consolas", 9, "bold"))
        next_tasks_countdown_text.tag_config("countdown", font=("Consolas", 9, "bold"), foreground="blue")
        next_tasks_countdown_text.tag_config("runtime", font=("Consolas", 9, "bold"))
        
        # Disabilita il text widget
        next_tasks_countdown_text.config(state=tk.DISABLED)
        
    except Exception as e:
        console_log(f"Errore durante l'aggiornamento del countdown: {e}", level="ERROR")
    
    # Programma il prossimo aggiornamento dopo 1 secondo
    if root and root.winfo_exists():
        try:
            countdown_update_job = root.after(1000, update_next_tasks_countdown)
        except tk.TclError:
            # La finestra è stata chiusa
            pass

def create_new_scheduled_task_dialog():
    """Dialog per creare un nuovo scheduled task"""
    dialog = tk.Toplevel(root)
    dialog.title("Nuovo Scheduled Task")
    dialog.transient(root)
    dialog.grab_set()
    
    # Carica posizione/dimensione salvata per questa finestra
    dialog.geometry("550x850")
    restore_saved_window_geometry(dialog, "new_scheduled_task_dialog_window", "new scheduled task dialog")
    
    # Salva posizione/dimensione alla chiusura
    def save_dialog_geometry():
        save_window_geometry_config(dialog, "new_scheduled_task_dialog_window", "new scheduled task dialog")
    
    def on_dialog_close():
        save_dialog_geometry()
        dialog.destroy()
    
    dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)
    
    # Applica lo stesso stile della finestra principale al dialog
    apply_dialog_styles(dialog)
    
    # Variabili
    nome_var = tk.StringVar()
    descrizione_var = tk.StringVar()
    macro_id_var = tk.StringVar()
    schedulazione_tipo_var = tk.StringVar(value="ora_fissa")
    ora_target_var = tk.StringVar()
    intervallo_ore_var = tk.StringVar(value="0")
    intervallo_minuti_var = tk.StringVar(value="0")
    
    # Nome task
    ttk.Label(dialog, text="Nome Task:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    nome_entry = ttk.Entry(dialog, textvariable=nome_var, width=40)
    nome_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
    # Descrizione
    ttk.Label(dialog, text="Descrizione:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
    descrizione_entry = ttk.Entry(dialog, textvariable=descrizione_var, width=40)
    descrizione_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
    
    # Macro da associare - ComboBox
    ttk.Label(dialog, text="Macro principale:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
    macro_options = []
    for macro in get_all_macros():
        macro_options.append(f"{macro['id']} - {macro['nome']} ({macro['eseguibile']})")
    
    macro_combobox = ttk.Combobox(dialog, values=macro_options, textvariable=macro_id_var, width=37, state="readonly")
    macro_combobox.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
    
    # Sezione Sequenza Macro (per macro aggiuntive)
    sequence_frame = ttk.LabelFrame(dialog, text="Sequenza Macro Aggiuntive (opzionale)")
    sequence_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
    
    # TreeView per la sequenza
    sequence_tree_frame = ttk.Frame(sequence_frame)
    sequence_tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
    
    sequence_tree = ttk.Treeview(sequence_tree_frame, columns=("Macro", "Attesa"), show="headings", height=4)
    sequence_tree.heading("Macro", text="Macro")
    sequence_tree.heading("Attesa", text="Attesa (sec)")
    sequence_tree.column("Macro", width=250)
    sequence_tree.column("Attesa", width=100)
    sequence_tree.pack(side="left", fill="both", expand=True)
    
    sequence_scrollbar = ttk.Scrollbar(sequence_tree_frame, orient="vertical", command=sequence_tree.yview)
    sequence_scrollbar.pack(side="right", fill="y")
    sequence_tree.configure(yscrollcommand=sequence_scrollbar.set)
    
    # Frame per i pulsanti della sequenza
    sequence_buttons_frame = ttk.Frame(sequence_frame)
    sequence_buttons_frame.pack(fill="x", padx=5, pady=5)
    
    def add_macro_to_sequence():
        """Aggiunge una macro alla sequenza"""
        add_dialog = tk.Toplevel(dialog)
        add_dialog.title("Aggiungi Macro alla Sequenza")
        add_dialog.transient(dialog)
        add_dialog.grab_set()
        add_dialog.geometry("400x150")
        apply_dialog_styles(add_dialog)
        
        ttk.Label(add_dialog, text="Macro:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        macro_options_add = []
        for macro in get_all_macros():
            macro_options_add.append(f"{macro['id']} - {macro['nome']} ({macro['eseguibile']})")
        
        macro_combobox_add = ttk.Combobox(add_dialog, values=macro_options_add, width=40, state="readonly")
        macro_combobox_add.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(add_dialog, text="Attesa (secondi):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        attesa_var = tk.StringVar(value="0")
        attesa_entry = ttk.Entry(add_dialog, textvariable=attesa_var, width=10)
        attesa_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        def confirm_add():
            if not macro_combobox_add.get():
                messagebox.showwarning("Input Errato", "Seleziona una macro.", parent=add_dialog)
                return
            try:
                macro_id = int(macro_combobox_add.get().split(" - ")[0])
                macro_name = macro_combobox_add.get().split(" - ")[1].split(" (")[0]
                attesa = int(attesa_var.get() or "0")
                if attesa < 0:
                    messagebox.showwarning("Input Errato", "L'attesa non può essere negativa.", parent=add_dialog)
                    return
                sequence_tree.insert("", "end", values=(f"{macro_id} - {macro_name}", str(attesa)), tags=(macro_id,))
                add_dialog.destroy()
            except (ValueError, IndexError):
                messagebox.showwarning("Input Errato", "Valori non validi.", parent=add_dialog)
        
        ttk.Button(add_dialog, text="Aggiungi", command=confirm_add).grid(row=2, column=0, columnspan=2, pady=10)
    
    def remove_macro_from_sequence():
        """Rimuove una macro dalla sequenza"""
        selected = sequence_tree.selection()
        if selected:
            sequence_tree.delete(selected)
        else:
            messagebox.showwarning("Rimozione", "Seleziona una macro da rimuovere.", parent=dialog)
    
    ttk.Button(sequence_buttons_frame, text="➕ Aggiungi Macro", command=add_macro_to_sequence).pack(side="left", padx=5)
    ttk.Button(sequence_buttons_frame, text="➖ Rimuovi Macro", command=remove_macro_from_sequence).pack(side="left", padx=5)
    
    # Tipo di schedulazione
    ttk.Label(dialog, text="Tipo di schedulazione:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
    schedulazione_frame = ttk.Frame(dialog)
    schedulazione_frame.grid(row=4, column=1, sticky="ew", padx=5, pady=5)
    
    ora_fissa_radio = ttk.Radiobutton(schedulazione_frame, text="Ora fissa", variable=schedulazione_tipo_var, value="ora_fissa")
    ora_fissa_radio.pack(side="left")
    intervallo_radio = ttk.Radiobutton(schedulazione_frame, text="Intervallo", variable=schedulazione_tipo_var, value="intervallo")
    intervallo_radio.pack(side="left", padx=(10, 0))
    
    # Sezione ora fissa
    time_frame = ttk.LabelFrame(dialog, text="Ora Fissa")
    time_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
    
    ttk.Label(time_frame, text="Orario (HH:MM):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    ora_entry = ttk.Entry(time_frame, textvariable=ora_target_var, width=10)
    ora_entry.grid(row=0, column=1, padx=5, pady=5)
    
    # Sezione intervallo
    interval_frame = ttk.LabelFrame(dialog, text="Intervallo")
    interval_frame.grid(row=6, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
    
    ttk.Label(interval_frame, text="Ogni ore:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(interval_frame, textvariable=intervallo_ore_var, width=10).grid(row=0, column=1, padx=5, pady=5)
    
    ttk.Label(interval_frame, text="Ogni minuti:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(interval_frame, textvariable=intervallo_minuti_var, width=10).grid(row=1, column=1, padx=5, pady=5)
    
    # Sezione Termina Schedulazione
    termination_frame = ttk.LabelFrame(dialog, text="Termina Schedulazione")
    termination_frame.grid(row=7, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
    
    terminazione_tipo_var = tk.StringVar(value="nessuna")
    terminazione_valore_var = tk.StringVar(value="")
    
    ttk.Radiobutton(termination_frame, text="Nessuna terminazione", variable=terminazione_tipo_var, value="nessuna").grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)
    ttk.Radiobutton(termination_frame, text="Dopo numero di esecuzioni:", variable=terminazione_tipo_var, value="esecuzioni").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(termination_frame, textvariable=terminazione_valore_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")
    ttk.Label(termination_frame, text="esecuzioni").grid(row=1, column=2, sticky="w", padx=5)
    
    ttk.Radiobutton(termination_frame, text="Dopo durata (ore):", variable=terminazione_tipo_var, value="durata_ore").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(termination_frame, textvariable=terminazione_valore_var, width=10).grid(row=2, column=1, padx=5, pady=5, sticky="w")
    ttk.Label(termination_frame, text="ore").grid(row=2, column=2, sticky="w", padx=5)
    
    ttk.Radiobutton(termination_frame, text="Dopo durata (minuti):", variable=terminazione_tipo_var, value="durata_minuti").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(termination_frame, textvariable=terminazione_valore_var, width=10).grid(row=3, column=1, padx=5, pady=5, sticky="w")
    ttk.Label(termination_frame, text="minuti").grid(row=3, column=2, sticky="w", padx=5)
    
    def validate_and_create():
        nome = nome_var.get().strip()
        descrizione = descrizione_var.get().strip()
        
        if not nome:
            messagebox.showwarning("Input Errato", "Il nome del task non può essere vuoto.", parent=dialog)
            return
        
        # Usa la variabile invece del metodo get() diretto per garantire la persistenza del valore
        macro_selection = macro_id_var.get()
        if not macro_selection:
            messagebox.showwarning("Input Errato", "Seleziona una macro da eseguire.", parent=dialog)
            return
        
        # Estrai macro_id dalla stringa selezionata
        try:
            macro_id = int(macro_selection.split(" - ")[0])
        except (ValueError, IndexError):
            messagebox.showwarning("Input Errato", "Selezione macro non valida.", parent=dialog)
            return
        
        schedulazione_tipo = schedulazione_tipo_var.get()
        terminazione_tipo = terminazione_tipo_var.get()
        terminazione_valore = None
        
        # Valida terminazione
        if terminazione_tipo != "nessuna":
            try:
                terminazione_valore = int(terminazione_valore_var.get().strip())
                if terminazione_valore <= 0:
                    messagebox.showwarning("Input Errato", "Il valore di terminazione deve essere positivo.", parent=dialog)
                    return
            except ValueError:
                messagebox.showwarning("Input Errato", "Il valore di terminazione deve essere un numero intero.", parent=dialog)
                return
        
        try:
            if schedulazione_tipo == "ora_fissa":
                ora_target = ora_target_var.get().strip()
                if not ora_target:
                    messagebox.showwarning("Input Errato", "Per ora fissa devi specificare l'orario.", parent=dialog)
                    return
                # Valida formato ora
                import datetime
                datetime.datetime.strptime(ora_target, "%H:%M")
                
                task_id = create_scheduled_task(
                    nome=nome, descrizione=descrizione, macro_id=macro_id,
                    schedulazione_tipo=schedulazione_tipo, ora_target=ora_target,
                    terminazione_tipo=terminazione_tipo, terminazione_valore=terminazione_valore
                )
            else:
                intervallo_ore = int(intervallo_ore_var.get() or "0")
                intervallo_minuti = int(intervallo_minuti_var.get() or "0")
                
                if intervallo_ore == 0 and intervallo_minuti == 0:
                    messagebox.showwarning("Input Errato", "Per intervalli devi specificare almeno ore o minuti.", parent=dialog)
                    return
                
                task_id = create_scheduled_task(
                    nome=nome, descrizione=descrizione, macro_id=macro_id,
                    schedulazione_tipo=schedulazione_tipo,
                    intervallo_ore=intervallo_ore if intervallo_ore > 0 else None,
                    intervallo_minuti=intervallo_minuti if intervallo_minuti > 0 else None,
                    terminazione_tipo=terminazione_tipo, terminazione_valore=terminazione_valore
                )
            
            # Aggiungi la macro principale come prima nella sequenza (ordine 0)
            # Prima rimuovi eventuali sequenze esistenti per questo task
            clear_task_macro_sequence(task_id)
            # Aggiungi la macro principale con ordine 0
            add_macro_to_task_sequence_with_order(task_id, macro_id, 0, 0)
            
            # Aggiungi le macro aggiuntive della sequenza (se presenti) con ordine incrementale
            ordine_counter = 1
            for item in sequence_tree.get_children():
                values = sequence_tree.item(item, "values")
                if values and len(values) >= 2:
                    try:
                        macro_id_seq = int(values[0].split(" - ")[0])
                        # Evita di aggiungere la macro principale di nuovo se è già nella sequenza
                        if macro_id_seq != macro_id:
                            attesa_secondi = int(values[1] or "0")
                            add_macro_to_task_sequence_with_order(task_id, macro_id_seq, ordine_counter, attesa_secondi)
                            ordine_counter += 1
                    except (ValueError, IndexError) as e:
                        console_log(f"⚠️ Errore nell'aggiunta della macro alla sequenza: {e}", level="WARNING")
            
            console_log(f"✅ Scheduled task '{nome}' creato con successo (ID: {task_id}).")
            save_dialog_geometry()  # Salva la geometria prima di chiudere
            dialog.destroy()
            refresh_scheduled_task_list()
            
        except ValueError as e:
            messagebox.showerror("Errore Creazione", f"Errore: {e}", parent=dialog)
        except Exception as e:
            messagebox.showerror("Errore Creazione", f"Errore generico: {e}", parent=dialog)
    
    ttk.Button(dialog, text="Crea Task", command=validate_and_create).grid(row=8, column=0, columnspan=2, pady=10)
    
    # Configure grid weights
    dialog.columnconfigure(1, weight=1)
    time_frame.columnconfigure(1, weight=1)
    interval_frame.columnconfigure(1, weight=1)
    termination_frame.columnconfigure(1, weight=1)

def edit_selected_scheduled_task():
    """Modifica il scheduled task selezionato"""
    try:
        if not scheduled_tasks_list_tree:
            return
        
        selected_item = scheduled_tasks_list_tree.selection()
        if not selected_item:
            messagebox.showwarning("Modifica Task", "Seleziona un task da modificare.")
            return
        
        task_id = int(selected_item[0])
        task_data = get_scheduled_task_by_id(task_id)
        
        if not task_data:
            messagebox.showerror("Errore Modifica", "Task non trovato.")
            return
        
        # Creazione dialog di modifica (simile a create ma con valori precompilati)
        dialog = tk.Toplevel(root)
        dialog.title(f"Modifica Task: {task_data['nome']}")
        dialog.transient(root)
        dialog.grab_set()
        
        # Carica posizione/dimensione salvata per questa finestra
        dialog.geometry("500x700")
        restore_saved_window_geometry(dialog, "edit_scheduled_task_dialog_window", "edit scheduled task dialog")
        
        # Salva posizione/dimensione alla chiusura
        def save_dialog_geometry():
            save_window_geometry_config(dialog, "edit_scheduled_task_dialog_window", "edit scheduled task dialog")
        
        def on_dialog_close():
            save_dialog_geometry()
            dialog.destroy()
        
        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)
        
        # Applica lo stesso stile della finestra principale al dialog
        apply_dialog_styles(dialog)
        
        # Variabili precompilate
        nome_var = tk.StringVar(value=task_data['nome'])
        descrizione_var = tk.StringVar(value=task_data['descrizione'] or "")
        macro_id_var = tk.StringVar()
        schedulazione_tipo_var = tk.StringVar(value=task_data['schedulazione_tipo'])
        ora_target_var = tk.StringVar(value=task_data['ora_target'] or "")
        intervallo_ore_var = tk.StringVar(value=str(task_data['intervallo_ore'] or 0))
        intervallo_minuti_var = tk.StringVar(value=str(task_data['intervallo_minuti'] or 0))
        
        # Layout come nel dialog di creazione...
        ttk.Label(dialog, text="Nome Task:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        nome_entry = ttk.Entry(dialog, textvariable=nome_var, width=40)
        nome_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(dialog, text="Descrizione:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        descrizione_entry = ttk.Entry(dialog, textvariable=descrizione_var, width=40)
        descrizione_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        # Macro selection (con quella selezionata)
        ttk.Label(dialog, text="Macro principale:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        macro_options = []
        current_macro_idx = 0
        macro_id_current = task_data['macro_id']
        current_macro_str = None
        
        for i, macro in enumerate(get_all_macros()):
            macro_str = f"{macro['id']} - {macro['nome']} ({macro['eseguibile']})"
            macro_options.append(macro_str)
            if macro['id'] == macro_id_current:
                current_macro_idx = i
                current_macro_str = macro_str
        
        # Imposta il valore nella variabile prima di creare il combobox
        if current_macro_str:
            macro_id_var.set(current_macro_str)
        
        macro_combobox = ttk.Combobox(dialog, values=macro_options, textvariable=macro_id_var, width=37, state="readonly")
        macro_combobox.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        macro_combobox.current(current_macro_idx)
        
        # Sezione Sequenza Macro (per macro aggiuntive)
        sequence_frame = ttk.LabelFrame(dialog, text="Sequenza Macro Aggiuntive (opzionale)")
        sequence_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        # TreeView per la sequenza
        sequence_tree_frame = ttk.Frame(sequence_frame)
        sequence_tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        sequence_tree = ttk.Treeview(sequence_tree_frame, columns=("Macro", "Attesa"), show="headings", height=4)
        sequence_tree.heading("Macro", text="Macro")
        sequence_tree.heading("Attesa", text="Attesa (sec)")
        sequence_tree.column("Macro", width=250)
        sequence_tree.column("Attesa", width=100)
        sequence_tree.pack(side="left", fill="both", expand=True)
        
        sequence_scrollbar = ttk.Scrollbar(sequence_tree_frame, orient="vertical", command=sequence_tree.yview)
        sequence_scrollbar.pack(side="right", fill="y")
        sequence_tree.configure(yscrollcommand=sequence_scrollbar.set)
        
        # Carica sequenze esistenti (escludendo la macro principale che è già nel combobox)
        existing_sequence = get_task_macro_sequence(task_id)
        for seq_item in existing_sequence:
            # Escludi la macro principale (ordine 0) dalla sequenza mostrata, perché è già nel combobox
            if seq_item.get('ordine', 0) > 0:
                macro_name = seq_item.get('macro_nome', f"ID:{seq_item['macro_id']}")
                sequence_tree.insert("", "end", values=(f"{seq_item['macro_id']} - {macro_name}", str(seq_item['attesa_secondi'])), tags=(seq_item['macro_id'],))
        
        # Frame per i pulsanti della sequenza
        sequence_buttons_frame = ttk.Frame(sequence_frame)
        sequence_buttons_frame.pack(fill="x", padx=5, pady=5)
        
        def add_macro_to_sequence():
            """Aggiunge una macro alla sequenza"""
            add_dialog = tk.Toplevel(dialog)
            add_dialog.title("Aggiungi Macro alla Sequenza")
            add_dialog.transient(dialog)
            add_dialog.grab_set()
            add_dialog.geometry("400x150")
            apply_dialog_styles(add_dialog)
            
            ttk.Label(add_dialog, text="Macro:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
            macro_options_add = []
            for macro in get_all_macros():
                macro_options_add.append(f"{macro['id']} - {macro['nome']} ({macro['eseguibile']})")
            
            macro_combobox_add = ttk.Combobox(add_dialog, values=macro_options_add, width=40, state="readonly")
            macro_combobox_add.grid(row=0, column=1, padx=5, pady=5)
            
            ttk.Label(add_dialog, text="Attesa (secondi):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
            attesa_var = tk.StringVar(value="0")
            attesa_entry = ttk.Entry(add_dialog, textvariable=attesa_var, width=10)
            attesa_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
            
            def confirm_add():
                if not macro_combobox_add.get():
                    messagebox.showwarning("Input Errato", "Seleziona una macro.", parent=add_dialog)
                    return
                try:
                    macro_id = int(macro_combobox_add.get().split(" - ")[0])
                    macro_name = macro_combobox_add.get().split(" - ")[1].split(" (")[0]
                    attesa = int(attesa_var.get() or "0")
                    if attesa < 0:
                        messagebox.showwarning("Input Errato", "L'attesa non può essere negativa.", parent=add_dialog)
                        return
                    sequence_tree.insert("", "end", values=(f"{macro_id} - {macro_name}", str(attesa)), tags=(macro_id,))
                    add_dialog.destroy()
                except (ValueError, IndexError):
                    messagebox.showwarning("Input Errato", "Valori non validi.", parent=add_dialog)
            
            ttk.Button(add_dialog, text="Aggiungi", command=confirm_add).grid(row=2, column=0, columnspan=2, pady=10)
        
        def remove_macro_from_sequence():
            """Rimuove una macro dalla sequenza"""
            selected = sequence_tree.selection()
            if selected:
                sequence_tree.delete(selected)
            else:
                messagebox.showwarning("Rimozione", "Seleziona una macro da rimuovere.", parent=dialog)
        
        ttk.Button(sequence_buttons_frame, text="➕ Aggiungi Macro", command=add_macro_to_sequence).pack(side="left", padx=5)
        ttk.Button(sequence_buttons_frame, text="➖ Rimuovi Macro", command=remove_macro_from_sequence).pack(side="left", padx=5)
        
        # Layout per scheduler
        ttk.Label(dialog, text="Tipo di schedulazione:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        schedulazione_frame = ttk.Frame(dialog)
        schedulazione_frame.grid(row=4, column=1, sticky="ew", padx=5, pady=5)
        
        ora_fissa_radio = ttk.Radiobutton(schedulazione_frame, text="Ora fissa", variable=schedulazione_tipo_var, value="ora_fissa")
        ora_fissa_radio.pack(side="left")
        intervallo_radio = ttk.Radiobutton(schedulazione_frame, text="Intervallo", variable=schedulazione_tipo_var, value="intervallo")
        intervallo_radio.pack(side="left", padx=(10, 0))
        
        time_frame = ttk.LabelFrame(dialog, text="Ora Fissa")
        time_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        ttk.Label(time_frame, text="Orario (HH:MM):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ora_entry = ttk.Entry(time_frame, textvariable=ora_target_var, width=10)
        ora_entry.grid(row=0, column=1, padx=5, pady=5)
        
        interval_frame = ttk.LabelFrame(dialog, text="Intervallo")
        interval_frame.grid(row=6, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        ttk.Label(interval_frame, text="Ogni ore:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(interval_frame, textvariable=intervallo_ore_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(interval_frame, text="Ogni minuti:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(interval_frame, textvariable=intervallo_minuti_var, width=10).grid(row=1, column=1, padx=5, pady=5)
        
        # Sezione Termina Schedulazione
        termination_frame = ttk.LabelFrame(dialog, text="Termina Schedulazione")
        termination_frame.grid(row=7, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        terminazione_tipo_var = tk.StringVar(value=task_data.get('terminazione_tipo', 'nessuna'))
        terminazione_valore_var = tk.StringVar(value=str(task_data.get('terminazione_valore') or ""))
        
        ttk.Radiobutton(termination_frame, text="Nessuna terminazione", variable=terminazione_tipo_var, value="nessuna").grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        ttk.Radiobutton(termination_frame, text="Dopo numero di esecuzioni:", variable=terminazione_tipo_var, value="esecuzioni").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(termination_frame, textvariable=terminazione_valore_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(termination_frame, text="esecuzioni").grid(row=1, column=2, sticky="w", padx=5)
        
        ttk.Radiobutton(termination_frame, text="Dopo durata (ore):", variable=terminazione_tipo_var, value="durata_ore").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(termination_frame, textvariable=terminazione_valore_var, width=10).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(termination_frame, text="ore").grid(row=2, column=2, sticky="w", padx=5)
        
        ttk.Radiobutton(termination_frame, text="Dopo durata (minuti):", variable=terminazione_tipo_var, value="durata_minuti").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(termination_frame, textvariable=terminazione_valore_var, width=10).grid(row=3, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(termination_frame, text="minuti").grid(row=3, column=2, sticky="w", padx=5)
        
        def validate_and_update():
            nome = nome_var.get().strip()
            descrizione = descrizione_var.get().strip()
            
            if not nome:
                messagebox.showwarning("Input Errato", "Il nome del task non può essere vuoto.", parent=dialog)
                return
            
            # Usa la variabile invece del metodo get() diretto per garantire la persistenza del valore
            macro_selection = macro_id_var.get()
            if not macro_selection:
                messagebox.showwarning("Input Errato", "Seleziona una macro da eseguire.", parent=dialog)
                return
            
            try:
                macro_id = int(macro_selection.split(" - ")[0])
            except (ValueError, IndexError):
                messagebox.showwarning("Input Errato", "Selezione macro non valida.", parent=dialog)
                return
            
            schedulazione_tipo = schedulazione_tipo_var.get()
            terminazione_tipo = terminazione_tipo_var.get()
            terminazione_valore = None
            
            # Valida terminazione
            if terminazione_tipo != "nessuna":
                try:
                    terminazione_valore = int(terminazione_valore_var.get().strip())
                    if terminazione_valore <= 0:
                        messagebox.showwarning("Input Errato", "Il valore di terminazione deve essere positivo.", parent=dialog)
                        return
                except ValueError:
                    messagebox.showwarning("Input Errato", "Il valore di terminazione deve essere un numero intero.", parent=dialog)
                    return
            
            try:
                if schedulazione_tipo == "ora_fissa":
                    ora_target = ora_target_var.get().strip()
                    if not ora_target:
                        messagebox.showwarning("Input Errato", "Per ora fissa devi specificare l'orario.", parent=dialog)
                        return
                    
                    import datetime
                    datetime.datetime.strptime(ora_target, "%H:%M")
                    
                    update_scheduled_task(
                        task_id=task_id, nome=nome, descrizione=descrizione, macro_id=macro_id,
                        schedulazione_tipo=schedulazione_tipo, ora_target=ora_target,
                        terminazione_tipo=terminazione_tipo, terminazione_valore=terminazione_valore
                    )
                else:
                    intervallo_ore = int(intervallo_ore_var.get() or "0")
                    intervallo_minuti = int(intervallo_minuti_var.get() or "0")
                    
                    if intervallo_ore == 0 and intervallo_minuti == 0:
                        messagebox.showwarning("Input Errato", "Per intervalli devi specificare almeno ore o minuti.", parent=dialog)
                        return
                    
                    update_scheduled_task(
                        task_id=task_id, nome=nome, descrizione=descrizione, macro_id=macro_id,
                        schedulazione_tipo=schedulazione_tipo,
                        intervallo_ore=intervallo_ore if intervallo_ore > 0 else None,
                        intervallo_minuti=intervallo_minuti if intervallo_minuti > 0 else None,
                        terminazione_tipo=terminazione_tipo, terminazione_valore=terminazione_valore
                    )
                
                # Aggiorna la sequenza: prima rimuovi tutte le macro esistenti, poi aggiungi quelle nuove
                clear_task_macro_sequence(task_id)
                # Aggiungi la macro principale come prima nella sequenza (ordine 0)
                add_macro_to_task_sequence_with_order(task_id, macro_id, 0, 0)
                
                # Aggiungi le macro aggiuntive della sequenza (se presenti) con ordine incrementale
                ordine_counter = 1
                for item in sequence_tree.get_children():
                    values = sequence_tree.item(item, "values")
                    if values and len(values) >= 2:
                        try:
                            macro_id_seq = int(values[0].split(" - ")[0])
                            # Evita di aggiungere la macro principale di nuovo se è già nella sequenza
                            if macro_id_seq != macro_id:
                                attesa_secondi = int(values[1] or "0")
                                add_macro_to_task_sequence_with_order(task_id, macro_id_seq, ordine_counter, attesa_secondi)
                                ordine_counter += 1
                        except (ValueError, IndexError) as e:
                            console_log(f"⚠️ Errore nell'aggiunta della macro alla sequenza: {e}", level="WARNING")
                
                console_log(f"✅ Task '{nome}' aggiornato con successo.")
                save_dialog_geometry()  # Salva la geometria prima di chiudere
                dialog.destroy()
                refresh_scheduled_task_list()
                
            except ValueError as e:
                messagebox.showerror("Errore Modifica", f"Errore: {e}", parent=dialog)
            except Exception as e:
                messagebox.showerror("Errore Modifica", f"Errore generico: {e}", parent=dialog)
        
        # Frame per i pulsanti di azione
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.grid(row=8, column=0, columnspan=2, pady=10)
        
        def test_task_execution():
            """Avvia il test di esecuzione del task con countdown di 10 secondi"""
            # Crea una finestra di countdown
            countdown_window = tk.Toplevel(dialog)
            countdown_window.title("Test Esecuzione Task")
            countdown_window.transient(dialog)
            countdown_window.grab_set()
            countdown_window.geometry("400x200")
            countdown_window.resizable(False, False)
            
            # Centra la finestra
            countdown_window.update_idletasks()
            x = (countdown_window.winfo_screenwidth() // 2) - (countdown_window.winfo_width() // 2)
            y = (countdown_window.winfo_screenheight() // 2) - (countdown_window.winfo_height() // 2)
            countdown_window.geometry(f"+{x}+{y}")
            
            # Label principale
            main_label = ttk.Label(countdown_window, text="Test Esecuzione Task", font=("Arial", 14, "bold"))
            main_label.pack(pady=20)
            
            # Label per il countdown
            countdown_label = ttk.Label(countdown_window, text="10", font=("Arial", 48, "bold"), foreground="red")
            countdown_label.pack(pady=20)
            
            # Label informativa
            info_label = ttk.Label(countdown_window, text="L'esecuzione inizierà tra:", font=("Arial", 10))
            info_label.pack()
            
            # Variabile per controllare se il countdown è stato annullato
            countdown_cancelled = [False]
            countdown_remaining = [10]
            
            # Bottone per annullare
            def cancel_countdown():
                countdown_cancelled[0] = True
                countdown_window.destroy()
            
            cancel_button = ttk.Button(countdown_window, text="Annulla", command=cancel_countdown)
            cancel_button.pack(pady=10)
            
            # Funzione ricorsiva per il countdown usando after
            def update_countdown():
                if countdown_cancelled[0]:
                    return
                
                if countdown_remaining[0] > 0:
                    countdown_label.config(text=str(countdown_remaining[0]), foreground="red")
                    countdown_remaining[0] -= 1
                    countdown_window.after(1000, update_countdown)  # Richiama dopo 1 secondo
                else:
                    # Countdown terminato, mostra "AVVIO!"
                    countdown_label.config(text="AVVIO!", foreground="green")
                    countdown_window.update()
                    
                    # Chiudi la finestra e avvia il test dopo 1 secondo
                    def start_test_after_delay():
                        if not countdown_cancelled[0]:
                            countdown_window.destroy()
                            # Avvia il test in un thread separato
                            def start_test():
                                try:
                                    test_execute_scheduled_task(
                                        task_data,
                                        log_callback=console_log
                                    )
                                except Exception as e:
                                    console_log(f"❌ Errore nell'avvio del test: {e}", level="ERROR")
                            
                            import threading
                            test_thread = threading.Thread(target=start_test, daemon=True)
                            test_thread.start()
                    
                    countdown_window.after(1000, start_test_after_delay)
            
            # Avvia il countdown
            update_countdown()
        
        # Bottone Test Esecuzione
        test_button = ttk.Button(buttons_frame, text="🧪 Test Esecuzione", command=test_task_execution)
        test_button.pack(side="left", padx=5)
        
        # Bottone Salva Modifiche
        ttk.Button(buttons_frame, text="Salva Modifiche", command=validate_and_update).pack(side="left", padx=5)
        dialog.columnconfigure(1, weight=1)
        time_frame.columnconfigure(1, weight=1)
        interval_frame.columnconfigure(1, weight=1)
        termination_frame.columnconfigure(1, weight=1)
        
    except Exception as e:
        console_log(f"Errore nel modifica del scheduled task: {e}", level="ERROR")

def delete_selected_scheduled_task():
    """Elimina il scheduled task selezionato"""
    try:
        if not scheduled_tasks_list_tree:
            return
        
        selected_item = scheduled_tasks_list_tree.selection()
        if not selected_item:
            messagebox.showwarning("Elimina Task", "Seleziona un task da eliminare.")
            return
        
        task_id = int(selected_item[0])
        task_data = get_scheduled_task_by_id(task_id)
        
        if not task_data:
            messagebox.showerror("Errore Eliminazione", "Task non trovato.")
            return
        
        result = messagebox.askyesno(
            "Conferma Eliminazione",
            f"Sei sicuro di voler eliminare il task '{task_data['nome']}'?\nQuesta azione non può essere annullata.",
            parent=root
        )
        
        if result:
            delete_scheduled_task(task_id)
            console_log(f"✅ Task '{task_data['nome']}' eliminato con successo.")
            refresh_scheduled_task_list()
            
    except Exception as e:
        console_log(f"Errore nell'eliminazione del scheduled task: {e}", level="ERROR")
        messagebox.showerror("Errore Eliminazione", f"Errore nell'eliminazione del task: {e}", parent=root)

def duplicate_selected_scheduled_task():
    """Duplica il scheduled task selezionato"""
    try:
        if not scheduled_tasks_list_tree:
            return
        
        selected_item = scheduled_tasks_list_tree.selection()
        if not selected_item:
            console_log("⚠️ Seleziona un task da duplicare.", level="WARNING")
            return
        
        task_id = int(selected_item[0])
        task_data = get_scheduled_task_by_id(task_id)
        
        if not task_data:
            console_log("❌ Task non trovato.", level="ERROR")
            return
        
        new_task_id, new_task_name = duplicate_scheduled_task(task_id)
        console_log(f"✅ Task duplicato con successo come '{new_task_name}' (ID: {new_task_id}).")
        refresh_scheduled_task_list()
        
    except Exception as e:
        console_log(f"Errore nella duplicazione del scheduled task: {e}", level="ERROR")

def toggle_selected_scheduled_task():
    """Attiva/disattiva il scheduled task selezionato"""
    try:
        if not scheduled_tasks_list_tree:
            return
        
        selected_item = scheduled_tasks_list_tree.selection()
        if not selected_item:
            console_log("⚠️ Seleziona un task da attivare/disattivare.", level="WARNING")
            return
        
        task_id = int(selected_item[0])
        task_data = get_scheduled_task_by_id(task_id)
        
        if not task_data:
            console_log("❌ Task non trovato.", level="ERROR")
            return
        
        # Se il task è completato, riattivalo
        if task_data.get('stato') == 'completed':
            reactivate_completed_task(task_id)
            console_log(f"✅ Task '{task_data['nome']}' riattivato con successo.")
            refresh_scheduled_task_list()
            return
        
        new_status = not task_data['attivo']
        update_scheduled_task(task_id=task_id, attivo=new_status)
        
        # Se si attiva, avvia la schedulazione
        if new_status and task_data.get('stato') != 'running':
            start_task_scheduling(task_id)
            console_log(f"✅ Task '{task_data['nome']}' attivato e schedulazione avviata.")
        elif not new_status and task_data.get('stato') == 'running':
            stop_task_scheduling(task_id)
            console_log(f"✅ Task '{task_data['nome']}' disattivato e schedulazione fermata.")
        else:
            status_text = "attivato" if new_status else "disattivato"
            console_log(f"✅ Task '{task_data['nome']}' {status_text} con successo.")
        
        refresh_scheduled_task_list()
        
    except Exception as e:
        console_log(f"Errore nel toggle del scheduled task: {e}", level="ERROR")

def stop_selected_scheduled_task():
    """Ferma manualmente la schedulazione del task selezionato"""
    try:
        if not scheduled_tasks_list_tree:
            return
        
        selected_item = scheduled_tasks_list_tree.selection()
        if not selected_item:
            console_log("⚠️ Seleziona un task da fermare.", level="WARNING")
            return
        
        task_id = int(selected_item[0])
        task_data = get_scheduled_task_by_id(task_id)
        
        if not task_data:
            console_log("❌ Task non trovato.", level="ERROR")
            return
        
        if task_data.get('stato') != 'running':
            console_log(f"⚠️ Il task '{task_data['nome']}' non è in esecuzione.", level="WARNING")
            return
        
        stop_task_scheduling(task_id)
        console_log(f"✅ Schedulazione del task '{task_data['nome']}' fermata manualmente.")
        refresh_scheduled_task_list()
        
    except Exception as e:
        console_log(f"Errore nel fermare il scheduled task: {e}", level="ERROR")


def reset_scheduled_task_status(task_id):
    """Aiuta a disabilitare o fare reset dello stato degli scheduled tasks"""
    try:
        # Questa funzione può essere espansa per gestire il cleanup quando si elimina un task
        console_log(f"Reset dello stato per task {task_id}")
        pass
    except Exception as e:
        console_log(f"Errore nel reset dello stato del task: {e}", level="ERROR")



# --- Setup GUI ---

def save_window_geometry():
    if root is None:
        return
    try:
        geom = root.geometry()  # es: '1200x800+100+100'
        width_height, x_y = geom.split('+', 1)
        width, height = width_height.split('x')
        x, y = x_y.split('+')
        set_window_geometry(
            "macro_manager_window",
            x=int(x),
            y=int(y),
            width=int(width),
            height=int(height),
        )
        logger.info("Salvata posizione/dimensione macro manager")
    except Exception as e:
        logger.error(f"Errore salvataggio posizione/dimensione macro manager: {e}")

def load_window_geometry():
    restore_saved_window_geometry(root, "macro_manager_window", "macro manager")


def get_panel_visibility_state():
    config_data = load_app_config()
    return config_data.get(
        "panel_visibility",
        {
            "macro_actions": True,
            "macro_details": True,
            "macro_live_control": True,
            "macro_list": True,
            "macro_execution": True,
            "console": True,
        },
    )


def save_panel_visibility(panel_key, expanded):
    config_data = load_app_config()
    panel_visibility = dict(config_data.get("panel_visibility", {}))
    panel_visibility[panel_key] = bool(expanded)
    config_data["panel_visibility"] = panel_visibility
    save_app_config(config_data)


def toggle_collapsible_section(panel_key, section):
    section.toggle()
    save_panel_visibility(panel_key, section._expanded)

def setup_gui():
    logger.info("Setup GUI Macro Manager")
    global root, macro_list_tree, console_text, status_bar
    # CORREZIONE: Aggiunto record_button alla dichiarazione global
    global new_macro_button, record_button, play_button, stop_button, emergency_stop_button, edit_button, delete_button, duplicate_button, concat_button
    global loop_var, loop_delay_entry, max_repetitions_entry, loop_var_checkbox, recording_indicator_button, playing_indicator_button, focus_monitor_indicator, macro_details_text
    global recording_timer_label

    single_instance_state = enforce_single_macro_manager_instance()
    if not single_instance_state["keep_current"]:
        logger.info(
            "Istanza secondaria rilevata, chiusura immediata. Duplicati presenti: %s",
            single_instance_state["duplicate_pids"],
        )
        sys.exit(0)

    root = tk.Tk()
    load_config() # Carica la configurazione prima di applicare gli stili
    if single_instance_state["closed_pids"]:
        logger.info("Chiuse istanze duplicate del Macro Manager: %s", single_instance_state["closed_pids"])
    
    # Applica il stile selezionato al riavvio
    apply_window_styles(root)
    
    root.title(config['macro_manager']['window_title'])
    root.geometry("1000x700") # Dimensione iniziale della finestra
    load_window_geometry()  # <--- ripristina posizione/dimensione se presenti

    # Applica stili dalla configurazione
    bg_color = config['theme']['background_color']
    text_color = config['theme']['text_color']
    button_bg = config['theme']['button_bg_color']
    button_fg = config['theme']['button_fg_color']
    border_color = config['theme']['border_color']
    font_family = config['theme']['font_family']
    font_size_medium = config['theme']['font_size_medium']
    
    root.configure(bg=bg_color)

    style = ttk.Style()
    style.theme_use('clam') # Scegli un tema base che permetta personalizzazione
    style.configure('.', background=bg_color, foreground=text_color, font=(font_family, font_size_medium))
    style.configure('TFrame', background=bg_color)
    style.configure('TLabel', background=bg_color, foreground=text_color)
    style.configure('TButton', background=button_bg, foreground=button_fg, font=(font_family, font_size_medium, 'bold'), borderwidth=1, relief="solid")
    style.map('TButton', 
              background=[('active', button_bg), ('disabled', '#555555')],
              foreground=[('active', button_fg), ('disabled', '#b0b0b0')]) # Mantieni lo stesso colore per lo stato attivo per coerenza
    style.configure(
        'ActivePlay.TButton',
        background='#1f9d55',
        foreground='white',
        font=(font_family, font_size_medium, 'bold'),
        borderwidth=1,
        relief="solid",
    )
    style.map(
        'ActivePlay.TButton',
        background=[('active', '#1f9d55'), ('disabled', '#1f9d55')],
        foreground=[('active', 'white'), ('disabled', 'white')],
    )
    
    style.configure('Treeview', 
                    background=border_color, 
                    foreground=text_color, 
                    fieldbackground=border_color,
                    borderwidth=1, 
                    relief="solid",
                    rowheight=25) # Aumenta l'altezza delle righe per una migliore leggibilità
    style.map('Treeview', background=[('selected', config['theme']['button_bg_color'])]) # Colore selezione
    style.configure('Treeview.Heading', 
                    background=button_bg, 
                    foreground=button_fg, 
                    font=(font_family, font_size_medium, 'bold'))
    
    style.configure('TScrolledText', background=border_color, foreground=text_color, borderwidth=1, relief="solid")
    style.configure('TEntry', fieldbackground=border_color, foreground=text_color, borderwidth=1, relief="solid")
    style.configure('TCheckbutton', background=bg_color, foreground=text_color, font=(font_family, font_size_medium))
    style.map('TCheckbutton', background=[('active', bg_color)])

    # Stile per i tab con carattere nero grassetto
    style.configure('TNotebook.Tab', font=(font_family, font_size_medium, 'bold'), foreground='black')


    # --- Frame Principale ---
    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill="both", expand=True)

    # --- Tab Control ---
    tab_control = ttk.Notebook(main_frame)
    tab_control.pack(fill="both", expand=True, pady=(0, 10))
    panel_state = get_panel_visibility_state()

    # Configura uno stile speciale per il pulsante di emergenza
    try:
        emergency_style = ttk.Style()
        emergency_style.configure('Emergency.TButton', 
                                background='#ff4444', 
                                foreground='white', 
                                font=('Segoe UI', 10, 'bold'))
        emergency_style.map(
            'Emergency.TButton',
            background=[('active', '#ff4444'), ('disabled', '#555555')],
            foreground=[('active', 'white'), ('disabled', '#b0b0b0')],
        )
    except Exception as e:
        console_log(f"⚠️ Impossibile applicare stile speciale al pulsante di emergenza: {e}", level="WARNING")
    macro_panel_refs = build_macro_management_tab(
        tab_control=tab_control,
        theme=config["theme"],
        macro_manager_config=config["macro_manager"],
        create_new_macro_dialog=create_new_macro_dialog,
        console_log=console_log,
        start_playback_thread=start_playback_thread,
        stop_current_operation=stop_current_operation,
        edit_selected_macro=edit_selected_macro,
        delete_selected_macro=delete_selected_macro,
        duplicate_selected_macro=duplicate_selected_macro,
        concat_macros_dialog=concat_macros_dialog,
        emergency_stop_all=emergency_stop_all,
        update_button_states=update_button_states,
        setup_click_context_preview=setup_click_context_preview,
        setup_execution_visualizer=setup_execution_visualizer,
        panel_state=panel_state,
        on_panel_state_change=toggle_collapsible_section,
    )

    macro_tab = macro_panel_refs["macro_tab"]
    new_macro_button = macro_panel_refs["new_macro_button"]
    record_button = macro_panel_refs["record_button"]
    play_button = macro_panel_refs["play_button"]
    stop_button = macro_panel_refs["stop_button"]
    edit_button = macro_panel_refs["edit_button"]
    delete_button = macro_panel_refs["delete_button"]
    duplicate_button = macro_panel_refs["duplicate_button"]
    concat_button = macro_panel_refs["concat_button"]
    emergency_stop_button = macro_panel_refs["emergency_stop_button"]
    loop_var = macro_panel_refs["loop_var"]
    loop_var_checkbox = macro_panel_refs["loop_var_checkbox"]
    loop_delay_entry = macro_panel_refs["loop_delay_entry"]
    max_repetitions_entry = macro_panel_refs["max_repetitions_entry"]
    macro_list_tree = macro_panel_refs["macro_list_tree"]
    console_parent = macro_panel_refs["console_parent"]
    loop_delay_entry.bind("<FocusOut>", persist_loop_delay_from_entry)
    loop_delay_entry.bind("<Return>", persist_loop_delay_from_entry)

    global macro_details_text
    macro_details_text = macro_panel_refs["macro_details_text"]

    build_secondary_tabs(
        tab_control=tab_control,
        setup_ui_graph_browser_interface=setup_ui_graph_browser_interface,
        setup_knowledge_graph_interface=setup_knowledge_graph_interface,
        setup_scheduled_tasks_interface=setup_scheduled_tasks_interface,
        setup_game_elements_interface=setup_game_elements_interface,
        setup_settings_tab=setup_settings_tab,
    )

    console_text = build_log_console(
        console_parent,
        font_family=font_family,
        font_size_small=config["theme"]["font_size_small"],
        border_color=border_color,
        text_color=text_color,
    )

    status_bar_refs = build_status_bar(root, bg_color=bg_color, text_color=text_color)
    status_bar = status_bar_refs["status_bar"]
    recording_indicator_button = status_bar_refs["recording_indicator_button"]
    playing_indicator_button = status_bar_refs["playing_indicator_button"]
    focus_monitor_indicator = status_bar_refs["focus_monitor_indicator"]

    global recording_timer_label
    recording_timer_label = status_bar_refs["recording_timer_label"]

    bind_main_window_events(
        root,
        macro_list_tree=macro_list_tree,
        update_button_states=update_button_states,
        update_macro_details=update_macro_details,
        open_selected_macro_action=open_selected_macro_action,
        on_window_focus_in=on_window_focus_in,
        on_window_focus_out=on_window_focus_out,
        on_window_destroy=on_window_destroy,
        stop_current_operation=stop_current_operation,
        emergency_stop_all=emergency_stop_all,
    )

    # Setup console logging
    setup_console_logging()
    process_log_queue()  # Start processing log queue
    debug_config = get_debug_config()
    if debug_config.get("save_playback_logs"):
        console_log(
            f"🧪 Debug playback attivo. Log file: {Path(__file__).resolve().parent / 'logs' / 'playback_focus_debug.log'}",
            level="INFO",
        )
    
    initialize_runtime_components()
    log_startup_messages()
    
    logger.info("Setup GUI completato")

    # Aggancia salvataggio posizione/dimensione alla chiusura
    def on_close():
        try:
            # Ferma il monitoraggio del focus
            stop_focus_monitoring()
            # Ferma il background scheduler
            task_controller.stop_scheduler(log_callback=console_log)
            # Ferma eventuali operazioni in corso
            stop_current_operation()
            # Aggiorna i dettagli della macro
            update_macro_details()
            # Salva la geometria della finestra
            save_window_geometry()
        finally:
            cleanup_on_application_close()
            root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)


if __name__ == "__main__":
    logger.info("Avvio GUI Macro Manager")
    setup_gui()
    logger.info("GUI inizializzata, avvio mainloop")
    root.mainloop()
