import time
import mouse
import keyboard
import win32gui
import win32process
import psutil
import json
import threading
import win32api
import win32con # Aggiunto import per win32con
import logging

from doomsday.vision.click_context_guard import ClickContextGuard, ClickContextGuardConfig
from macro_config import get_focus_check_interval, get_visual_click_guard_config
from services.click_element_capture_service import (
    DOOMSDAY_GRAPH_ID,
    UNKNOWN_VIEW_NODE_ID,
    classify_doomsday_view,
    register_recorded_click_element,
)

logger = logging.getLogger(__name__)


def _create_visual_click_guard():
    config = get_visual_click_guard_config() or {}
    return ClickContextGuard(
        ClickContextGuardConfig(
            enabled=bool(config.get("enabled", True)),
            radius_px=int(config.get("radius_px", 48)),
            resize_px=int(config.get("resize_px", 32)),
            min_similarity=float(config.get("min_similarity", 0.55)),
            stop_on_mismatch=bool(config.get("stop_on_mismatch", True)),
        )
    )


def _emit_playback_event_debug(log_callback, index, total, message):
    """Invia un messaggio di debug per l'esecuzione di un evento playback."""
    debug_message = f"DEBUG PLAYBACK [{index + 1}/{total}] {message}"
    logger.debug(debug_message)
    if log_callback:
        log_callback(debug_message, level="DEBUG")


def _format_actual_mouse_position():
    """Restituisce la posizione reale del cursore per il debug playback."""
    try:
        actual_x, actual_y = mouse.get_position()
        return f" actual=({actual_x},{actual_y})"
    except Exception as exc:
        return f" actual=(unavailable:{exc})"


def _get_actual_mouse_position():
    """Legge la posizione attuale del cursore."""
    try:
        return mouse.get_position()
    except Exception:
        try:
            return win32api.GetCursorPos()
        except Exception:
            return None


def _move_mouse_absolute(x, y):
    """Muove il cursore usando un backend ibrido con fallback."""
    target_x = int(x)
    target_y = int(y)

    # Primo tentativo: backend mouse, che storicamente dava feedback visivo migliore.
    try:
        mouse.move(target_x, target_y, absolute=True, duration=0)
        actual_position = _get_actual_mouse_position()
        if actual_position and abs(actual_position[0] - target_x) <= 2 and abs(actual_position[1] - target_y) <= 2:
            return
    except Exception:
        pass

    # Fallback: Win32 nativo.
    try:
        win32api.SetCursorPos((target_x, target_y))
        return
    except Exception:
        pass

    # Ultimo tentativo: API mouse relativa/assoluta senza keyword duration.
    mouse.move(target_x, target_y, absolute=True)


def _dispatch_mouse_button(button, is_press):
    """Invia un click mouse con backend ibrido e fallback."""
    normalized_button = (button or "left").lower()
    try:
        if is_press:
            mouse.press(normalized_button)
        else:
            mouse.release(normalized_button)
        return
    except Exception:
        pass

    button_flags = {
        "left": (win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP),
        "right": (win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP),
        "middle": (win32con.MOUSEEVENTF_MIDDLEDOWN, win32con.MOUSEEVENTF_MIDDLEUP),
    }
    down_flag, up_flag = button_flags.get(normalized_button, button_flags["left"])
    win32api.mouse_event(down_flag if is_press else up_flag, 0, 0, 0, 0)


def _dispatch_mouse_scroll(delta):
    """Invia uno scroll mouse con backend ibrido e fallback."""
    try:
        mouse.wheel(delta)
        return
    except Exception:
        pass

    wheel_delta = int((delta or 0) * 120)
    win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, wheel_delta, 0)

# Variabili globali per la registrazione
_eventi_registrati = []
_recording_active = False
_start_time = None
_target_process_name = "Doomsday.exe" # Valore di default
_record_duration_sec = 0 # 0 per registrazione continua
_recording_thread = None # Riferimento al thread di registrazione
_recording_stop_event = threading.Event()
_recording_log_callback = None
_recording_macro_name = ""
_recording_ui_node_id = None
_recorded_click_element_count = 0
_playback_stop_event = threading.Event()


def _wait_with_event(stop_event, timeout_seconds, step_seconds=0.05):
    """Attende in modo interrompibile, restituendo True se l'evento è stato segnalato."""
    if timeout_seconds <= 0:
        return stop_event.is_set()

    deadline = time.monotonic() + timeout_seconds
    while not stop_event.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        if stop_event.wait(min(step_seconds, remaining)):
            return True
    return True


def _cleanup_recording_hooks(log_callback=None):
    """Sgancia gli hook di input usati dalla registrazione."""
    try:
        keyboard.unhook_all()
        mouse.unhook_all()
    except Exception as e:
        if log_callback:
            log_callback(f"⚠️ Errore durante la pulizia degli hook di registrazione: {e}")

def now():
    """Restituisce il tempo trascorso dall'inizio della registrazione in millisecondi."""
    if _start_time is None:
        return 0
    return round((time.time() - _start_time) * 1000)

