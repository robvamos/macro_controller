import threading
import time
from repositories.macro_repository import (
    get_macro_metadata_by_id,
    load_macro_events,
)
from repositories.task_repository import (
    check_and_complete_task_if_needed,
    get_active_tasks_ordered_by_next_execution,
    get_task_macro_sequence,
    get_tasks_due_for_execution,
    increment_task_execution_count,
    start_task_scheduling,
    stop_task_scheduling,
    update_last_execution,
)
from macro_controller import (
    play_macro_events,
    get_game_window_rect,
    get_foreground_process_name,
    _attempt_bring_window_to_front
)


# Variabili globali per il task scheduler
scheduler_active = False
scheduler_thread = None
_scheduler_stop_event = threading.Event()
_scheduler_state_lock = threading.Lock()

# Lock globale per garantire che solo un task alla volta esegua le sue macro
# Quando un task inizia la prima macro, gli altri task devono attendere
task_execution_lock = threading.Lock()
currently_executing_task_id = None
currently_executing_task_name = None
_execution_slot_lock = threading.Lock()
_execution_slot_reserved = False
_execution_slot_owner = None


def _wait_for_scheduler_stop(timeout_seconds):
    """Attende lo stop dello scheduler oppure il timeout specificato."""
    return _scheduler_stop_event.wait(timeout_seconds)


def _reserve_execution_slot(owner_id):
    """Prenota lo slot di esecuzione esclusiva prima di creare il worker."""
    global _execution_slot_reserved, _execution_slot_owner
    with _execution_slot_lock:
        if _execution_slot_reserved:
            return False
        _execution_slot_reserved = True
        _execution_slot_owner = owner_id
        return True


def _release_execution_slot(owner_id=None):
    """Rilascia lo slot di esecuzione prenotato."""
    global _execution_slot_reserved, _execution_slot_owner
    with _execution_slot_lock:
        if not _execution_slot_reserved:
            return
        if owner_id is not None and _execution_slot_owner != owner_id:
            return
        _execution_slot_reserved = False
        _execution_slot_owner = None


def start_scheduler(log_callback=None, root_callback=None):
    """Avvia il background scheduler per gli scheduled tasks."""
    global scheduler_active, scheduler_thread

    with _scheduler_state_lock:
        if scheduler_active and scheduler_thread and scheduler_thread.is_alive():
            if log_callback:
                log_callback("⚠️ Scheduler già attivo")
            return

        _scheduler_stop_event.clear()
        scheduler_active = True
    
    def scheduler_loop():
        global scheduler_active, scheduler_thread
        if log_callback:
            log_callback("🔄 Background Scheduler per scheduled tasks avviato.")
        
        while scheduler_active and not _scheduler_stop_event.is_set():
            try:
                # Controlla se la GUI è ancora attiva (se root_callback è fornito)
                if root_callback and not root_callback():
                    break
                
                # Ottieni i task da eseguire e ordinali per prossima esecuzione
                # Il primo task che deve partire è quello che acquisisce il lock
                tasks_to_execute = get_tasks_due_for_execution()
                
                # Ordina i task per prossima esecuzione (più prossimi prima)
                # Questo garantisce che il task più urgente acquisisca il lock per primo
                active_tasks_ordered = get_active_tasks_ordered_by_next_execution()
                
                # Ordina i task da eseguire in base all'ordine di prossima esecuzione
                task_order_map = {t['id']: idx for idx, t in enumerate(active_tasks_ordered)}
                tasks_to_execute.sort(key=lambda t: task_order_map.get(t['id'], 9999))
                
                for task in tasks_to_execute:
                    if _scheduler_stop_event.is_set():
                        break

                    try:
                        # Avvia la schedulazione se non è già running
                        if task.get('stato') != 'running':
                            start_task_scheduling(task['id'])
                            if log_callback:
                                log_callback(f"▶️ Avviata schedulazione per task '{task['nome']}'")
                        
                        # Controlla se il task deve essere completato
                        if check_and_complete_task_if_needed(task['id']):
                            if log_callback:
                                log_callback(f"✅ Task '{task['nome']}' completato: soglia di terminazione raggiunta")
                            continue
                        
                        # Prenota lo slot esclusivo prima di creare il worker per evitare race condition.
                        if not _reserve_execution_slot(task['id']):
                            if log_callback:
                                executing_task_name = "altro task" if currently_executing_task_id != task['id'] else task['nome']
                                log_callback(f"⏸️ Task '{task['nome']}' in attesa: un altro task sta già eseguendo le sue macro")
                            continue
                        
                        execute_scheduled_task(task, log_callback, execution_slot_reserved=True)
                    except Exception as e:
                        _release_execution_slot(task['id'])
                        if log_callback:
                            log_callback(f"❌ Errore durante l'esecuzione del task '{task['nome']}': {e}")
                
                # Aspetta 30 secondi prima di ricontrollare, ma interrompiti subito se richiesto.
                if _wait_for_scheduler_stop(30):
                    break
                
            except Exception as e:
                if log_callback:
                    log_callback(f"❌ Errore nel background scheduler: {e}")
                if _wait_for_scheduler_stop(60):
                    break  # In caso di errore, aspetta di più prima di riprovare
        
        scheduler_active = False
        scheduler_thread = None
        if log_callback:
            log_callback("🛑 Background Scheduler fermato.")
    
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True, name="scheduled-task-loop")
    scheduler_thread.start()


