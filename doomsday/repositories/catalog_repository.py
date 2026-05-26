"""Repository per import e lettura del catalogo Doomsday."""

from __future__ import annotations

import json

from doomsday.catalog.market_loader import load_market_profiles, load_profile_pack
from doomsday.repositories.database import connect_doomsday_db, setup_doomsday_tables


def import_catalog_datasets() -> dict:
    """Importa catalogo eroi, bestie, chip e profili statici."""
    setup_doomsday_tables()
    profiles = load_market_profiles()
    profile_pack = load_profile_pack()
    conn = connect_doomsday_db()
    cursor = conn.cursor()
    try:
        imported = {
            "catalog_profiles": 0,
            "beast_profiles": 0,
            "chip_profiles": 0,
            "hero_profile_notes": 0,
        }

        for profile in profiles:
            cursor.execute(
                """
                INSERT INTO CatalogProfiles (
                    source_file, display_name, canonical_name, rarity, hero_type,
                    roles_json, abilities_json, talent_branches_json, web_sources_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_file) DO UPDATE SET
                    display_name=excluded.display_name,
                    canonical_name=excluded.canonical_name,
                    rarity=excluded.rarity,
                    hero_type=excluded.hero_type,
                    roles_json=excluded.roles_json,
                    abilities_json=excluded.abilities_json,
                    talent_branches_json=excluded.talent_branches_json,
                    web_sources_json=excluded.web_sources_json,
                    raw_json=excluded.raw_json,
                    imported_at=CURRENT_TIMESTAMP;
                """,
                (
                    profile.get("_source_file", f"{profile.get('name', 'unknown')}.json"),
                    profile.get("_display_name", profile.get("name", "Unknown")),
                    profile.get("name"),
                    profile.get("rarity"),
                    profile.get("type"),
                    json.dumps(profile.get("roles", []), ensure_ascii=False),
                    json.dumps(profile.get("abilities", []), ensure_ascii=False),
                    json.dumps(profile.get("talent_branches", []), ensure_ascii=False),
                    json.dumps(profile.get("web_sources", []), ensure_ascii=False),
                    json.dumps(profile, ensure_ascii=False),
                ),
            )
            imported["catalog_profiles"] += 1

        for name, data in profile_pack.get("beasts_registry", {}).items():
            cursor.execute(
                """
                INSERT INTO BeastProfiles (
                    name, element, beast_type, level, skills_json, strategic_roles_json, synergies_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    element=excluded.element,
                    beast_type=excluded.beast_type,
                    level=excluded.level,
                    skills_json=excluded.skills_json,
                    strategic_roles_json=excluded.strategic_roles_json,
                    synergies_json=excluded.synergies_json,
                    raw_json=excluded.raw_json,
                    imported_at=CURRENT_TIMESTAMP;
                """,
                (
                    name,
                    data.get("element"),
                    data.get("type"),
                    data.get("level"),
                    json.dumps(data.get("skills", []), ensure_ascii=False),
                    json.dumps(data.get("ruolo_strategico", []), ensure_ascii=False),
                    json.dumps(data.get("sinergie", []), ensure_ascii=False),
                    json.dumps(data, ensure_ascii=False),
                ),
            )
            imported["beast_profiles"] += 1

        for name, data in profile_pack.get("chips_registry", {}).items():
            cursor.execute(
                """
                INSERT INTO ChipProfiles (name, stars, bonus, role, raw_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    stars=excluded.stars,
                    bonus=excluded.bonus,
                    role=excluded.role,
                    raw_json=excluded.raw_json,
                    imported_at=CURRENT_TIMESTAMP;
                """,
                (
                    name,
                    data.get("stars"),
                    data.get("bonus"),
                    data.get("role"),
                    json.dumps(data, ensure_ascii=False),
                ),
            )
            imported["chip_profiles"] += 1

        hero_notes = profile_pack.get("hero_profile_cynthia")
        if hero_notes:
            cursor.execute(
                """
                INSERT INTO HeroProfileNotes (
                    profile_name, level, beast, allies_json, enemies_json, skills_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_name) DO UPDATE SET
                    level=excluded.level,
                    beast=excluded.beast,
                    allies_json=excluded.allies_json,
                    enemies_json=excluded.enemies_json,
                    skills_json=excluded.skills_json,
                    raw_json=excluded.raw_json,
                    imported_at=CURRENT_TIMESTAMP;
                """,
                (
                    hero_notes.get("name", "Unknown"),
                    hero_notes.get("level"),
                    hero_notes.get("beast"),
                    json.dumps(hero_notes.get("allies", []), ensure_ascii=False),
                    json.dumps(hero_notes.get("enemies", []), ensure_ascii=False),
                    json.dumps(hero_notes.get("skills", []), ensure_ascii=False),
                    json.dumps(hero_notes, ensure_ascii=False),
                ),
            )
            imported["hero_profile_notes"] = 1

        conn.commit()
        return imported
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_catalog_profiles() -> list[dict]:
    conn = connect_doomsday_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT display_name, canonical_name, rarity, hero_type, roles_json, abilities_json, talent_branches_json
        FROM CatalogProfiles
        ORDER BY display_name COLLATE NOCASE;
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "display_name": row[0],
            "canonical_name": row[1],
            "rarity": row[2],
            "hero_type": row[3],
            "roles": json.loads(row[4]),
            "abilities": json.loads(row[5]),
            "talent_branches": json.loads(row[6]),
        }
        for row in rows
    ]


def list_beast_profiles() -> list[dict]:
    conn = connect_doomsday_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT name, element, beast_type, level, skills_json, strategic_roles_json, synergies_json
        FROM BeastProfiles
        ORDER BY name COLLATE NOCASE;
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "name": row[0],
            "element": row[1],
            "beast_type": row[2],
            "level": row[3],
            "skills": json.loads(row[4]),
            "strategic_roles": json.loads(row[5]),
            "synergies": json.loads(row[6]),
        }
        for row in rows
    ]


def list_chip_profiles() -> list[dict]:
    conn = connect_doomsday_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, stars, bonus, role FROM ChipProfiles ORDER BY name COLLATE NOCASE;")
    rows = cursor.fetchall()
    conn.close()
    return [
        {"name": row[0], "stars": row[1], "bonus": row[2], "role": row[3]}
        for row in rows
    ]


def list_hero_profile_notes() -> list[dict]:
    conn = connect_doomsday_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT profile_name, level, beast, allies_json, enemies_json, skills_json FROM HeroProfileNotes ORDER BY profile_name COLLATE NOCASE;"
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "profile_name": row[0],
            "level": row[1],
            "beast": row[2],
            "allies": json.loads(row[3]),
            "enemies": json.loads(row[4]),
            "skills": json.loads(row[5]),
        }
        for row in rows
    ]


def get_catalog_stats() -> dict:
    conn = connect_doomsday_db()
    cursor = conn.cursor()
    result = {}
    for table_name in ("CatalogProfiles", "BeastProfiles", "ChipProfiles", "HeroProfileNotes"):
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        result[table_name] = cursor.fetchone()[0]
    conn.close()
    return result