def get_foreground_process_name():
    """Restituisce il nome del processo della finestra in primo piano."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        return proc.name()
    except (win32gui.error, psutil.NoSuchProcess):
        return None

def get_game_window_rect(target_exe):
    """
    Cerca la finestra con il nome dell'eseguibile specificato e restituisce le sue
    coordinate client (escluse bordi e barra del titolo) sullo schermo.
    Restituisce None se la finestra non è trovata.
    """
    top_level_windows = []
    win32gui.EnumWindows(lambda hwnd, lst: lst.append(hwnd), top_level_windows)

    for hwnd in top_level_windows:
        if win32gui.IsWindowVisible(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid)
                if proc.name() == target_exe:
                    # Ottieni le coordinate della finestra
                    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                    
                    # Ottieni le coordinate dell'area client (senza bordi e barra del titolo)
                    client_left, client_top, client_right, client_bottom = win32gui.GetClientRect(hwnd)
                    
                    # Converte le coordinate client in coordinate schermo
                    point_tl = win32gui.ClientToScreen(hwnd, (client_left, client_top))
                    point_br = win32gui.ClientToScreen(hwnd, (client_right, client_bottom))
                    
                    rect = (point_tl[0], point_tl[1], point_br[0], point_br[1])
                    logger.debug("Finestra target trovata per '%s': %s", target_exe, rect)
                    return rect
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception as e:
                logger.debug("Errore lettura rettangolo finestra per '%s': %s", target_exe, e)
                continue
    logger.debug("Nessuna finestra visibile trovata per '%s'", target_exe)
    return None

def _attempt_bring_window_to_front(target_exe, log_callback=None):
    """
    Attempts to bring the target application window to the front.
    Returns True if successful, False otherwise.
    """
    try:
        # Find the window handle for the target application
        target_hwnd = None
        window_title = ""
        
        def enum_proc(hwnd, _):
            nonlocal target_hwnd, window_title
            if win32gui.IsWindowVisible(hwnd):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc = psutil.Process(pid)
                    if proc.name().lower() == target_exe.lower():
                        window_title = win32gui.GetWindowText(hwnd)
                        target_hwnd = hwnd
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                except:
                    pass
            return True
        
        win32gui.EnumWindows(enum_proc, None)
        
        if not target_hwnd:
            if log_callback:
                log_callback(f"⚠️ Finestra '{target_exe}' non trovata per il bring-to-front")
            return False
        
        # Try different methods to bring the window to front
        # Method 1: ShowWindow and SetForegroundWindow
        try:
            win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(target_hwnd)
            if log_callback:
                log_callback(f"✅ Tentativo riuscito: '{target_exe}' ({window_title}) portato in primo piano")
            return True
        except Exception:
            pass
        
        # Method 2: Activate window with alt+tab simulation
        try:
            current_hwnd = win32gui.GetForegroundWindow()
            win32gui.SetForegroundWindow(target_hwnd)
            win32gui.SetActiveWindow(target_hwnd)
            if log_callback:
                log_callback(f"✅ Metodo alternativo riuscito per '{target_exe}'")
            return True
        except Exception:
            pass
            
        if log_callback:
            log_callback(f"⚠️ Impossibile portare automaticamente '{target_exe}' in primo piano - richiederà click manuale")
        return False
        
    except Exception as e:
        if log_callback:
            log_callback(f"❌ Errore durante il tentativo di portare '{target_exe}' in primo piano: {e}")
        return False

def clear_playback_stop_request():
    """Azzera un eventuale segnale di stop playback precedente."""
    _playback_stop_event.clear()

def request_playback_stop(log_callback=None):
    """Richiede l'interruzione della riproduzione in corso."""
    _playback_stop_event.set()
    if log_callback:
        log_callback("🛑 Richiesta di stop playback inviata.")

def is_playback_stop_requested():
    """Indica se è stato richiesto lo stop del playback."""
    return _playback_stop_event.is_set()