def stop_scheduler(log_callback=None):
    """Ferma il background scheduler."""
    global scheduler_active, scheduler_thread
    
    if not scheduler_active:
        if log_callback:
            log_callback("⚠️ Scheduler già fermo")
        return
    
    scheduler_active = False
    _scheduler_stop_event.set()
    if scheduler_thread and scheduler_thread.is_alive():
        scheduler_thread.join(timeout=5.0)
    
    scheduler_thread = None
    
    if log_callback:
        log_callback("🛑 Background Scheduler fermato.")


def get_scheduler_runtime_status():
    """Restituisce uno snapshot leggero dello stato runtime dello scheduler."""
    thread_alive = bool(scheduler_thread and scheduler_thread.is_alive())
    with _execution_slot_lock:
        slot_reserved = _execution_slot_reserved
        slot_owner = _execution_slot_owner

    return {
        "scheduler_active": scheduler_active,
        "thread_alive": thread_alive,
        "slot_reserved": slot_reserved,
        "slot_owner": slot_owner,
        "currently_executing_task_id": currently_executing_task_id,
        "currently_executing_task_name": currently_executing_task_name,
    }


def execute_scheduled_task(task, log_callback=None, execution_slot_reserved=False):
    """Esegue un scheduled task. Se esiste una sequenza di macro, esegue tutte le macro in sequenza con i tempi di attesa configurati."""
    try:
        task_id = task['id']
        task_name = task['nome']
        
        if log_callback:
            log_callback(f"⏰ Esecuzione scheduled task '{task_name}' (ID: {task_id})")
        
        # Controlla se esiste una sequenza di macro per questo task
        macro_sequence = get_task_macro_sequence(task_id)
        
        if macro_sequence:
            # Esegui la sequenza di macro
            if log_callback:
                log_callback(f"📋 Esecuzione sequenza di {len(macro_sequence)} macro per il task '{task_name}'")
        else:
            # Retrocompatibilità: usa la macro_id dalla tabella ScheduledTasks
            macro_id = task.get('macro_id')
            if not macro_id:
                if log_callback:
                    log_callback(f"❌ Nessuna macro o sequenza trovata per il task '{task_name}'")
                update_last_execution(task_id)
                if execution_slot_reserved:
                    _release_execution_slot(task_id)
                return
            
            # Crea una sequenza temporanea con una sola macro (per retrocompatibilità)
            macro_metadata = get_macro_metadata_by_id(macro_id)
            if not macro_metadata:
                if log_callback:
                    log_callback(f"❌ Macro con ID {macro_id} non trovata per il task '{task_name}'")
                update_last_execution(task_id)
                if execution_slot_reserved:
                    _release_execution_slot(task_id)
                return
            
            macro_sequence = [{
                'macro_id': macro_id,
                'attesa_secondi': 0,
                'macro_nome': macro_metadata['nome'],
                'macro_eseguibile': macro_metadata['eseguibile']
            }]
        
        # Esegui tutte le macro in sequenza
        def execute_sequence():
            global currently_executing_task_id, currently_executing_task_name
            lock_acquired = False
            try:
                # Acquisisci il lock PRIMA di eseguire la prima macro
                # Questo impedisce ad altri task di partire
                if log_callback:
                    log_callback(f"🔒 Task '{task_name}' acquisisce il lock per l'esecuzione esclusiva")
                
                task_execution_lock.acquire()
                lock_acquired = True
                currently_executing_task_id = task_id
                currently_executing_task_name = task_name
                
                if log_callback:
                    log_callback(f"✅ Task '{task_name}' ha acquisito il lock - inizio esecuzione esclusiva")
                
                task_stopped = False  # Flag per indicare se il task è stato fermato
                for idx, seq_item in enumerate(macro_sequence):
                    macro_id = seq_item['macro_id']
                    attesa_secondi = seq_item.get('attesa_secondi', 0)
                    macro_name = seq_item.get('macro_nome', f"ID:{macro_id}")
                    
                    # Attendi prima di eseguire questa macro (tranne la prima)
                    if idx > 0 and attesa_secondi > 0:
                        if log_callback:
                            log_callback(f"⏳ Attesa di {attesa_secondi} secondi prima della prossima macro...")
                        time.sleep(attesa_secondi)
                    
                    # Carica i metadati della macro
                    macro_metadata = get_macro_metadata_by_id(macro_id)
                    if not macro_metadata:
                        if log_callback:
                            log_callback(f"❌ Macro con ID {macro_id} non trovata per il task '{task_name}'")
                        continue
                    
                    # Carica gli eventi della macro
                    macro_events = load_macro_events(macro_id)
                    if not macro_events:
                        if log_callback:
                            log_callback(f"⚠️ Nessun evento trovato per la macro '{macro_metadata['nome']}' del task '{task_name}'")
                        continue
                    
                    target_exe = macro_metadata['eseguibile']
                    macro_name = macro_metadata['nome']
                    
                    if log_callback:
                        log_callback(f"📍 Esecuzione macro {idx + 1}/{len(macro_sequence)}: '{macro_name}' su '{target_exe}' per il task '{task_name}'")
                    
                    # Verifica che la finestra dell'applicazione esista
                    window_rect = get_game_window_rect(target_exe)
                    if not window_rect:
                        # Finestra non trovata: ferma il task e logga l'errore
                        if log_callback:
                            log_callback(f"❌ Errore di esecuzione: finestra dell'applicazione '{target_exe}' non trovata per il task '{task_name}'. Task fermato.")
                        stop_task_scheduling(task_id)
                        task_stopped = True
                        break  # Esce dal loop delle macro
                    
                    # Controlla se la finestra ha già il focus
                    current_foreground_process = get_foreground_process_name()
                    if not current_foreground_process or current_foreground_process.lower() != target_exe.lower():
                        # La finestra non ha il focus: porta la finestra in primo piano
                        if log_callback:
                            log_callback(f"🔄 Spostamento focus alla finestra '{target_exe}'...")
                        success = _attempt_bring_window_to_front(target_exe, log_callback)
                        if not success:
                            # Se non riesce a portare la finestra in primo piano, aspetta un po' e verifica di nuovo
                            time.sleep(0.5)
                            current_foreground_process = get_foreground_process_name()
                            if not current_foreground_process or current_foreground_process.lower() != target_exe.lower():
                                if log_callback:
                                    log_callback(f"⚠️ Impossibile portare '{target_exe}' in primo piano, ma procedo comunque con l'esecuzione")
                    
                    # Esegui la macro
                    play_macro_events(macro_events, target_exe, log_callback=log_callback, loop_enabled=False, loop_delay=0)
                
                # Dopo aver eseguito tutte le macro nella sequenza (solo se il task non è stato fermato)
                if not task_stopped:
                    update_last_execution(task_id)
                    
                    # Incrementa il conteggio delle esecuzioni
                    increment_task_execution_count(task_id)
                    
                    # Controlla se il task deve essere completato dopo questa esecuzione
                    if check_and_complete_task_if_needed(task_id):
                        if log_callback:
                            log_callback(f"✅ Task '{task_name}' completato: soglia di terminazione raggiunta")
                    else:
                        if log_callback:
                            log_callback(f"✅ Task '{task_name}' completato con successo")
                else:
                    if log_callback:
                        log_callback(f"🛑 Task '{task_name}' fermato a causa di errore di esecuzione")
            except Exception as e:
                if log_callback:
                    log_callback(f"❌ Errore nell'esecuzione della sequenza per il task '{task_name}': {e}")
            finally:
                # Rilascia sempre il lock quando il task finisce, anche in caso di errore
                if lock_acquired:
                    currently_executing_task_id = None
                    currently_executing_task_name = None
                    task_execution_lock.release()
                    if log_callback:
                        log_callback(f"🔓 Task '{task_name}' ha rilasciato il lock - altri task possono ora partire")
                if execution_slot_reserved:
                    _release_execution_slot(task_id)
        
        # Esegui in un thread separato per non bloccare il scheduler
        execution_thread = threading.Thread(target=execute_sequence, daemon=True, name=f"scheduled-task-{task_id}")
        execution_thread.start()
        
    except Exception as e:
        if execution_slot_reserved:
            _release_execution_slot(task['id'])
        if log_callback:
            log_callback(f"❌ Errore critico nell'esecuzione del scheduled task '{task['nome']}': {e}")


