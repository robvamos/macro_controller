"""Repository per backup delle macro."""

import datetime

from repositories.database import connect_db

EVENT_METADATA_COLUMNS = (
    ("game_element_id", "INTEGER"),
    ("previous_game_element_id", "INTEGER"),
    ("ui_graph_id", "TEXT"),
    ("ui_node_id", "TEXT"),
)


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


def get_all_backups():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, macro_id, backup_name, backup_timestamp, original_macro_name FROM MacroBackup ORDER BY backup_timestamp DESC;"
    )
    backups = []
    for row in cursor.fetchall():
        backups.append(
            {
                "id": row[0],
                "macro_id": row[1],
                "backup_name": row[2],
                "backup_timestamp": row[3],
                "original_macro_name": row[4],
            }
        )
    conn.close()
    return backups


def restore_macro_from_backup(backup_id):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT macro_id FROM MacroBackup WHERE id = ?", (backup_id,))
        backup_data = cursor.fetchone()
        if not backup_data:
            raise ValueError(f"Backup con ID {backup_id} non trovato.")
        original_macro_id = backup_data[0]
        backup_events_table = f"MacroEventBackup_{backup_id}"
        _ensure_event_metadata_columns(backup_events_table, cursor)
        cursor.execute(
            f"""
            SELECT time, type, event, name, button, x, y, delta, is_pressed, normalized_x, normalized_y,
                   game_element_id, previous_game_element_id, ui_graph_id, ui_node_id
            FROM {backup_events_table}
            ORDER BY time;
            """
        )
        backup_events = []
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
            backup_events.append(event_data)
        cursor.execute("SELECT id FROM Macro WHERE id = ?", (original_macro_id,))
        if not cursor.fetchone():
            raise ValueError(f"La macro originale con ID {original_macro_id} non esiste più. Impossibile ripristinare.")
        original_events_table = f"MacroEvent_{original_macro_id}"
        cursor.execute(f"DELETE FROM {original_events_table};")
        _save_events_to_table(original_events_table, backup_events, cursor)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            UPDATE Macro SET data_ultima_modifica = ? WHERE id = ?
            """,
            (now, original_macro_id),
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Errore durante il ripristino del backup ID {backup_id}: {e}")
        raise e
    finally:
        conn.close()


def drop_all_backup_tables():
    """Elimina tutte le tabelle di eventi di backup e svuota la tabella MacroBackup."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'MacroEventBackup_%';")
        tables = cursor.fetchall()
        for (table_name,) in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        cursor.execute("DELETE FROM MacroBackup;")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Errore durante l'eliminazione delle tabelle di backup: {e}")
        raise e
    finally:
        conn.close()


__all__ = [
    "drop_all_backup_tables",
    "get_all_backups",
    "restore_macro_from_backup",
]