def wait_for_app_window(exe_name, log_callback=None, max_wait_time=10, check_recording_flag=False, should_cancel=None):
    """
    Attende che la finestra dell'applicazione specificata diventi attiva.
    Version migliorata con timeout e retry logic.
    
    Args:
        exe_name: Nome dell'eseguibile da attendere
        log_callback: Funzione di callback per i log
        max_wait_time: Tempo massimo di attesa in secondi 
        check_recording_flag: Se True, controlla il flag _recording_active (solo per registrazione)
        should_cancel: Callback opzionale che restituisce True se l'operazione deve essere annullata
    """
    def is_cancelled():
        try:
            return bool(should_cancel and should_cancel())
        except Exception:
            return False

    if log_callback:
        log_callback(f"🕹️ In attesa che '{exe_name}' sia in primo piano (timeout: {max_wait_time}s)...")
        log_callback(f"💡 ISTRUZIONI: CLICCA sulla finestra '{exe_name}' per portarla in primo piano prima dello scadere del timer")
    logger.info("Inizio attesa focus per '%s' con timeout %.1fs", exe_name, max_wait_time)

    start_wait_time = time.time()
    last_check_time = start_wait_time
    attempted_bring_to_front = False
    
    # First check: verify the application process is running
    process_found = False
    process_pid = None
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            if is_cancelled():
                if log_callback:
                    log_callback(f"🛑 Attesa di '{exe_name}' annullata prima del focus.")
                return False
            if proc.info['name'].lower() == exe_name.lower():
                process_found = True
                process_pid = proc.info['pid']
                break
    except Exception:
        pass
    
    if not process_found:
        logger.warning("Processo target '%s' non trovato durante wait_for_app_window", exe_name)
        if log_callback:
            log_callback(f"❌ Processo '{exe_name}' non trovato nel sistema.")
            log_callback(f"💡 SOLUZIONE: Assicurati che '{exe_name}' sia in esecuzione prima di avviare la registrazione")
        return False
        
    # Check if the application window exists - con retry per gestire problemi di timing
    window_rect = None
    max_window_retries = 3
    for retry in range(max_window_retries):
        if is_cancelled():
            if log_callback:
                log_callback(f"🛑 Attesa di '{exe_name}' annullata durante la ricerca finestra.")
            return False
        window_rect = get_game_window_rect(exe_name)
        if window_rect:
            break
        if retry < max_window_retries - 1:
            # Piccolo delay prima di riprovare
            time.sleep(0.2)
            if log_callback:
                log_callback(f"🔄 Tentativo {retry + 1}/{max_window_retries}: Ricerca finestra '{exe_name}'...")
    
    if not window_rect:
        logger.warning("Finestra target '%s' non trovata dopo %s tentativi", exe_name, max_window_retries)
        if log_callback:
            log_callback(f"❌ Finestra dell'applicazione '{exe_name}' non trovata o non raggiungibile dopo {max_window_retries} tentativi.")
            log_callback(f"💡 SOLUZIONE: Assicurati che '{exe_name}' sia aperto e visibile sullo schermo prima di avviare la registrazione")
        return False
        
    while time.time() - start_wait_time < max_wait_time:
        if is_cancelled():
            if log_callback:
                log_callback(f"🛑 Attesa di '{exe_name}' annullata.")
            return False

        # Controlla se la registrazione è stata cancellata durante l'attesa (solo per registrazione)
        if check_recording_flag and not _recording_active:
            if log_callback:
                log_callback("⏹️ Registrazione annullata durante l'attesa dell'applicazione.")
            return False
        
        # Check focus status every second
        current_time = time.time()
        if current_time - last_check_time >= 1.0:
            current_foreground_process = get_foreground_process_name()
            logger.debug(
                "Controllo focus '%s': foreground='%s' elapsed=%.2fs",
                exe_name,
                current_foreground_process,
                current_time - start_wait_time,
            )
            if log_callback:
                remaining = max_wait_time - (current_time - start_wait_time)
                log_callback(f"🔍 Focus current: '{current_foreground_process}' (rimanenti: {remaining:.1f}s)")
            
            if current_foreground_process and current_foreground_process.lower() == exe_name.lower():
                if log_callback:
                    log_callback(f"✅ '{exe_name}' è in primo piano.")
                return True
            
            # Attempt to bring the window to front once during the timeout period
            if not attempted_bring_to_front and remaining < max_wait_time * 0.7:  # Try at 70% of timeout
                if log_callback:
                    log_callback(f"🔄 Tentativo automatico di portare '{exe_name}' in primo piano...")
                attempted_bring_to_front = True
                logger.info("Tentativo automatico bring-to-front per '%s'", exe_name)
                success = _attempt_bring_window_to_front(exe_name, log_callback)
                if success:
                    # Give the system a moment to respond
                    time.sleep(0.5)
                    # Check again after the bring-to-front attempt by getting fresh info
                    new_foreground_process = get_foreground_process_name()
                    logger.info(
                        "Esito bring-to-front per '%s': foreground adesso '%s'",
                        exe_name,
                        new_foreground_process,
                    )
                    if new_foreground_process and new_foreground_process.lower() == exe_name.lower():
                        if log_callback:
                            log_callback(f"✅ '{exe_name}' ora in primo piano dopo correzione automatica!")
                        return True
            
            last_check_time = current_time
        
        time.sleep(0.5) # Sleep base per responsività
    
    # Timeout reached - Try to check if the process is running and just needs user to bring it to focus
    if log_callback:
        log_callback(f"⏰ Timeout scaduto per '{exe_name}' - non è mai andato in focus.")
        current_foreground_process = get_foreground_process_name()
        logger.warning(
            "Timeout attesa focus per '%s'. Finestra in primo piano finale: '%s'",
            exe_name,
            current_foreground_process,
        )
        if current_foreground_process:
            log_callback(f"💡 Finestra in primo piano: '{current_foreground_process}' - È necessario cliccare su '{exe_name}' MANUALMENTE")
        else:
            log_callback(f"💡 Nessuna finestra rilevata in primo piano")
        
        # More helpful instructions
        log_callback(f"🚨 AZIONI DISPONIBILI:")
        log_callback(f"   1. Clicca sulla finestra '{exe_name}' nella taskbar o con Alt+Tab")
        log_callback(f"   2. Verifica che '{exe_name}' sia visibile sullo schermo")  
        log_callback(f"   3. Riprova la registrazione dopo aver portato '{exe_name}' in primo piano")
        log_callback(f"   4. Se il problema persiste, riavvia '{exe_name}' e riprova")
    return False

