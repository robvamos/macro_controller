"""Repository per macro ed eventi associati."""

import datetime
import json
import re
import sqlite3

from repositories.database import connect_db


SYSTEM_MACRO_KIND = "system"
STANDARD_MACRO_KIND = "standard"
EVENT_METADATA_COLUMNS = (
    ("game_element_id", "INTEGER"),
    ("previous_game_element_id", "INTEGER"),
    ("ui_graph_id", "TEXT"),
    ("ui_node_id", "TEXT"),
)


def _create_events_table(macro_id, cursor):
    table_name = f"MacroEvent_{macro_id}"
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
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
            normalized_y REAL,
            game_element_id INTEGER,
            previous_game_element_id INTEGER,
            ui_graph_id TEXT,
            ui_node_id TEXT
        );
        """
    )
    _ensure_event_metadata_columns(table_name, cursor)


def _create_backup_events_table(backup_id, cursor):
    table_name = f"MacroEventBackup_{backup_id}"
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
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
            normalized_y REAL,
            game_element_id INTEGER,
            previous_game_element_id INTEGER,
            ui_graph_id TEXT,
            ui_node_id TEXT
        );
        """
    )
    _ensure_event_metadata_columns(table_name, cursor)


def _ensure_event_metadata_columns(table_name, cursor):
    cursor.execute(f"PRAGMA table_info({table_name});")
    column_names = {row[1] for row in cursor.fetchall()}
    for column_name, column_type in EVENT_METADATA_COLUMNS:
        if column_name not in column_names:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};")


def _save_events_to_table(table_name, events_data, cursor):
    _ensure_event_metadata_columns(table_name, cursor)
    for event in events_data:
        is_pressed_val = 1 if event.get("is_pressed") else 0
        cursor.execute(
            f"""
            INSERT INTO {table_name} (
                time, type, event, name, button, x, y, delta, is_pressed, normalized_x, normalized_y,
                game_element_id, previous_game_element_id, ui_graph_id, ui_node_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                event.get("time"),
                event.get("type"),
                event.get("event"),
                event.get("name"),
                event.get("button"),
                event.get("x"),
                event.get("y"),
                event.get("delta"),
                is_pressed_val,
                event.get("normalized_x"),
                event.get("normalized_y"),
                event.get("game_element_id"),
                event.get("previous_game_element_id"),
                event.get("ui_graph_id"),
                event.get("ui_node_id"),
            ),
        )


def _copy_events_between_tables(source_table, dest_table, cursor):
    _ensure_event_metadata_columns(source_table, cursor)
    _ensure_event_metadata_columns(dest_table, cursor)
    cursor.execute(
        f"""
        SELECT time, type, event, name, button, x, y, delta, is_pressed, normalized_x, normalized_y,
               game_element_id, previous_game_element_id, ui_graph_id, ui_node_id
        FROM {source_table}
        ORDER BY time;
        """
    )
    events = cursor.fetchall()
    for row in events:
        cursor.execute(
            f"""
            INSERT INTO {dest_table} (
                time, type, event, name, button, x, y, delta, is_pressed, normalized_x, normalized_y,
                game_element_id, previous_game_element_id, ui_graph_id, ui_node_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            row,
        )


def get_all_macros():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome, descrizione, durata_sec, eseguibile, macro_kind, is_protected, system_key, system_payload, data_creazione, data_ultima_modifica FROM Macro ORDER BY is_protected DESC, data_ultima_modifica DESC, data_creazione DESC;"
    )
    macros = []
    for row in cursor.fetchall():
        macros.append(
            {
                "id": row[0],
                "nome": row[1],
                "descrizione": row[2],
                "durata_sec": row[3],
                "eseguibile": row[4],
                "macro_kind": row[5] or STANDARD_MACRO_KIND,
                "is_protected": bool(row[6]),
                "system_key": row[7],
                "system_payload": _decode_system_payload(row[8]),
                "data_creazione": row[9],
                "data_ultima_modifica": row[10],
            }
        )
    conn.close()
    return macros


