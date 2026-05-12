#!/usr/bin/env python3
"""
Script per verificare e riparare le macro esistenti nel database.
Identifica e risolve problemi comuni che impediscono la riproduzione delle macro.
"""

import sqlite3
import json
import time
import sys
import os
from pathlib import Path

# Aggiungi la directory corrente al path per importare i moduli
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from repositories.database import connect_db, get_db_path
from repositories.macro_repository import get_all_macros, get_macro_metadata_by_id, load_macro_events

def check_macro_integrity():
    """Verifica l'integrità di tutte le macro nel database."""
    print("🔍 Verifica integrità macro...")
    
    try:
        macros = get_all_macros()
        if not macros:
            print("⚠️ Nessuna macro trovata nel database")
            return []
        
        print(f"📊 Trovate {len(macros)} macro da verificare")
        
        problematic_macros = []
        
        for macro in macros:
            macro_id = macro['id']
            macro_name = macro['nome']
            target_exe = macro['eseguibile']
            
            print(f"\n🔍 Verifica macro: {macro_name} (ID: {macro_id})")
            
            # Verifica 1: Eventi presenti
            events = load_macro_events(macro_id)
            if not events:
                print(f"❌ Macro '{macro_name}' non ha eventi - impossibile riprodurre")
                problematic_macros.append({
                    'id': macro_id,
                    'name': macro_name,
                    'issue': 'no_events',
                    'description': 'Macro senza eventi'
                })
                continue
            
            print(f"✅ Eventi presenti: {len(events)}")
            
            # Verifica 2: Struttura eventi
            invalid_events = []
            for i, event in enumerate(events):
                if not validate_event_structure(event, i):
                    invalid_events.append((i, event))
            
            if invalid_events:
                print(f"⚠️ Macro '{macro_name}' ha {len(invalid_events)} eventi malformattati")
                problematic_macros.append({
                    'id': macro_id,
                    'name': macro_name,
                    'issue': 'invalid_events',
                    'description': f'{len(invalid_events)} eventi malformattati',
                    'invalid_events': invalid_events
                })
            else:
                print(f"✅ Struttura eventi valida")
            
            # Verifica 3: Coordinate mouse valide
            mouse_events = [e for e in events if e.get('type') == 'mouse']
            if mouse_events:
                invalid_coords = []
                for i, event in enumerate(mouse_events):
                    if not validate_mouse_coordinates(event, i):
                        invalid_coords.append((i, event))
                
                if invalid_coords:
                    print(f"⚠️ Macro '{macro_name}' ha {len(invalid_coords)} eventi mouse con coordinate invalide")
                    problematic_macros.append({
                        'id': macro_id,
                        'name': macro_name,
                        'issue': 'invalid_coordinates',
                        'description': f'{len(invalid_coords)} coordinate mouse invalide',
                        'invalid_coords': invalid_coords
                    })
                else:
                    print(f"✅ Coordinate mouse valide")
            
            # Verifica 4: Eseguibile target valido
            if not target_exe or target_exe.strip() == '':
                print(f"❌ Macro '{macro_name}' ha eseguibile target vuoto")
                problematic_macros.append({
                    'id': macro_id,
                    'name': macro_name,
                    'issue': 'invalid_target',
                    'description': 'Eseguibile target vuoto o invalido'
                })
            else:
                print(f"✅ Target: {target_exe}")
        
        return problematic_macros
        
    except Exception as e:
        print(f"❌ Errore durante verifica integrità: {e}")
        return []

def validate_event_structure(event, index):
    """Valida la struttura di un singolo evento."""
    required_fields = ['time', 'type', 'event']
    
    for field in required_fields:
        if field not in event:
            print(f"   ❌ Evento {index}: campo mancante '{field}'")
            return False
    
    # Validazione tipo evento
    event_type = event.get('type')
    if event_type not in ['key', 'mouse', 'delay', 'window_focus']:
        print(f"   ❌ Evento {index}: tipo evento invalido '{event_type}'")
        return False
    
    # Validazione campi specifici per tipo
    if event_type == 'key':
        if 'name' not in event:
            print(f"   ❌ Evento {index}: evento tastiera senza nome tasto")
            return False
    elif event_type == 'mouse':
        if 'event' not in event:
            print(f"   ❌ Evento {index}: evento mouse senza tipo azione")
            return False
    
    return True