def keyboard_hook(event):
    global _eventi_registrati, _recording_active
    if _recording_active:
        if event.event_type == keyboard.KEY_DOWN:
            _eventi_registrati.append(_with_recording_ui_context({"time": now(), "type": "key", "event": "down", "name": event.name}))
        elif event.event_type == keyboard.KEY_UP:
            _eventi_registrati.append(_with_recording_ui_context({"time": now(), "type": "key", "event": "up", "name": event.name}))


def _with_recording_ui_context(event_data):
    if _recording_ui_node_id:
        event_data.setdefault("ui_graph_id", DOOMSDAY_GRAPH_ID)
        event_data.setdefault("ui_node_id", _recording_ui_node_id)
    return event_data


def _detect_recording_start_ui_node(target_exe, log_callback=None):
    game_rect = get_game_window_rect(target_exe)
    if not game_rect:
        if log_callback:
            log_callback("Vista iniziale non rilevata: finestra di gioco non disponibile.", "WARNING")
        return UNKNOWN_VIEW_NODE_ID
    try:
        ui_node_id = classify_doomsday_view(game_rect)
    except Exception as exc:
        logger.warning("Impossibile classificare la vista iniziale della registrazione: %s", exc)
        if log_callback:
            log_callback(f"Vista iniziale non classificabile: {exc}", "WARNING")
        return UNKNOWN_VIEW_NODE_ID
    if log_callback:
        log_callback(f"Vista iniziale registrazione: {ui_node_id}", "INFO")
    return ui_node_id


def _capture_recorded_click_element(event_data, *, abs_x, abs_y, game_rect):
    global _recorded_click_element_count
    try:
        observation = register_recorded_click_element(
            macro_name=_recording_macro_name,
            event_time_ms=event_data.get("time"),
            button=event_data.get("button"),
            abs_x=abs_x,
            abs_y=abs_y,
            normalized_x=event_data.get("normalized_x"),
            normalized_y=event_data.get("normalized_y"),
            window_rect=game_rect,
            view_node_id=_recording_ui_node_id,
        )
    except Exception as exc:
        logger.warning("Impossibile censire l'elemento cliccato durante la registrazione: %s", exc)
        if _recording_log_callback:
            _recording_log_callback(
                f"Censimento elemento cliccato non riuscito: {exc}",
                "WARNING",
            )
        return

    _recorded_click_element_count += 1
    event_data["game_element_id"] = observation.element_id
    event_data["ui_graph_id"] = observation.graph_id
    event_data["ui_node_id"] = observation.view_node_id
    if _recording_log_callback:
        action_label = "riusato dal catalogo" if observation.reused_existing else "censito"
        _recording_log_callback(
            f"Elemento cliccato {action_label}: "
            f"{observation.element_name} -> {observation.view_node_id}",
            "INFO",
        )

def mouse_hook(event):
    global _eventi_registrati, _recording_active, _target_process_name
    if _recording_active:
        # Ottieni il rettangolo della finestra di gioco client aggiornato
        game_rect = get_game_window_rect(_target_process_name)
        if not game_rect:
            # Se la finestra non è trovata, non registrare l'evento del mouse
            return

        window_left, window_top, window_right, window_bottom = game_rect
        window_width = window_right - window_left
        window_height = window_bottom - window_top # Corretto

        normalized_x = 0.0
        normalized_y = 0.0

        if isinstance(event, mouse.MoveEvent):
            current_x = event.x
            current_y = event.y
        else:
            # Per ButtonEvent e WheelEvent, ottieni la posizione corrente del mouse
            current_x, current_y = mouse.get_position()
            
        normalized_x = (current_x - window_left) / window_width if window_width != 0 else 0.0
        normalized_y = (current_y - window_top) / window_height if window_height != 0 else 0.0

        if isinstance(event, mouse.MoveEvent):
            _eventi_registrati.append(_with_recording_ui_context({
                "time": now(),
                "type": "mouse",
                "event": "move",
                "normalized_x": round(normalized_x, 4),
                "normalized_y": round(normalized_y, 4)
            }))
        elif isinstance(event, mouse.ButtonEvent):
            if event.event_type == "down":
                event_data = _with_recording_ui_context({
                    "time": now(),
                    "type": "mouse",
                    "event": "down",
                    "button": event.button,
                    "normalized_x": round(normalized_x, 4),
                    "normalized_y": round(normalized_y, 4)
                })
                _eventi_registrati.append(event_data)
                _capture_recorded_click_element(
                    event_data,
                    abs_x=current_x,
                    abs_y=current_y,
                    game_rect=game_rect,
                )
            elif event.event_type == "up":
                _eventi_registrati.append(_with_recording_ui_context({
                    "time": now(),
                    "type": "mouse",
                    "event": "up",
                    "button": event.button,
                    "normalized_x": round(normalized_x, 4),
                    "normalized_y": round(normalized_y, 4)
                }))
        elif isinstance(event, mouse.WheelEvent):
            _eventi_registrati.append(_with_recording_ui_context({
                "time": now(),
                "type": "mouse",
                "event": "scroll",
                "delta": event.delta,
                "normalized_x": round(normalized_x, 4),
                "normalized_y": round(normalized_y, 4)
            }))