def get_macro_metadata_by_name(macro_name):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome, descrizione, durata_sec, eseguibile, macro_kind, is_protected, system_key, system_payload, data_creazione, data_ultima_modifica FROM Macro WHERE nome = ?",
        (macro_name,),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "nome": row[1],
            "descrizione": row[2],
            "durata_sec": row[3],
            "eseguibile": row[4],
            "macro_kind": row[5] or STANDARD_MACRO_KIND,
            "is_protected": bool(row[6]),
            "system_key": row[7],
            "system_payload": _decode_system_payload(row[8]),
            "data_creazione": row[9],
            "data_ultima_modifica": row[10],
        }
    return None


def get_macro_metadata_by_id(macro_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome, descrizione, durata_sec, eseguibile, macro_kind, is_protected, system_key, system_payload, data_creazione, data_ultima_modifica FROM Macro WHERE id = ?",
        (macro_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "nome": row[1],
            "descrizione": row[2],
            "durata_sec": row[3],
            "eseguibile": row[4],
            "macro_kind": row[5] or STANDARD_MACRO_KIND,
            "is_protected": bool(row[6]),
            "system_key": row[7],
            "system_payload": _decode_system_payload(row[8]),
            "data_creazione": row[9],
            "data_ultima_modifica": row[10],
        }
    return None


def _decode_system_payload(payload):
    if not payload:
        return None
    try:
        return json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return None


def _encode_system_payload(payload):
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False)


def salva_macro_test(
    nome_macro,
    descrizione,
    durata_sec,
    eseguibile,
    events,
    log_callback=None,
    macro_kind=STANDARD_MACRO_KIND,
    is_protected=False,
    system_key=None,
    system_payload=None,
):
    if log_callback:
        log_callback(
            f"DEBUG: Dentro salva_macro_test. Tipo di 'events': {type(events)}. Lunghezza: {len(events) if isinstance(events, list) else 'N/A'}",
            "DEBUG",
        )
        if not isinstance(events, list):
            log_callback(
                f"ERRORE GRAVE: 'events' non è una lista al suo arrivo in salva_macro_test! Tipo: {type(events)}",
                "ERROR",
            )

    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM Macro WHERE nome = ?", (nome_macro,))
        if cursor.fetchone():
            raise ValueError(f"Una macro con il nome '{nome_macro}' esiste già. Scegli un nome diverso.")

        cursor.execute(
            """
            INSERT INTO Macro (nome, descrizione, durata_sec, eseguibile, macro_kind, is_protected, system_key, system_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                nome_macro,
                descrizione,
                durata_sec,
                eseguibile,
                macro_kind,
                1 if is_protected else 0,
                system_key,
                _encode_system_payload(system_payload),
            ),
        )
        macro_id = cursor.lastrowid

        _create_events_table(macro_id, cursor)

        if log_callback:
            log_callback(
                f"DEBUG: Prima di save_events_to_table. Tipo di 'events': {type(events)}. Lunghezza: {len(events) if isinstance(events, list) else 'N/A'}",
                "DEBUG",
            )

        _save_events_to_table(f"MacroEvent_{macro_id}", events, cursor)

        conn.commit()
        if log_callback:
            log_callback(f"Macro '{nome_macro}' salvata con ID {macro_id} e {len(events)} eventi.", "INFO")
        return macro_id
    except Exception as e:
        conn.rollback()
        if log_callback:
            log_callback(f"Errore DB in salva_macro_test: {e}", "ERROR")
            log_callback(f"DEBUG: Tipo di eccezione in salva_macro_test: {type(e)}", "DEBUG")
            log_callback(f"DEBUG: Messaggio originale eccezione in salva_macro_test: {str(e)}", "DEBUG")
        raise e
    finally:
        conn.close()


def load_macro_events(macro_id):
    conn = connect_db()
    cursor = conn.cursor()
    table_name = f"MacroEvent_{macro_id}"
    events = []
    try:
        _ensure_event_metadata_columns(table_name, cursor)
        conn.commit()
        cursor.execute(
            f"""
            SELECT time, type, event, name, button, x, y, delta, is_pressed, normalized_x, normalized_y,
                   game_element_id, previous_game_element_id, ui_graph_id, ui_node_id
            FROM {table_name}
            ORDER BY time;
            """
        )
        for row in cursor.fetchall():
            event_data = {
                "time": row[0],
                "type": row[1],
                "event": row[2],
                "name": row[3],
                "button": row[4],
                "x": row[5],
                "y": row[6],
                "delta": row[7],
                "is_pressed": bool(row[8]),
                "normalized_x": row[9],
                "normalized_y": row[10],
            }
            if row[11] is not None:
                event_data["game_element_id"] = row[11]
            if row[12] is not None:
                event_data["previous_game_element_id"] = row[12]
            if row[13] is not None:
                event_data["ui_graph_id"] = row[13]
            if row[14] is not None:
                event_data["ui_node_id"] = row[14]
            events.append(event_data)
    except sqlite3.OperationalError as e:
        print(f"Errore: Tabella {table_name} non trovata o altri errori del DB: {e}")
        return []
    finally:
        conn.close()
    return events


def get_game_element_event_references(game_element_id):
    """Return macro event tables that reference a captured game element."""
    conn = connect_db()
    cursor = conn.cursor()
    references = []
    try:
        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND (name LIKE 'MacroEvent_%' OR name LIKE 'MacroEventBackup_%')
            ORDER BY name;
            """
        )
        for (table_name,) in cursor.fetchall():
            try:
                _ensure_event_metadata_columns(table_name, cursor)
                cursor.execute(
                    f"SELECT COUNT(*) FROM {table_name} WHERE game_element_id = ? OR previous_game_element_id = ?;",
                    (game_element_id, game_element_id),
                )
                count = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                continue
            if count:
                references.append({"table_name": table_name, "count": count})
        conn.commit()
    finally:
        conn.close()
    return references


