import time
import mouse
import keyboard
import win32gui
import win32process
import psutil
import json
import threading
import win32con # Aggiunto import per win32con

# Variabili globali per la registrazione
_eventi_registrati = []
_recording_active = False
_start_time = None
_target_process_name = "Doomsday.exe" # Valore di default
_record_duration_sec = 0 # 0 per registrazione continua
_recording_thread = None # Riferimento al thread di registrazione
_playback_stop_event = threading.Event()

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
                    
                    return (point_tl[0], point_tl[1], point_br[0], point_br[1])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception as e:
                # print(f"Errore durante l'ottenimento del rettangolo della finestra: {e}")
                continue
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
                success = _attempt_bring_window_to_front(exe_name, log_callback)
                if success:
                    # Give the system a moment to respond
                    time.sleep(0.5)
                    # Check again after the bring-to-front attempt by getting fresh info
                    new_foreground_process = get_foreground_process_name()
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
            _eventi_registrati.append({"time": now(), "type": "key", "event": "down", "name": event.name})
        elif event.event_type == keyboard.KEY_UP:
            _eventi_registrati.append({"time": now(), "type": "key", "event": "up", "name": event.name})

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
            _eventi_registrati.append({
                "time": now(),
                "type": "mouse",
                "event": "move",
                "normalized_x": round(normalized_x, 4),
                "normalized_y": round(normalized_y, 4)
            })
        elif isinstance(event, mouse.ButtonEvent):
            if event.event_type == "down":
                _eventi_registrati.append({
                    "time": now(),
                    "type": "mouse",
                    "event": "down",
                    "button": event.button,
                    "normalized_x": round(normalized_x, 4),
                    "normalized_y": round(normalized_y, 4)
                })
            elif event.event_type == "up":
                _eventi_registrati.append({
                    "time": now(),
                    "type": "mouse",
                    "event": "up",
                    "button": event.button,
                    "normalized_x": round(normalized_x, 4),
                    "normalized_y": round(normalized_y, 4)
                })
        elif isinstance(event, mouse.WheelEvent):
            _eventi_registrati.append({
                "time": now(),
                "type": "mouse",
                "event": "scroll",
                "delta": event.delta,
                "normalized_x": round(normalized_x, 4),
                "normalized_y": round(normalized_y, 4)
            })

