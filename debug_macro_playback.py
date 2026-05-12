#!/usr/bin/env python3
"""
Script di diagnostica per identificare problemi con la riproduzione delle macro.
Esegui questo script per verificare che le macro vengano caricate e riprodotte correttamente.
"""

import json
import time
import sys
import os

# Aggiungi la directory corrente al path per importare i moduli
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from repositories.database import connect_db, get_db_path
from repositories.macro_repository import get_all_macros, get_macro_metadata_by_id, load_macro_events
from macro_controller import get_game_window_rect, wait_for_app_window, play_macro_events

def test_database_connection():
    """Testa la connessione al database e verifica la struttura delle tabelle."""
    print("🔍 Test connessione database...")
    
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        # Verifica tabella Macro
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Macro';")
        if cursor.fetchone():
            print("✅ Tabella Macro trovata")
            
            # Conta le macro
            cursor.execute("SELECT COUNT(*) FROM Macro;")
            macro_count = cursor.fetchone()[0]
            print(f"📊 Numero totale di macro: {macro_count}")
            
            # Mostra le prime 5 macro
            cursor.execute("SELECT id, nome, eseguibile, durata_sec FROM Macro LIMIT 5;")
            macros = cursor.fetchall()
            print("📋 Prime 5 macro:")
            for macro in macros:
                print(f"   ID: {macro[0]}, Nome: {macro[1]}, Exe: {macro[2]}, Durata: {macro[3]}s")
        else:
            print("❌ Tabella Macro non trovata")
            
        # Verifica tabelle eventi
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'MacroEvent_%';")
        event_tables = cursor.fetchall()
        print(f"📊 Tabelle eventi trovate: {len(event_tables)}")
        print(f"📁 Database in uso: {get_db_path()}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Errore connessione database: {e}")
        return False

def test_macro_loading():
    """Testa il caricamento delle macro dal database."""
    print("\n🔍 Test caricamento macro...")
    
    try:
        macros = get_all_macros()
        print(f"✅ Caricate {len(macros)} macro dal database")
        
        if macros:
            # Testa il caricamento degli eventi per la prima macro
            first_macro = macros[0]
            macro_id = first_macro['id']
            macro_name = first_macro['nome']
            
            print(f"🧪 Test caricamento eventi per macro: {macro_name} (ID: {macro_id})")
            
            events = load_macro_events(macro_id)
            print(f"📊 Eventi caricati: {len(events)}")
            
            if events:
                print("📋 Primi 3 eventi:")
                for i, event in enumerate(events[:3]):
                    print(f"   {i+1}. Tipo: {event.get('type', 'N/A')}, Evento: {event.get('event', 'N/A')}")
                    if event.get('type') == 'key':
                        print(f"      Tasto: {event.get('name', 'N/A')}")
                    elif event.get('type') == 'mouse':
                        print(f"      Pulsante: {event.get('button', 'N/A')}, Pos: ({event.get('x', 'N/A')}, {event.get('y', 'N/A')}")
            
            return first_macro, events
        else:
            print("⚠️ Nessuna macro trovata nel database")
            return None, None
            
    except Exception as e:
        print(f"❌ Errore caricamento macro: {e}")
        return None, None

def test_window_detection(target_exe):
    """Testa il rilevamento della finestra target."""
    print(f"\n🔍 Test rilevamento finestra per: {target_exe}")
    
    try:
        # Test get_game_window_rect
        print("🧪 Test get_game_window_rect...")
        rect = get_game_window_rect(target_exe)
        if rect:
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top
            print(f"✅ Finestra trovata: ({left}, {top}) - ({right}, {bottom})")
            print(f"📏 Dimensioni: {width}x{height}")
        else:
            print(f"❌ Finestra non trovata per: {target_exe}")
            print("💡 Assicurati che l'applicazione sia aperta e visibile")
            return False
        
        # Test wait_for_app_window (con timeout)
        print("🧪 Test wait_for_app_window (con timeout di 5 secondi)...")
        try:
            # Usa un thread con timeout per non bloccare
            import threading
            import queue
            
            result_queue = queue.Queue()
            
            def test_wait():
                try:
                    wait_for_app_window(target_exe, lambda msg: print(f"   {msg}"), max_wait_time=5, check_recording_flag=False)
                    result_queue.put(("success", "Finestra attivata"))
                except Exception as e:
                    result_queue.put(("error", str(e)))
            
            thread = threading.Thread(target=test_wait)
            thread.daemon = True
            thread.start()
            
            # Attendi massimo 5 secondi
            thread.join(timeout=5)
            
            if thread.is_alive():
                print("⏰ Timeout raggiunto - finestra non attivata entro 5 secondi")
                return False
            else:
                result_type, result_msg = result_queue.get_nowait()
                if result_type == "success":
                    print(f"✅ {result_msg}")
                    return True
                else:
                    print(f"❌ Errore: {result_msg}")
                    return False
                    
        except Exception as e:
            print(f"❌ Errore test wait_for_app_window: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Errore test rilevamento finestra: {e}")
        return False