def update_macro_full(macro_id, new_name, new_description, new_duration_sec, new_eseguibile, new_events, save_backup=True):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nome, descrizione, durata_sec, eseguibile FROM Macro WHERE id = ?", (macro_id,))
        original_macro_data = cursor.fetchone()
        if not original_macro_data:
            raise ValueError(f"Macro con ID {macro_id} non trovata.")
        original_macro_name = original_macro_data[0]
        current_events = load_macro_events(macro_id)
        if save_backup and current_events:
            backup_name = f"Backup_{original_macro_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            cursor.execute(
                """
                INSERT INTO MacroBackup (macro_id, backup_name, original_macro_name)
                VALUES (?, ?, ?);
                """,
                (macro_id, backup_name, original_macro_name),
            )
            backup_id = cursor.lastrowid
            _create_backup_events_table(backup_id, cursor)
            _save_events_to_table(f"MacroEventBackup_{backup_id}", current_events, cursor)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            UPDATE Macro
            SET nome = ?, descrizione = ?, durata_sec = ?, eseguibile = ?, data_ultima_modifica = ?
            WHERE id = ?;
            """,
            (new_name, new_description, new_duration_sec, new_eseguibile, now, macro_id),
        )
        table_name = f"MacroEvent_{macro_id}"
        cursor.execute(f"DELETE FROM {table_name};")
        _save_events_to_table(table_name, new_events, cursor)
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError(f"Il nome macro '{new_name}' esiste già. Scegli un nome diverso.")
    except Exception as e:
        conn.rollback()
        print(f"Errore durante l'aggiornamento completo della macro ID {macro_id}: {e}")
        raise e
    finally:
        conn.close()


def update_macro_events_only(macro_id, new_events):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nome FROM Macro WHERE id = ?", (macro_id,))
        original_macro_name_res = cursor.fetchone()
        if not original_macro_name_res:
            raise ValueError(f"Macro con ID {macro_id} non trovata.")
        original_macro_name = original_macro_name_res[0]
        current_events = load_macro_events(macro_id)
        if current_events:
            backup_name = f"Backup_Rerecord_{original_macro_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            cursor.execute(
                """
                INSERT INTO MacroBackup (macro_id, backup_name, original_macro_name)
                VALUES (?, ?, ?);
                """,
                (macro_id, backup_name, original_macro_name),
            )
            backup_id = cursor.lastrowid
            _create_backup_events_table(backup_id, cursor)
            _save_events_to_table(f"MacroEventBackup_{backup_id}", current_events, cursor)
        table_name = f"MacroEvent_{macro_id}"
        cursor.execute(f"DELETE FROM {table_name};")
        _save_events_to_table(table_name, new_events, cursor)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            UPDATE Macro SET data_ultima_modifica = ? WHERE id = ?
            """,
            (now, macro_id),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Errore durante l'aggiornamento degli eventi della macro ID {macro_id}: {e}")
        raise e
    finally:
        conn.close()