def stop_recording(log_callback=None):
    """
    Ferma la registrazione degli eventi in modo più responsivo.
    Questa funzione può essere chiamata da un thread esterno (es. dalla GUI).
    """
    global _recording_active, _recording_thread
    if _recording_active:
        _recording_active = False # Imposta il flag per terminare i hook immediatamente
        
        # Sgancia gli hook immediatamente per essere più responsivo
        try:
            keyboard.unhook_all()
            mouse.unhook_all()
            if log_callback:
                log_callback("🔌 Hook di tastiera e mouse sganciati immediatamente.")
        except Exception as e:
            if log_callback:
                log_callback(f"⚠️ Errore durante lo sganciamento degli hook: {e}")
        
        if log_callback:
            log_callback(f"✅ Registrazione fermata manualmente. Registrati {len(_eventi_registrati)} eventi.")
        
        # Aspetta che il thread di registrazione termini con timeout ridotto per essere più responsivo
        if _recording_thread and _recording_thread.is_alive():
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
        
        _recording_thread = None # Rimuovi il riferimento al thread terminato
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

    def is_target_window_active():
        current_process = get_foreground_process_name()
        return current_process and current_process.lower() == target_exe.lower()

    # Reset completo dello stato prima di iniziare una nuova registrazione
    # Questo assicura che non ci siano hook residui o stato inconsistente da registrazioni precedenti
    if _recording_active:
        if log_callback:
            log_callback("⚠️ Rilevata registrazione precedente ancora attiva. Pulizia dello stato...")
        try:
            keyboard.unhook_all()
            mouse.unhook_all()
        except Exception:
            pass  # Ignora errori se gli hook non sono attivi
    
    # Reset completo di tutte le variabili di stato
    _eventi_registrati = []
    _recording_active = False  # Imposta prima a False per assicurare un reset pulito
    _start_time = None
    _target_process_name = None
    _record_duration_sec = 0
    _recording_thread = None
    
    # Piccolo delay per permettere al sistema di stabilizzarsi dopo il reset
    time.sleep(0.1)
    
    # Ora imposta lo stato per la nuova registrazione
    _recording_active = True # Imposta a True per indicare che stiamo iniziando
    _target_process_name = target_exe # Imposta il target process
    _record_duration_sec = durata_sec

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
            time.sleep(0.5)
        else:
            if log_callback:
                log_callback(f"❌ '{target_exe}' non più in focus dopo {max_retries} tentativi.")
            _recording_active = False
            return None
    
    # Piccola pausa per assicurarsi che la finestra abbia completamente acquisito il focus
    if log_callback:
        log_callback("✅ Finestra target confermata attiva, avvio registrazione...")
    time.sleep(0.2)
    
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
    
    if durata_sec > 0:
        # Crea un thread per gestire il timeout della registrazione
        _recording_thread = threading.Thread(target=lambda: time.sleep(durata_sec))
        _recording_thread.start()
        start_time = time.time()
        
        # Controlla più frequentemente se la registrazione deve essere fermata
        while _recording_active and (time.time() - start_time < durata_sec):
            if not is_target_window_active():
                _recording_active = False
                if log_callback:
                    log_callback(f"❌ Finestra target '{target_exe}' non più attiva. Interrompo la registrazione.", level="ERROR")
                break
            time.sleep(0.05)  # Controlla ogni 50ms invece di 100ms per essere più responsivo
        
        if _recording_thread.is_alive():
            _recording_thread.join(timeout=0.2)  # Timeout ridotto per essere più responsivo
            
        # Cleanup hooks when recording completes
        keyboard.unhook_all()
        mouse.unhook_all()
        _recording_active = False
        
        if log_callback:
            log_callback(f"✅ Registrazione di '{nome_macro}' completata. Registrati {len(_eventi_registrati)} eventi.")
    else:
        # Per registrazione continua, la funzione resta bloccata fino a che _recording_active non diventa False
        # Controlla più frequentemente per essere più responsiva
        while _recording_active:
            if not is_target_window_active():
                _recording_active = False
                if log_callback:
                    log_callback(f"❌ Finestra target '{target_exe}' non più attiva. Interrompo la registrazione.", level="ERROR")
                break
            time.sleep(0.05)  # Controlla ogni 50ms invece di 100ms per essere più responsiva
            
        # Cleanup hooks when continuous recording stops
        keyboard.unhook_all()
        mouse.unhook_all()
        
        if log_callback:
            log_callback(f"✅ Registrazione continua di '{nome_macro}' fermata. Registrati {len(_eventi_registrati)} eventi.")

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
    def is_target_window_active():
        return get_foreground_process_name() and get_foreground_process_name().lower() == target_exe.lower()

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

    while playing_flag and (loop_enabled or iteration_count == 0):
        if should_stop():
            break

        iteration_count += 1
        if log_callback:
            log_callback(f"🔄 Avvio iterazione {iteration_count} per '{target_exe}'...")
        else:
            print(f"🔄 Avvio iterazione {iteration_count} per '{target_exe}'...")

        # Attendi che la finestra target sia in primo piano
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
                            keyboard.press(key_name)
                            if event_callback:
                                event_callback(event, i, len(macro_events), "key_press", key_name)
                        elif event['event'] == "up":
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
                        mouse.move(abs_x, abs_y, absolute=True, duration=0)
                        if event_callback:
                            event_callback(event, i, len(macro_events), "mouse_move", None, abs_x, abs_y)
                    elif mouse_event_type == "down":
                        mouse.move(abs_x, abs_y, absolute=True, duration=0)
                        if button:
                            mouse.press(button)
                        if event_callback:
                            event_callback(event, i, len(macro_events), "mouse_down", button, abs_x, abs_y)
                    elif mouse_event_type == "up":
                        mouse.move(abs_x, abs_y, absolute=True, duration=0)
                        if button:
                            mouse.release(button)
                        if event_callback:
                            event_callback(event, i, len(macro_events), "mouse_up", button, abs_x, abs_y)
                    elif mouse_event_type == "scroll":
                        mouse.wheel(delta)
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