def test_macro_playback(macro_metadata, events, target_exe):
    """Testa la riproduzione di una macro."""
    print(f"\n🔍 Test riproduzione macro: {macro_metadata['nome']}")
    
    if not events:
        print("❌ Nessun evento da riprodurre")
        return False
    
    print(f"📊 Eventi da riprodurre: {len(events)}")
    print(f"🎯 Target: {target_exe}")
    
    # Verifica che la finestra sia attiva prima di testare
    print("🧪 Verifica finestra attiva...")
    if not test_window_detection(target_exe):
        print("❌ Finestra target non disponibile per il test")
        return False
    
    # Test riproduzione con timeout
    print("🧪 Test riproduzione macro (con timeout di 10 secondi)...")
    
    try:
        import threading
        import queue
        
        result_queue = queue.Queue()
        
        def test_playback():
            try:
                def log_callback(msg, level="INFO"):
                    print(f"   [PLAYBACK] {msg}")
                
                play_macro_events(events, target_exe, log_callback=log_callback, loop_enabled=False)
                result_queue.put(("success", "Riproduzione completata"))
            except Exception as e:
                result_queue.put(("error", str(e)))
        
        thread = threading.Thread(target=test_playback)
        thread.daemon = True
        thread.start()
        
        # Attendi massimo 10 secondi
        thread.join(timeout=10)
        
        if thread.is_alive():
            print("⏰ Timeout raggiunto - riproduzione non completata entro 10 secondi")
            return False
        else:
            try:
                result_type, result_msg = result_queue.get_nowait()
                if result_type == "success":
                    print(f"✅ {result_msg}")
                    return True
                else:
                    print(f"❌ Errore riproduzione: {result_msg}")
                    return False
            except queue.Empty:
                print("❌ Nessun risultato dalla riproduzione")
                return False
                
    except Exception as e:
        print(f"❌ Errore test riproduzione: {e}")
        return False

def main():
    """Funzione principale di diagnostica."""
    print("🚀 DIAGNOSTICA MACRO PLAYBACK")
    print("=" * 50)
    
    # Test 1: Connessione database
    if not test_database_connection():
        print("\n❌ Test database fallito - impossibile continuare")
        return
    
    # Test 2: Caricamento macro
    macro_metadata, events = test_macro_loading()
    if not macro_metadata or not events:
        print("\n❌ Test caricamento macro fallito - impossibile continuare")
        return
    
    # Test 3: Rilevamento finestra
    target_exe = macro_metadata['eseguibile']
    if not test_window_detection(target_exe):
        print(f"\n❌ Test rilevamento finestra fallito per: {target_exe}")
        print("💡 Soluzioni possibili:")
        print("   1. Assicurati che l'applicazione sia aperta")
        print("   2. Verifica che il nome dell'eseguibile sia corretto")
        print("   3. Controlla che la finestra sia visibile e non minimizzata")
        return
    
    # Test 4: Riproduzione macro
    if test_macro_playback(macro_metadata, events, target_exe):
        print("\n✅ Tutti i test completati con successo!")
        print("💡 La riproduzione delle macro dovrebbe funzionare correttamente")
    else:
        print("\n❌ Test riproduzione macro fallito")
        print("💡 Possibili problemi:")
        print("   1. Eventi macro corrotti o malformattati")
        print("   2. Problemi con gli hook di tastiera/mouse")
        print("   3. Conflitti con altre applicazioni")
        print("   4. Permessi insufficienti per l'input simulation")

if __name__ == "__main__":
    main()
