"""Funzioni condivise di accesso e setup database."""

import logging
from pathlib import Path
import shutil
import sqlite3
from threading import Lock

from core.paths import (
    DB_PATH,
    LEGACY_DB_PATH,
    LEGACY_ROOT_DB_PATH,
    ensure_project_directories,
)

logger = logging.getLogger(__name__)
PROJECT_DB_PATH = DB_PATH
_SHARED_KNOWLEDGE_IMPORT_LOCK = Lock()
_SHARED_KNOWLEDGE_IMPORT_ATTEMPTED = False

SQLITE_TIMEOUT_SECONDS = 10.0
SQLITE_BUSY_TIMEOUT_MS = 10000


def _ensure_database_location():
    ensure_project_directories()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        for legacy_path in (LEGACY_DB_PATH, LEGACY_ROOT_DB_PATH):
            if legacy_path.exists():
                shutil.copy2(legacy_path, DB_PATH)
                break


def connect_db():
    _ensure_database_location()
    conn = sqlite3.connect(DB_PATH, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS};")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def get_db_path():
    """Restituisce il percorso assoluto del database principale."""
    _ensure_database_location()
    return str(DB_PATH)


def setup_main_table():
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Macro';")
        macro_table_exists = cursor.fetchone()

        if not macro_table_exists:
            cursor.execute(
                """
                CREATE TABLE Macro (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL UNIQUE,
                    descrizione TEXT,
                    eseguibile TEXT DEFAULT 'Doomsday.exe',
                    durata_sec INTEGER NOT NULL,
                    macro_kind TEXT DEFAULT 'standard',
                    is_protected INTEGER DEFAULT 0,
                    system_key TEXT,
                    system_payload TEXT,
                    data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_ultima_modifica TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        else:
            cursor.execute("PRAGMA table_info(Macro);")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]

            if "data_ultima_modifica" not in column_names:
                cursor.execute("ALTER TABLE Macro ADD COLUMN data_ultima_modifica TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
                print("Colonna 'data_ultima_modifica' aggiunta alla tabella Macro.")
            if "eseguibile" not in column_names:
                cursor.execute("ALTER TABLE Macro ADD COLUMN eseguibile TEXT DEFAULT 'Doomsday.exe';")
                print("Colonna 'eseguibile' aggiunta alla tabella Macro.")
            if "macro_kind" not in column_names:
                cursor.execute("ALTER TABLE Macro ADD COLUMN macro_kind TEXT DEFAULT 'standard';")
                print("Colonna 'macro_kind' aggiunta alla tabella Macro.")
            if "is_protected" not in column_names:
                cursor.execute("ALTER TABLE Macro ADD COLUMN is_protected INTEGER DEFAULT 0;")
                print("Colonna 'is_protected' aggiunta alla tabella Macro.")
            if "system_key" not in column_names:
                cursor.execute("ALTER TABLE Macro ADD COLUMN system_key TEXT;")
                print("Colonna 'system_key' aggiunta alla tabella Macro.")
            if "system_payload" not in column_names:
                cursor.execute("ALTER TABLE Macro ADD COLUMN system_payload TEXT;")
                print("Colonna 'system_payload' aggiunta alla tabella Macro.")

        conn.commit()
    except Exception as e:
        print(f"Errore durante l'inizializzazione della tabella Macro: {e}")
        conn.rollback()
    finally:
        conn.close()


def setup_scheduled_tasks_table():
    """Crea la tabella per gestire gli scheduled tasks."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ScheduledTasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                descrizione TEXT,
                macro_id INTEGER NOT NULL,
                schedulazione_tipo TEXT NOT NULL CHECK(schedulazione_tipo IN ('ora_fissa', 'intervallo')),
                ora_target TEXT,
                intervallo_ore INTEGER,
                intervallo_minuti INTEGER,
                attivo BOOLEAN DEFAULT 1,
                data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_ultima_esecuzione TIMESTAMP,
                prossima_esecuzione TIMESTAMP,
                stato TEXT DEFAULT 'stopped' CHECK(stato IN ('running', 'stopped', 'completed')),
                terminazione_tipo TEXT CHECK(terminazione_tipo IN ('nessuna', 'esecuzioni', 'durata_ore', 'durata_minuti')),
                terminazione_valore INTEGER,
                data_inizio_schedulazione TIMESTAMP,
                conteggio_esecuzioni INTEGER DEFAULT 0,
                FOREIGN KEY (macro_id) REFERENCES Macro(id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()

        cursor.execute("PRAGMA table_info(ScheduledTasks);")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "stato" not in column_names:
            cursor.execute("ALTER TABLE ScheduledTasks ADD COLUMN stato TEXT DEFAULT 'stopped' CHECK(stato IN ('running', 'stopped', 'completed'));")
            print("Colonna 'stato' aggiunta alla tabella ScheduledTasks.")
        if "terminazione_tipo" not in column_names:
            cursor.execute("ALTER TABLE ScheduledTasks ADD COLUMN terminazione_tipo TEXT CHECK(terminazione_tipo IN ('nessuna', 'esecuzioni', 'durata_ore', 'durata_minuti'));")
            print("Colonna 'terminazione_tipo' aggiunta alla tabella ScheduledTasks.")
        if "terminazione_valore" not in column_names:
            cursor.execute("ALTER TABLE ScheduledTasks ADD COLUMN terminazione_valore INTEGER;")
            print("Colonna 'terminazione_valore' aggiunta alla tabella ScheduledTasks.")
        if "data_inizio_schedulazione" not in column_names:
            cursor.execute("ALTER TABLE ScheduledTasks ADD COLUMN data_inizio_schedulazione TIMESTAMP;")
            print("Colonna 'data_inizio_schedulazione' aggiunta alla tabella ScheduledTasks.")
        if "conteggio_esecuzioni" not in column_names:
            cursor.execute("ALTER TABLE ScheduledTasks ADD COLUMN conteggio_esecuzioni INTEGER DEFAULT 0;")
            print("Colonna 'conteggio_esecuzioni' aggiunta alla tabella ScheduledTasks.")

        conn.commit()
        print("Tabella ScheduledTasks creata o verificata.")
    except Exception as e:
        print(f"Errore durante l'inizializzazione della tabella ScheduledTasks: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()


def setup_task_macro_sequence_table():
    """Crea la tabella per gestire le sequenze di macro per ogni scheduled task."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS TaskMacroSequence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                macro_id INTEGER NOT NULL,
                ordine INTEGER NOT NULL,
                attesa_secondi INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES ScheduledTasks(id) ON DELETE CASCADE,
                FOREIGN KEY (macro_id) REFERENCES Macro(id) ON DELETE CASCADE,
                UNIQUE(task_id, ordine)
            );
            """
        )
        conn.commit()
        print("Tabella TaskMacroSequence creata o verificata.")
    except Exception as e:
        print(f"Errore durante l'inizializzazione della tabella TaskMacroSequence: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()


def setup_game_elements_table():
    """Crea la tabella per gestire gli elementi grafici del gioco."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS GameElements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                descrizione TEXT,
                immagine BLOB NOT NULL,
                formato_immagine TEXT NOT NULL,
                data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_ultima_modifica TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
        print("Tabella GameElements creata o verificata.")
    except Exception as e:
        print(f"Errore durante l'inizializzazione della tabella GameElements: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()
    global _SHARED_KNOWLEDGE_IMPORT_ATTEMPTED
    if Path(DB_PATH).resolve() == Path(PROJECT_DB_PATH).resolve():
        try:
            with _SHARED_KNOWLEDGE_IMPORT_LOCK:
                if _SHARED_KNOWLEDGE_IMPORT_ATTEMPTED:
                    return
                _SHARED_KNOWLEDGE_IMPORT_ATTEMPTED = True
            from services.shared_knowledge_import_service import import_shared_game_elements

            result = import_shared_game_elements()
            if result["imported"] or result["updated"]:
                logger.info(
                    "Knowledge visuali condivise: importati %s, aggiornati %s, immagini mancanti %s.",
                    result["imported"],
                    result["updated"],
                    result["missing_images"],
                )
        except Exception:
            logger.exception("Import della knowledge visuale condivisa non riuscito.")


def setup_ui_graph_macro_links_table():
    """Crea la tabella che collega nodi del grafo UI e intenti alle macro disponibili."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS UIGraphMacroLinks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                graph_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                intent_key TEXT,
                relation_type TEXT NOT NULL DEFAULT 'candidate' CHECK(relation_type IN ('candidate', 'preferred', 'fallback', 'recovery', 'composed_step')),
                macro_id INTEGER,
                macro_name_snapshot TEXT,
                priority INTEGER NOT NULL DEFAULT 100,
                enabled INTEGER NOT NULL DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (macro_id) REFERENCES Macro(id) ON DELETE SET NULL
            );
            """
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ui_graph_macro_links_unique ON UIGraphMacroLinks (graph_id, node_id, COALESCE(intent_key, ''), relation_type, COALESCE(macro_id, -1));"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_ui_graph_macro_links_lookup ON UIGraphMacroLinks (graph_id, node_id, intent_key, enabled, priority);"
        )
        conn.commit()
    except Exception as e:
        print(f"Errore durante l'inizializzazione della tabella UIGraphMacroLinks: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()


def setup_backup_table():
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS MacroBackup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                macro_id INTEGER NOT NULL,
                backup_name TEXT NOT NULL,
                backup_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                original_macro_name TEXT NOT NULL,
                FOREIGN KEY (macro_id) REFERENCES Macro(id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()
    except Exception as e:
        print(f"Errore durante l'inizializzazione della tabella MacroBackup: {e}")
        conn.rollback()
    finally:
        conn.close()


__all__ = [
    "connect_db",
    "get_db_path",
    "setup_backup_table",
    "setup_game_elements_table",
    "setup_main_table",
    "setup_scheduled_tasks_table",
    "setup_task_macro_sequence_table",
    "setup_ui_graph_macro_links_table",
]