def delete_macro(macro_name):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM Macro WHERE nome = ?", (macro_name,))
        macro_id_result = cursor.fetchone()
        if macro_id_result:
            macro_id = macro_id_result[0]
            cursor.execute("SELECT is_protected FROM Macro WHERE id = ?", (macro_id,))
            protected_row = cursor.fetchone()
            if protected_row and bool(protected_row[0]):
                raise ValueError(f"La macro di sistema '{macro_name}' non può essere cancellata.")
            cursor.execute(f"DROP TABLE IF EXISTS MacroEvent_{macro_id}")
        cursor.execute("DELETE FROM Macro WHERE nome = ?", (macro_name,))
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Macro '{macro_name}' non trovata.")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def duplicate_macro(macro_id):
    """Duplica una macro esistente con un nuovo nome che include la data e ora corrente."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT nome, descrizione, durata_sec, eseguibile, macro_kind, system_key, system_payload FROM Macro WHERE id = ?",
            (macro_id,),
        )
        original_macro = cursor.fetchone()
        if not original_macro:
            raise ValueError(f"Macro con ID {macro_id} non trovata.")

        original_name, description, duration_sec, eseguibile, macro_kind, system_key, system_payload = original_macro
        timestamp_pattern = r"_\d{8}_\d{6}$"
        timestamp_match = re.search(timestamp_pattern, original_name)

        if timestamp_match:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = re.sub(timestamp_pattern, f"_{timestamp}", original_name)
        else:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"{original_name}_{timestamp}"

        cursor.execute("SELECT id FROM Macro WHERE nome = ?", (new_name,))
        if cursor.fetchone():
            counter = 1
            while True:
                if timestamp_match:
                    new_name = re.sub(timestamp_pattern, f"_{timestamp}_{counter}", original_name)
                else:
                    new_name = f"{original_name}_{timestamp}_{counter}"

                cursor.execute("SELECT id FROM Macro WHERE nome = ?", (new_name,))
                if not cursor.fetchone():
                    break
                counter += 1

        cursor.execute(
            """
            INSERT INTO Macro (nome, descrizione, durata_sec, eseguibile, macro_kind, is_protected, system_key, system_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (new_name, description, duration_sec, eseguibile, macro_kind or STANDARD_MACRO_KIND, 0, system_key, system_payload),
        )
        new_macro_id = cursor.lastrowid

        _create_events_table(new_macro_id, cursor)

        original_events_table = f"MacroEvent_{macro_id}"
        new_events_table = f"MacroEvent_{new_macro_id}"

        cursor.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{original_events_table}';"
        )
        if cursor.fetchone():
            _copy_events_between_tables(original_events_table, new_events_table, cursor)

        conn.commit()
        return new_macro_id, new_name
    except Exception as e:
        conn.rollback()
        print(f"Errore durante la duplicazione della macro ID {macro_id}: {e}")
        raise e
    finally:
        conn.close()


__all__ = [
    "delete_macro",
    "duplicate_macro",
    "get_all_macros",
    "get_game_element_event_references",
    "get_macro_metadata_by_id",
    "get_macro_metadata_by_name",
    "load_macro_events",
    "salva_macro_test",
    "STANDARD_MACRO_KIND",
    "SYSTEM_MACRO_KIND",
    "update_macro_events_only",
    "update_macro_full",
]