def stop_recording(log_callback=None):
    """
    Ferma la registrazione degli eventi in modo più responsivo.
    Questa funzione può essere chiamata da un thread esterno (es. dalla GUI).
    """
    global _recording_active, _recording_thread
    if _recording_active:
        _recording_active = False # Imposta il flag per terminare i hook immediatamente
        _recording_stop_event.set()
        
        # Sgancia gli hook immediatamente per essere più responsivo
        try:
            _cleanup_recording_hooks(log_callback)
            if log_callback:
                log_callback("🔌 Hook di tastiera e mouse sganciati immediatamente.")
        except Exception:
            pass
        
        if log_callback:
            log_callback(f"✅ Registrazione fermata manualmente. Registrati {len(_eventi_registrati)} eventi.")
        
        # Aspetta che il thread di registrazione termini con timeout ridotto per essere più responsivo
        if _recording_thread and _recording_thread.is_alive() and _recording_thread != threading.current_thread():
            if log_callback:
                log_callback("⏳ Attendo terminazione thread di registrazione...")
            
            # Timeout ridotto da 1 secondo a 0.3 secondi per essere più responsivo
            _recording_thread.join(timeout=0.3)
            
            if _recording_thread.is_alive():
                if log_callback:
                    log_callback("⚠️ Thread di registrazione non terminato in tempo - continuo comunque.")
                # Non blocchiamo ulteriormente, il thread terminerà da solo
            else:
                if log_callback:
                    log_callback("✅ Thread di registrazione terminato correttamente.")
        
        return True
    else:
        if log_callback:
            log_callback("⚠️ Nessuna registrazione attiva da fermare.")
        return False

def registra_eventi(nome_macro, durata_sec, target_exe, log_callback=None):
    """
    Registra gli eventi di tastiera e mouse per una durata specificata,
    targettizzando una specifica applicazione. Si interrompe se la finestra attiva cambia.
    Versione migliorata per essere più responsiva agli stop.
    """
    global _eventi_registrati, _recording_active, _start_time, _target_process_name, _record_duration_sec, _recording_thread
    global _recording_log_callback, _recording_macro_name, _recording_ui_node_id, _recorded_click_element_count

    def is_target_window_active():
        current_process = get_foreground_process_name()
        return current_process and current_process.lower() == target_exe.lower()

    # Reset completo dello stato prima di iniziare una nuova registrazione
    # Questo assicura che non ci siano hook residui o stato inconsistente da registrazioni precedenti
    if _recording_active:
        if log_callback:
            log_callback("⚠️ Rilevata registrazione precedente ancora attiva. Pulizia dello stato...")
        try:
            _cleanup_recording_hooks(log_callback)
        except Exception:
            pass  # Ignora errori se gli hook non sono attivi
    
    # Reset completo di tutte le variabili di stato
    _eventi_registrati = []
    _recording_active = False  # Imposta prima a False per assicurare un reset pulito
    _start_time = None
    _target_process_name = None
    _record_duration_sec = 0
    _recording_thread = None
    _recording_log_callback = log_callback
    _recording_macro_name = nome_macro
    _recording_ui_node_id = None
    _recorded_click_element_count = 0
    _recording_stop_event.clear()
    
    # Piccolo delay per permettere al sistema di stabilizzarsi dopo il reset
    _wait_with_event(_recording_stop_event, 0.1)
    
    # Ora imposta lo stato per la nuova registrazione
    _recording_active = True # Imposta a True per indicare che stiamo iniziando
    _target_process_name = target_exe # Imposta il target process
    _record_duration_sec = durata_sec
    _recording_thread = threading.current_thread()

    # Verifica preliminare che il processo target esista
    if log_callback:
        log_callback(f"🔍 Verificando che '{target_exe}' sia disponibile...")
    
    process_found = False
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'].lower() == target_exe.lower():
                process_found = True
                break
    except Exception:
        pass
    
    if not process_found:
        if log_callback:
            log_callback(f"❌ Processo '{target_exe}' non trovato nel sistema.")
        _recording_active = False
        return None

    # Attendi che l'applicazione sia in primo piano con timeout più tollerante  
    window_found = wait_for_app_window(_target_process_name, log_callback, max_wait_time=15, check_recording_flag=True)
    
    # Se la registrazione è stata fermata durante l'attesa (es. dall'utente), esci
    if not _recording_active:
        if log_callback:
            log_callback("⏹️ Registrazione annullata manualmente durante l'attesa dell'applicazione.")
        return None
    
    if not window_found:
        if log_callback:
            log_callback("❌ Finestra dell'applicazione non trovata o non raggiungibile.")
        return None

    # Conferma multipla che la finestra è ancora in focus - con retry
    max_retries = 3
    for attempt in range(max_retries):
        current_foreground_process = get_foreground_process_name()
        if current_foreground_process and current_foreground_process.lower() == target_exe.lower():
            break
        if attempt < max_retries - 1:
            if log_callback:
                log_callback(f"⚠️ Tentativo {attempt + 1}/{max_retries}: Ripristino focus su '{target_exe}'...")
            if _wait_with_event(_recording_stop_event, 0.5):
                _recording_active = False
                return None
        else:
            if log_callback:
                log_callback(f"❌ '{target_exe}' non più in focus dopo {max_retries} tentativi.")
            _recording_active = False
            return None
    
    # Piccola pausa per assicurarsi che la finestra abbia completamente acquisito il focus
    if log_callback:
        log_callback("✅ Finestra target confermata attiva, avvio registrazione...")
    if _wait_with_event(_recording_stop_event, 0.2):
        _recording_active = False
        return None
    
    _recording_ui_node_id = _detect_recording_start_ui_node(_target_process_name, log_callback)
    _start_time = time.time() # Inizia a contare il tempo dopo che l'app è attiva
    
    # Setup hooks meno aggressivo con delucidate gestione errori
    try:
        keyboard.hook(keyboard_hook)
        mouse.hook(mouse_hook)
        if log_callback:
            log_callback("🎯 Hook di input attivati con successo.")
    except Exception as e:
        if log_callback:
            log_callback(f"❌ Errore durante l'attivazione degli hook: {e}")
        _recording_active = False
        return None

    if log_callback:
        if durata_sec > 0:
            log_callback(f"🔴 Registrazione di '{nome_macro}' per {durata_sec} secondi su '{_target_process_name}'...")
        else:
            log_callback(f"🔴 Registrazione continua di '{nome_macro}' su '{_target_process_name}'... (Premi Stop per terminare)")
    
    try:
        start_time = time.time()
        if durata_sec > 0:
            # Controlla più frequentemente se la registrazione deve essere fermata
            while _recording_active and (time.time() - start_time < durata_sec):
                if not is_target_window_active():
                    _recording_active = False
                    if log_callback:
                        log_callback(f"❌ Finestra target '{target_exe}' non più attiva. Interrompo la registrazione.", level="ERROR")
                    break
                if _wait_with_event(_recording_stop_event, 0.05):
                    _recording_active = False
                    break

            if log_callback:
                log_callback(f"✅ Registrazione di '{nome_macro}' completata. Registrati {len(_eventi_registrati)} eventi.")
                log_callback(f"Elementi cliccati censiti: {_recorded_click_element_count}.")
        else:
            # Per registrazione continua, la funzione resta bloccata fino a che _recording_active non diventa False
            while _recording_active:
                if not is_target_window_active():
                    _recording_active = False
                    if log_callback:
                        log_callback(f"❌ Finestra target '{target_exe}' non più attiva. Interrompo la registrazione.", level="ERROR")
                    break
                if _wait_with_event(_recording_stop_event, 0.05):
                    _recording_active = False
                    break

            if log_callback:
                log_callback(f"✅ Registrazione continua di '{nome_macro}' fermata. Registrati {len(_eventi_registrati)} eventi.")
                log_callback(f"Elementi cliccati censiti: {_recorded_click_element_count}.")

        # Final validation and cleanup
        try:
            if _eventi_registrati and len(_eventi_registrati) > 0:
                if log_callback:
                    log_callback(f"💾 {len(_eventi_registrati)} eventi pronti per il salvataggio.")
            else:
                if log_callback:
                    log_callback("⚠️ Nessun evento registrato - possibile registrazione troppo breve.")
        except Exception as e:
            if log_callback:
                log_callback(f"⚠️ Errore durante la validazione finale: {e}")

        return _eventi_registrati
    finally:
        _cleanup_recording_hooks(log_callback)
        _recording_active = False
        _recording_thread = None
        _recording_log_callback = None
        _recording_ui_node_id = None
        _recording_stop_event.clear()

