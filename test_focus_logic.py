#!/usr/bin/env python3
"""
Script di test per verificare la logica del monitoraggio del focus
"""

import win32gui
import win32process
import psutil

def get_foreground_process_name():
    """Restituisce il nome del processo della finestra in primo piano."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        return proc.name()
    except (win32gui.error, psutil.NoSuchProcess):
        return None

def is_target_window_active(target_exe):
    """Verifica se la finestra target è attualmente attiva"""
    if not target_exe:
        return False
    
    try:
        # Ottieni la finestra attualmente attiva
        active_window = win32gui.GetForegroundWindow()
        if active_window:
            # Controlla se è la finestra target
            _, pid = win32process.GetWindowThreadProcessId(active_window)
            proc = psutil.Process(pid)
            return proc.name().lower() == target_exe.lower()
    except Exception as e:
        print(f"Errore nel controllo della finestra target: {e}")
    
    return False

def test_focus_logic():
    """Testa la logica del monitoraggio del focus"""
    print("🔍 Test della logica del monitoraggio del focus")
    print("=" * 50)
    
    # Test 1: Verifica processo attuale
    current_process = get_foreground_process_name()
    print(f"📱 Processo attualmente in primo piano: {current_process}")
    
    # Test 2: Verifica se la finestra target è attiva
    target_exe = "Doomsday.exe"  # Sostituisci con il tuo eseguibile target
    is_target_active = is_target_window_active(target_exe)
    print(f"🎯 Finestra target '{target_exe}' è attiva: {is_target_active}")
    
    # Test 3: Simula diversi scenari
    print("\n🧪 Simulazione scenari:")
    
    # Scenario 1: Macro in riproduzione, finestra target attiva
    playing_flag = True
    current_target_exe = target_exe
    if playing_flag and current_target_exe:
        if is_target_window_active(current_target_exe):
            print("✅ SCENARIO 1: Macro in riproduzione + finestra target attiva = CONTINUA")
        else:
            print("⚠️ SCENARIO 1: Macro in riproduzione + finestra target NON attiva = INTERROMPI")
    
    # Scenario 2: Macro in riproduzione, finestra target NON attiva
    # Simula cambiando il target
    current_target_exe = "notepad.exe"  # Simula un target diverso
    if playing_flag and current_target_exe:
        if is_target_window_active(current_target_exe):
            print("✅ SCENARIO 2: Macro in riproduzione + finestra target attiva = CONTINUA")
        else:
            print("⚠️ SCENARIO 2: Macro in riproduzione + finestra target NON attiva = INTERROMPI")
    
    # Scenario 3: Registrazione in corso, perde focus
    recording_flag = True
    current_target_exe = target_exe
    print("🔴 SCENARIO 3: Registrazione in corso + perde focus = INTERROMPI SEMPRE")
    
    # Scenario 4: Nessuna operazione attiva
    playing_flag = False
    recording_flag = False
    current_target_exe = None
    print("ℹ️ SCENARIO 4: Nessuna operazione attiva + perde focus = SOLO LOG")
    
    print("\n" + "=" * 50)
    print("✅ Test completato!")

if __name__ == "__main__":
    test_focus_logic()