def validate_mouse_coordinates(event, index):
    """Valida le coordinate del mouse per un evento."""
    # Verifica coordinate normalizzate
    norm_x = event.get('normalized_x')
    norm_y = event.get('normalized_y')
    
    if norm_x is not None and (norm_x < 0 or norm_x > 1):
        print(f"   ❌ Evento {index}: coordinate X normalizzate invalide: {norm_x}")
        return False
    
    if norm_y is not None and (norm_y < 0 or norm_y > 1):
        print(f"   ❌ Evento {index}: coordinate Y normalizzate invalide: {norm_y}")
        return False
    
    # Verifica coordinate assolute se presenti
    abs_x = event.get('x')
    abs_y = event.get('y')
    
    if abs_x is not None and (abs_x < 0 or abs_x > 10000):  # Limite ragionevole per coordinate schermo
        print(f"   ❌ Evento {index}: coordinate X assolute invalide: {abs_x}")
        return False
    
    if abs_y is not None and (abs_y < 0 or abs_y > 10000):
        print(f"   ❌ Evento {index}: coordinate Y assolute invalide: {abs_y}")
        return False
    
    return True

def repair_macro_events(macro_id, events):
    """Ripara gli eventi di una macro rimuovendo quelli invalidi."""
    print(f"🔧 Riparazione eventi macro ID: {macro_id}")
    
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        # Rimuovi tutti gli eventi esistenti
        table_name = f"MacroEvent_{macro_id}"
        cursor.execute(f"DELETE FROM {table_name}")
        
        # Filtra e ripara gli eventi
        repaired_events = []
        for event in events:
            if validate_event_structure(event, 0) and validate_mouse_coordinates(event, 0):
                # Normalizza le coordinate se necessario
                if event.get('type') == 'mouse':
                    event = normalize_mouse_coordinates(event)
                repaired_events.append(event)
        
        # Salva gli eventi riparati
        if repaired_events:
            for event in repaired_events:
                cursor.execute(f"""
                    INSERT INTO {table_name} 
                    (time, type, event, name, button, x, y, delta, is_pressed, normalized_x, normalized_y)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.get('time', 0),
                    event.get('type', ''),
                    event.get('event', ''),
                    event.get('name', ''),
                    event.get('button', ''),
                    event.get('x', 0),
                    event.get('y', 0),
                    event.get('delta', 0),
                    event.get('is_pressed', False),
                    event.get('normalized_x', 0.0),
                    event.get('normalized_y', 0.0)
                ))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Eventi riparati: {len(repaired_events)}/{len(events)}")
        return len(repaired_events)
        
    except Exception as e:
        print(f"❌ Errore durante riparazione: {e}")
        return 0

def normalize_mouse_coordinates(event):
    """Normalizza le coordinate del mouse se necessario."""
    if event.get('type') != 'mouse':
        return event
    
    # Se abbiamo coordinate assolute ma non normalizzate, calcolale
    if 'x' in event and 'y' in event and 'normalized_x' not in event:
        # Usa coordinate di default per una finestra 800x600
        # In produzione, queste dovrebbero essere le dimensioni reali della finestra target
        default_width = 800
        default_height = 600
        
        x = event.get('x', 0)
        y = event.get('y', 0)
        
        event['normalized_x'] = max(0.0, min(1.0, x / default_width))
        event['normalized_y'] = max(0.0, min(1.0, y / default_height))
    
    # Se abbiamo coordinate normalizzate ma non assolute, calcolale
    elif 'normalized_x' in event and 'normalized_y' in event and 'x' not in event:
        default_width = 800
        default_height = 600
        
        norm_x = event.get('normalized_x', 0.0)
        norm_y = event.get('normalized_y', 0.0)
        
        event['x'] = int(norm_x * default_width)
        event['y'] = int(norm_y * default_height)
    
    return event

def repair_all_macros():
    """Ripara tutte le macro problematiche trovate."""
    print("🔧 RIPARAZIONE MACRO PROBLEMATICHE")
    print("=" * 50)
    
    # Verifica integrità
    problematic_macros = check_macro_integrity()
    
    if not problematic_macros:
        print("\n✅ Nessuna macro problematica trovata!")
        return
    
    print(f"\n⚠️ Trovate {len(problematic_macros)} macro problematiche")
    
    # Chiedi conferma per la riparazione
    response = input("\n🔧 Vuoi procedere con la riparazione automatica? (y/N): ").strip().lower()
    if response != 'y':
        print("❌ Riparazione annullata dall'utente")
        return
    
    # Ripara ogni macro problematica
    repaired_count = 0
    for macro in problematic_macros:
        macro_id = macro['id']
        macro_name = macro['name']
        issue = macro['issue']
        
        print(f"\n🔧 Riparazione macro: {macro_name}")
        print(f"   Problema: {macro['description']}")
        
        if issue in ['no_events', 'invalid_events', 'invalid_coordinates']:
            # Carica gli eventi attuali
            events = load_macro_events(macro_id)
            if events:
                # Ripara gli eventi
                repaired_count += repair_macro_events(macro_id, events)
            else:
                print(f"   ❌ Impossibile riparare: nessun evento da riparare")
        
        elif issue == 'invalid_target':
            # Imposta un target di default
            try:
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("UPDATE Macro SET eseguibile = ? WHERE id = ?", ("Doomsday.exe", macro_id))
                conn.commit()
                conn.close()
                print(f"   ✅ Target impostato a 'Doomsday.exe'")
                repaired_count += 1
            except Exception as e:
                print(f"   ❌ Errore riparazione target: {e}")
    
    print(f"\n✅ Riparazione completata: {repaired_count} macro riparate")

def create_backup_macro(macro_id):
    """Crea un backup di una macro prima della riparazione."""
    try:
        macro_metadata = get_macro_metadata_by_id(macro_id)
        if not macro_metadata:
            return False
        
        events = load_macro_events(macro_id)
        if not events:
            return False
        
        # Crea nome backup
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{macro_metadata['nome']}_{timestamp}"
        
        # Salva backup
        conn = connect_db()
        cursor = conn.cursor()
        
        # Inserisci record backup
        cursor.execute("""
            INSERT INTO MacroBackup (macro_id, backup_name, original_macro_name)
            VALUES (?, ?, ?)
        """, (macro_id, backup_name, macro_metadata['nome']))
        
        backup_id = cursor.lastrowid
        
        # Crea tabella backup eventi
        backup_table = f"MacroEventBackup_{backup_id}"
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {backup_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time INTEGER,
                type TEXT,
                event TEXT,
                name TEXT,
                button TEXT,
                x REAL,
                y REAL,
                delta INTEGER,
                is_pressed BOOLEAN,
                normalized_x REAL,
                normalized_y REAL
            )
        """)
        
        # Copia eventi
        for event in events:
            cursor.execute(f"""
                INSERT INTO {backup_table} 
                (time, type, event, name, button, x, y, delta, is_pressed, normalized_x, normalized_y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.get('time', 0),
                event.get('type', ''),
                event.get('event', ''),
                event.get('name', ''),
                event.get('button', ''),
                event.get('x', 0),
                event.get('y', 0),
                event.get('delta', 0),
                event.get('is_pressed', False),
                event.get('normalized_x', 0.0),
                event.get('normalized_y', 0.0)
            ))
        
        conn.commit()
        conn.close()
        
        print(f"   💾 Backup creato: {backup_name}")
        return True
        
    except Exception as e:
        print(f"   ❌ Errore creazione backup: {e}")
        return False

def main():
    """Funzione principale."""
    print("🚀 STRUMENTO RIPARAZIONE MACRO")
    print("=" * 50)
    
    # Verifica che il database esista
    db_path = Path(get_db_path())
    if not db_path.exists():
        print(f"❌ Database '{db_path}' non trovato!")
        print("💡 Assicurati che il database principale dell'applicazione sia presente")
        return
    
    # Menu principale
    while True:
        print("\n📋 Menu opzioni:")
        print("1. Verifica integrità macro")
        print("2. Ripara macro problematiche")
        print("3. Crea backup macro")
        print("4. Esci")
        
        choice = input("\n🔧 Scegli un'opzione (1-4): ").strip()
        
        if choice == '1':
            check_macro_integrity()
        elif choice == '2':
            repair_all_macros()
        elif choice == '3':
            macro_id = input("📝 Inserisci ID macro per backup: ").strip()
            try:
                macro_id = int(macro_id)
                create_backup_macro(macro_id)
            except ValueError:
                print("❌ ID macro non valido")
        elif choice == '4':
            print("👋 Uscita...")
            break
        else:
            print("❌ Opzione non valida")

if __name__ == "__main__":
    main()
