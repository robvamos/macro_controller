"""Repository per i collegamenti tra grafo UI del gioco e macro operative."""

from __future__ import annotations

from repositories.database import connect_db, setup_ui_graph_macro_links_table


def _row_to_dict(row):
    return {
        "id": row[0],
        "graph_id": row[1],
        "node_id": row[2],
        "intent_key": row[3],
        "relation_type": row[4],
        "macro_id": row[5],
        "macro_name_snapshot": row[6],
        "priority": row[7],
        "enabled": bool(row[8]),
        "notes": row[9],
        "created_at": row[10],
        "updated_at": row[11],
    }


def create_ui_graph_macro_link(
    *,
    graph_id,
    node_id,
    macro_id=None,
    macro_name_snapshot=None,
    intent_key=None,
    relation_type="candidate",
    priority=100,
    enabled=True,
    notes=None,
):
    setup_ui_graph_macro_links_table()
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO UIGraphMacroLinks
            (graph_id, node_id, intent_key, relation_type, macro_id, macro_name_snapshot, priority, enabled, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                graph_id,
                node_id,
                intent_key,
                relation_type,
                macro_id,
                macro_name_snapshot,
                priority,
                1 if enabled else 0,
                notes,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_ui_graph_macro_links(*, graph_id=None, node_id=None, intent_key=None, enabled_only=True):
    setup_ui_graph_macro_links_table()
    conn = connect_db()
    cursor = conn.cursor()
    try:
        query = """
            SELECT id, graph_id, node_id, intent_key, relation_type, macro_id, macro_name_snapshot,
                   priority, enabled, notes, created_at, updated_at
            FROM UIGraphMacroLinks
            WHERE 1=1
        """
        params = []
        if graph_id is not None:
            query += " AND graph_id = ?"
            params.append(graph_id)
        if node_id is not None:
            query += " AND node_id = ?"
            params.append(node_id)
        if intent_key is not None:
            query += " AND intent_key = ?"
            params.append(intent_key)
        if enabled_only:
            query += " AND enabled = 1"
        query += " ORDER BY priority ASC, updated_at DESC, created_at DESC"
        cursor.execute(query, params)
        return [_row_to_dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def update_ui_graph_macro_link(link_id, *, macro_id=None, macro_name_snapshot=None, intent_key=None, relation_type=None, priority=None, enabled=None, notes=None):
    setup_ui_graph_macro_links_table()
    updates = []
    params = []
    if macro_id is not None:
        updates.append("macro_id = ?")
        params.append(macro_id)
    if macro_name_snapshot is not None:
        updates.append("macro_name_snapshot = ?")
        params.append(macro_name_snapshot)
    if intent_key is not None:
        updates.append("intent_key = ?")
        params.append(intent_key)
    if relation_type is not None:
        updates.append("relation_type = ?")
        params.append(relation_type)
    if priority is not None:
        updates.append("priority = ?")
        params.append(priority)
    if enabled is not None:
        updates.append("enabled = ?")
        params.append(1 if enabled else 0)
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)
    if not updates:
        return False

    conn = connect_db()
    cursor = conn.cursor()
    try:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(link_id)
        cursor.execute(
            f"UPDATE UIGraphMacroLinks SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_ui_graph_macro_link(link_id):
    setup_ui_graph_macro_links_table()
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM UIGraphMacroLinks WHERE id = ?", (link_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


__all__ = [
    "create_ui_graph_macro_link",
    "delete_ui_graph_macro_link",
    "get_ui_graph_macro_links",
    "update_ui_graph_macro_link",
]
