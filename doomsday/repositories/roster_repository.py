"""Repository per import e lettura del roster Doomsday locale."""

from __future__ import annotations

import json

from doomsday.catalog.market_loader import (
    load_beast_roster as load_beast_roster_dataset,
    load_roster_summary as load_roster_summary_dataset,
)
from doomsday.repositories.database import connect_doomsday_db, setup_doomsday_tables


def import_roster_datasets() -> dict:
    """Importa il roster locale e le bestie personali dai dataset legacy."""
    setup_doomsday_tables()
    summary = load_roster_summary_dataset()
    beasts = load_beast_roster_dataset()
    conn = connect_doomsday_db()
    cursor = conn.cursor()
    try:
        imported = {"roster_documents": 0, "roster_beasts": 0}

        if summary:
            cursor.execute(
                """
                INSERT INTO RosterDocuments (doc_type, raw_json)
                VALUES (?, ?)
                ON CONFLICT(doc_type) DO UPDATE SET
                    raw_json=excluded.raw_json,
                    imported_at=CURRENT_TIMESTAMP;
                """,
                ("summary", json.dumps(summary, ensure_ascii=False)),
            )
            imported["roster_documents"] += 1

        for name, data in beasts.items():
            cursor.execute(
                """
                INSERT INTO RosterBeasts (
                    name, element, support_reason, strategic_roles_json, synergies_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    element=excluded.element,
                    support_reason=excluded.support_reason,
                    strategic_roles_json=excluded.strategic_roles_json,
                    synergies_json=excluded.synergies_json,
                    raw_json=excluded.raw_json,
                    imported_at=CURRENT_TIMESTAMP;
                """,
                (
                    name,
                    data.get("elemento"),
                    data.get("motivazione_supporto"),
                    json.dumps(data.get("ruolo_strategico", []), ensure_ascii=False),
                    json.dumps(data.get("sinergie", []), ensure_ascii=False),
                    json.dumps(data, ensure_ascii=False),
                ),
            )
            imported["roster_beasts"] += 1

        conn.commit()
        return imported
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_roster_summary() -> dict:
    """Restituisce il documento riepilogativo del roster."""
    conn = connect_doomsday_db()
    cursor = conn.cursor()
    cursor.execute("SELECT raw_json FROM RosterDocuments WHERE doc_type = 'summary'")
    row = cursor.fetchone()
    conn.close()
    return json.loads(row[0]) if row else {}


def load_roster_beasts() -> list[dict]:
    conn = connect_doomsday_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT name, element, support_reason, strategic_roles_json, synergies_json
        FROM RosterBeasts
        ORDER BY name COLLATE NOCASE;
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "name": row[0],
            "element": row[1],
            "support_reason": row[2],
            "strategic_roles": json.loads(row[3]),
            "synergies": json.loads(row[4]),
        }
        for row in rows
    ]


def get_roster_stats() -> dict:
    conn = connect_doomsday_db()
    cursor = conn.cursor()
    result = {}
    for table_name in ("RosterDocuments", "RosterBeasts"):
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        result[table_name] = cursor.fetchone()[0]
    conn.close()
    return result