def play_macro_events(macro_events, target_exe, log_callback=None, loop_enabled=False, loop_delay=0, max_repetitions=None, event_callback=None):
    """
    Riproduce una lista di eventi macro. Si interrompe se la finestra attiva non è più quella dell'applicazione target.
    Versione migliorata per essere più responsiva agli stop.
    
    Args:
        macro_events: Lista di eventi da riprodurre
        target_exe: Nome dell'eseguibile target
        log_callback: Callback per i log
        loop_enabled: Se True, ripete la sequenza
        loop_delay: Ritardo tra le iterazioni in secondi
        max_repetitions: Numero massimo di ripetizioni (None o 0 = nessun limite)
        event_callback: Callback chiamato per ogni evento eseguito (event, index, total)
    """
    focus_check_interval = max(0.05, float(get_focus_check_interval() or 0.05))
    last_focus_check_at = 0.0
    last_focus_check_result = True
    click_context_guard = _create_visual_click_guard()
    click_context_guard.reset()

    def is_target_window_active(force=False):
        nonlocal last_focus_check_at, last_focus_check_result
        now_monotonic = time.monotonic()
        if not force and (now_monotonic - last_focus_check_at) < focus_check_interval:
            return last_focus_check_result

        current_process_name = get_foreground_process_name()
        last_focus_check_result = bool(
            current_process_name and current_process_name.lower() == target_exe.lower()
        )
        last_focus_check_at = now_monotonic
        return last_focus_check_result

    iteration_count = 0
    playing_flag = True
    stop_reason = None
    
    # Controlla più frequentemente se la riproduzione deve essere fermata
    def should_stop():
        nonlocal stop_reason
        if is_playback_stop_requested():
            if stop_reason != "user_stop":
                stop_reason = "user_stop"
                if log_callback:
                    log_callback("🛑 Stop playback richiesto: interrompo la riproduzione.")
            return True
        # Controlla se la finestra target è ancora attiva
        if not is_target_window_active():
            if stop_reason != "focus_loss":
                stop_reason = "focus_loss"
                if log_callback:
                    log_callback(f"❌ Finestra target '{target_exe}' non più attiva. Interrompo la riproduzione.", level="ERROR")
            return True
        return False

    click_context_guard.reset()
    while playing_flag and (loop_enabled or iteration_count == 0):
        if should_stop():
            break

        iteration_count += 1
        iteration_guard_checked = False
        if log_callback:
            log_callback(f"🔄 Avvio iterazione {iteration_count} per '{target_exe}'...")
        else:
            print(f"🔄 Avvio iterazione {iteration_count} per '{target_exe}'...")

        # Evita una seconda attesa completa se la finestra e' gia' attiva:
        # il PlaybackService ha gia' gestito l'attesa iniziale prima di arrivare qui.
        window_found = True
        if not is_target_window_active(force=True):
            window_found = wait_for_app_window(
                target_exe,
                log_callback,
                max_wait_time=15,
                check_recording_flag=False,
                should_cancel=should_stop,
            )
        if not window_found or should_stop():
            if not window_found and stop_reason != "user_stop":
                if log_callback:
                    log_callback(f"❌ Finestra dell'applicazione '{target_exe}' non trovata o non raggiungibile.")
            break

        # Ottieni le dimensioni della finestra target
        game_rect = get_game_window_rect(target_exe)
        if not game_rect:
            if log_callback:
                log_callback(f"❌ Impossibile trovare la finestra di '{target_exe}' per la riproduzione.", level="ERROR")
            break
        window_left, window_top, window_right, window_bottom = game_rect
        window_width = window_right - window_left
        window_height = window_bottom - window_top

        last_event_time = 0
        for i, event in enumerate(macro_events):
            # Controlla più frequentemente se deve fermarsi
            if should_stop():
                playing_flag = False
                break

            current_event_time = event['time']
            delay = (current_event_time - last_event_time) / 1000.0
            if delay > 0:
                # Dividi il delay in controlli più frequenti per essere più responsivo
                check_interval = min(0.05, delay / 10)  # Controlla ogni 50ms o meno
                remaining_delay = delay
                while remaining_delay > 0 and not should_stop():
                    sleep_time = min(check_interval, remaining_delay)
                    time.sleep(sleep_time)
                    remaining_delay -= sleep_time

                if should_stop():
                    playing_flag = False
                    break

            last_event_time = current_event_time

            if event['type'] == "key":
                key_name = event.get('name')
                if key_name:
                    try:
                        if event['event'] == "down":
                            _emit_playback_event_debug(
                                log_callback,
                                i,
                                len(macro_events),
                                f"key_down key='{key_name}' t={current_event_time}ms",
                            )
                            keyboard.press(key_name)
                            if event_callback:
                                event_callback(event, i, len(macro_events), "key_press", key_name)
                        elif event['event'] == "up":
                            _emit_playback_event_debug(
                                log_callback,
                                i,
                                len(macro_events),
                                f"key_up key='{key_name}' t={current_event_time}ms",
                            )
                            keyboard.release(key_name)
                            if event_callback:
                                event_callback(event, i, len(macro_events), "key_release", key_name)
                    except Exception as e:
                        if log_callback:
                            log_callback(f"❌ Errore tastiera (evento {i}): {e} per tasto '{key_name}'", level="ERROR")
            elif event['type'] == "mouse":
                mouse_event_type = event.get('event')
                button = event.get('button')
                delta = event.get('delta')
                abs_x = int(window_left + (event.get('normalized_x', 0.0) * window_width))
                abs_y = int(window_top + (event.get('normalized_y', 0.0) * window_height))
                try:
                    if mouse_event_type == "move":
                        _emit_playback_event_debug(
                            log_callback,
                            i,
                            len(macro_events),
                            f"mouse_move abs=({abs_x},{abs_y}) norm=({event.get('normalized_x')},{event.get('normalized_y')}) t={current_event_time}ms",
                        )
                        _move_mouse_absolute(abs_x, abs_y)
                        _emit_playback_event_debug(
                            log_callback,
                            i,
                            len(macro_events),
                            f"mouse_move_result target=({abs_x},{abs_y}){_format_actual_mouse_position()}",
                        )
                        if event_callback:
                            event_callback(event, i, len(macro_events), "mouse_move", None, abs_x, abs_y)
                    elif mouse_event_type == "down":
                        guard_result = None
                        if not iteration_guard_checked:
                            iteration_guard_checked = True
                            try:
                                guard_result = click_context_guard.verify_or_prime(
                                    abs_x,
                                    abs_y,
                                    screen_bounds=game_rect,
                                )
                            except Exception as exc:
                                stop_reason = "visual_guard_error"
                                if log_callback:
                                    log_callback(
                                        f"❌ Controllo visivo click non disponibile: {exc}. Riproduzione fermata per sicurezza.",
                                        level="ERROR",
                                    )
                                playing_flag = False
                                break
                            if guard_result["primed"]:
                                _emit_playback_event_debug(
                                    log_callback,
                                    i,
                                    len(macro_events),
                                    f"visual_guard_reference_set abs=({abs_x},{abs_y}) threshold={guard_result['threshold']:.2f}",
                                )
                            elif not guard_result["ok"]:
                                stop_reason = "visual_context_mismatch"
                                message = (
                                    f"❌ Contesto visivo non compatibile all'avvio dell'iterazione su ({abs_x},{abs_y}). "
                                    f"Compatibilità {guard_result['score']:.2f} < soglia {guard_result['threshold']:.2f}. "
                                    "Macro fermata per evitare click sulla schermata sbagliata."
                                )
                                if log_callback:
                                    log_callback(message, level="ERROR")
                                    log_callback(
                                        "💡 Il contesto iniziale non è recuperabile automaticamente: la macro si ferma in sicurezza.",
                                        level="WARNING",
                                    )
                                playing_flag = False
                                break

                        _emit_playback_event_debug(
                            log_callback,
                            i,
                            len(macro_events),
                            f"mouse_down button='{button}' abs=({abs_x},{abs_y}) norm=({event.get('normalized_x')},{event.get('normalized_y')}) t={current_event_time}ms",
                        )
                        _move_mouse_absolute(abs_x, abs_y)
                        if button:
                            _dispatch_mouse_button(button, is_press=True)
                        _emit_playback_event_debug(
                            log_callback,
                            i,
                            len(macro_events),
                            f"mouse_down_result button='{button}' target=({abs_x},{abs_y}){_format_actual_mouse_position()}",
                        )
                        if event_callback:
                            event_callback(
                                event,
                                i,
                                len(macro_events),
                                "mouse_down",
                                button,
                                abs_x,
                                abs_y,
                                visual_context=guard_result,
                            )
                    elif mouse_event_type == "up":
                        _emit_playback_event_debug(
                            log_callback,
                            i,
                            len(macro_events),
                            f"mouse_up button='{button}' abs=({abs_x},{abs_y}) norm=({event.get('normalized_x')},{event.get('normalized_y')}) t={current_event_time}ms",
                        )
                        _move_mouse_absolute(abs_x, abs_y)
                        if button:
                            _dispatch_mouse_button(button, is_press=False)
                        _emit_playback_event_debug(
                            log_callback,
                            i,
                            len(macro_events),
                            f"mouse_up_result button='{button}' target=({abs_x},{abs_y}){_format_actual_mouse_position()}",
                        )
                        if event_callback:
                            event_callback(event, i, len(macro_events), "mouse_up", button, abs_x, abs_y)
                    elif mouse_event_type == "scroll":
                        _emit_playback_event_debug(
                            log_callback,
                            i,
                            len(macro_events),
                            f"mouse_scroll delta={delta} abs=({abs_x},{abs_y}) norm=({event.get('normalized_x')},{event.get('normalized_y')}) t={current_event_time}ms",
                        )
                        _dispatch_mouse_scroll(delta)
                        if event_callback:
                            event_callback(event, i, len(macro_events), "mouse_scroll", None, abs_x, abs_y, delta)
                except Exception as e:
                    if log_callback:
                        log_callback(f"❌ Errore mouse (evento {i}): {e} per tipo '{mouse_event_type}'", level="ERROR")

        # Controlla se deve continuare con il loop
        if playing_flag and loop_enabled:
            # Controlla se è stato raggiunto il numero massimo di ripetizioni
            if max_repetitions is not None and max_repetitions > 0 and iteration_count >= max_repetitions:
                if log_callback:
                    log_callback(f"✅ Raggiunto il numero massimo di ripetizioni ({max_repetitions}). Interrompo la riproduzione.")
                break

            if log_callback:
                log_callback(f"😴 Ritardo di {loop_delay} secondi prima della prossima iterazione...")

            # Controlla più frequentemente durante il delay del loop
            remaining_loop_delay = loop_delay
            check_interval = 0.1  # Controlla ogni 100ms
            while remaining_loop_delay > 0 and not should_stop():
                sleep_time = min(check_interval, remaining_loop_delay)
                time.sleep(sleep_time)
                remaining_loop_delay -= sleep_time

            if should_stop():
                break
        else:
            break

    if log_callback:
        log_callback(f"✅ Riproduzione macro completata o interrotta.")
    else:
        print("✅ Riproduzione macro completata o interrotta.")


if __name__ == "__main__":
    # Esempio di utilizzo se si esegue questo script direttamente
    # NON dovrebbe essere chiamato così da gui_macro_manager.py
    print("Questo script è pensato per essere importato come modulo.")
    print("Esempio di registrazione di una macro di test per 5 secondi su notepad.exe:")
    
    # Registrazione a tempo
    # events = registra_eventi("TestMacroTime", 5, "notepad.exe", print)
    # if events:
    #     print(f"Eventi registrati: {len(events)}")
    #     # Qui potresti salvare 'events' in un file o database

    # Esempio di registrazione continua (richiede stop_recording manuale)
    print("\nAvvio registrazione continua (premi Ctrl+C o chiama stop_recording() da un altro punto per fermare)...")
    registra_eventi("TestMacroContinuous", 0, "notepad.exe", print)
    
    # Per fermare la registrazione continua, dovresti chiamare stop_recording()
    # dopo un certo tempo o un'azione utente, ad esempio:
    # time.sleep(10)
    # stop_recording(print)
    # print(f"Eventi registrati per TestMacroContinuous: {len(_eventi_registrati)}")