def is_scheduler_active():
    """Controlla se lo scheduler è attivo."""
    return scheduler_active


def test_execute_scheduled_task(task, log_callback=None):
    """
    Esegue un test di un scheduled task senza aggiornare il database.
    Se esiste una sequenza di macro, esegue tutte le macro in sequenza con i tempi di attesa configurati.
    """
    try:
        task_id = task['id']
        task_name = task['nome']
        
        if log_callback:
            log_callback(f"🧪 Test esecuzione scheduled task '{task_name}' (ID: {task_id})")
        
        # Controlla se esiste una sequenza di macro per questo task
        macro_sequence = get_task_macro_sequence(task_id)
        
        if macro_sequence:
            # Esegui la sequenza di macro
            if log_callback:
                log_callback(f"📋 Test sequenza di {len(macro_sequence)} macro per il task '{task_name}'")
        else:
            # Retrocompatibilità: usa la macro_id dalla tabella ScheduledTasks
            macro_id = task.get('macro_id')
            if not macro_id:
                if log_callback:
                    log_callback(f"❌ Nessuna macro o sequenza trovata per il task '{task_name}'")
                return
            
            # Crea una sequenza temporanea con una sola macro (per retrocompatibilità)
            macro_metadata = get_macro_metadata_by_id(macro_id)
            if not macro_metadata:
                if log_callback:
                    log_callback(f"❌ Macro con ID {macro_id} non trovata per il task '{task_name}'")
                return
            
            macro_sequence = [{
                'macro_id': macro_id,
                'attesa_secondi': 0,
                'macro_nome': macro_metadata['nome'],
                'macro_eseguibile': macro_metadata['eseguibile']
            }]

        if not _reserve_execution_slot(f"test-{task_id}"):
            if log_callback:
                log_callback(f"⏸️ Test task '{task_name}' non avviato: un'altra esecuzione esclusiva è già in corso")
            return
        
        # Esegui tutte le macro in sequenza
        def execute_sequence():
            global currently_executing_task_id
            lock_acquired = False
            try:
                # Acquisisci il lock PRIMA di eseguire la prima macro
                # Questo impedisce ad altri task di partire
                if log_callback:
                    log_callback(f"🔒 Test task '{task_name}' acquisisce il lock per l'esecuzione esclusiva")
                
                task_execution_lock.acquire()
                lock_acquired = True
                currently_executing_task_id = task_id
                
                if log_callback:
                    log_callback(f"✅ Test task '{task_name}' ha acquisito il lock - inizio esecuzione esclusiva")
                
                task_stopped = False  # Flag per indicare se il task è stato fermato
                for idx, seq_item in enumerate(macro_sequence):
                    macro_id = seq_item['macro_id']
                    attesa_secondi = seq_item.get('attesa_secondi', 0)
                    macro_name = seq_item.get('macro_nome', f"ID:{macro_id}")
                    
                    # Attendi prima di eseguire questa macro (tranne la prima)
                    if idx > 0 and attesa_secondi > 0:
                        if log_callback:
                            log_callback(f"⏳ Attesa di {attesa_secondi} secondi prima della prossima macro...")
                        time.sleep(attesa_secondi)
                    
                    # Carica i metadati della macro
                    macro_metadata = get_macro_metadata_by_id(macro_id)
                    if not macro_metadata:
                        if log_callback:
                            log_callback(f"❌ Macro con ID {macro_id} non trovata per il task '{task_name}'")
                        continue
                    
                    # Carica gli eventi della macro
                    macro_events = load_macro_events(macro_id)
                    if not macro_events:
                        if log_callback:
                            log_callback(f"⚠️ Nessun evento trovato per la macro '{macro_metadata['nome']}' del task '{task_name}'")
                        continue
                    
                    target_exe = macro_metadata['eseguibile']
                    macro_name = macro_metadata['nome']
                    
                    if log_callback:
                        log_callback(f"📍 Test esecuzione macro {idx + 1}/{len(macro_sequence)}: '{macro_name}' su '{target_exe}' per il task '{task_name}'")
                    
                    # Verifica che la finestra dell'applicazione esista
                    window_rect = get_game_window_rect(target_exe)
                    if not window_rect:
                        # Finestra non trovata: ferma il task e logga l'errore
                        if log_callback:
                            log_callback(f"❌ Errore di esecuzione: finestra dell'applicazione '{target_exe}' non trovata per il task '{task_name}'. Test fermato.")
                        task_stopped = True
                        break  # Esce dal loop delle macro
                    
                    # Controlla se la finestra ha già il focus
                    current_foreground_process = get_foreground_process_name()
                    if not current_foreground_process or current_foreground_process.lower() != target_exe.lower():
                        # La finestra non ha il focus: porta la finestra in primo piano
                        if log_callback:
                            log_callback(f"🔄 Spostamento focus alla finestra '{target_exe}'...")
                        success = _attempt_bring_window_to_front(target_exe, log_callback)
                        if not success:
                            # Se non riesce a portare la finestra in primo piano, aspetta un po' e verifica di nuovo
                            time.sleep(0.5)
                            current_foreground_process = get_foreground_process_name()
                            if not current_foreground_process or current_foreground_process.lower() != target_exe.lower():
                                if log_callback:
                                    log_callback(f"⚠️ Impossibile portare '{target_exe}' in primo piano, ma procedo comunque con l'esecuzione")
                    
                    # Esegui la macro
                    play_macro_events(macro_events, target_exe, log_callback=log_callback, loop_enabled=False, loop_delay=0)
                
                # Dopo aver eseguito tutte le macro nella sequenza (solo se il task non è stato fermato)
                if not task_stopped:
                    if log_callback:
                        log_callback(f"✅ Test task '{task_name}' completato con successo")
                else:
                    if log_callback:
                        log_callback(f"🛑 Test task '{task_name}' fermato a causa di errore di esecuzione")
            except Exception as e:
                if log_callback:
                    log_callback(f"❌ Errore nell'esecuzione del test per il task '{task_name}': {e}")
            finally:
                # Rilascia sempre il lock quando il task finisce, anche in caso di errore
                if lock_acquired:
                    currently_executing_task_id = None
                    task_execution_lock.release()
                    if log_callback:
                        log_callback(f"🔓 Test task '{task_name}' ha rilasciato il lock - altri task possono ora partire")
                _release_execution_slot(f"test-{task_id}")
        
        # Esegui in un thread separato per non bloccare la GUI
        execution_thread = threading.Thread(target=execute_sequence, daemon=True, name=f"scheduled-task-test-{task_id}")
        execution_thread.start()
        
    except Exception as e:
        _release_execution_slot(f"test-{task['id']}")
        if log_callback:
            log_callback(f"❌ Errore critico nel test del scheduled task '{task['nome']}': {e}")
