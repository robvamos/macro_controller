"""Accesso e setup database dedicato Doomsday."""

from __future__ import annotations

import shutil
import sqlite3

from core.paths import DOOMSDAY_DB_PATH, LEGACY_DOOMSDAY_DB_PATH, ensure_project_directories


SQLITE_TIMEOUT_SECONDS = 10.0
SQLITE_BUSY_TIMEOUT_MS = 10000


def connect_doomsday_db():
    """Apre una connessione SQLite al database Doomsday."""
    ensure_project_directories()
    if not DOOMSDAY_DB_PATH.exists() and LEGACY_DOOMSDAY_DB_PATH.exists():
        shutil.copy2(LEGACY_DOOMSDAY_DB_PATH, DOOMSDAY_DB_PATH)
    conn = sqlite3.connect(DOOMSDAY_DB_PATH, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS};")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def get_doomsday_db_path() -> str:
    ensure_project_directories()
    return str(DOOMSDAY_DB_PATH)


def setup_doomsday_tables() -> None:
    """Crea o verifica le tabelle del catalogo/roster Doomsday."""
    conn = connect_doomsday_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS CatalogProfiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                canonical_name TEXT,
                rarity TEXT,
                hero_type TEXT,
                roles_json TEXT NOT NULL,
                abilities_json TEXT NOT NULL,
                talent_branches_json TEXT NOT NULL,
                web_sources_json TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS BeastProfiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                element TEXT,
                beast_type TEXT,
                level INTEGER,
                skills_json TEXT NOT NULL,
                strategic_roles_json TEXT NOT NULL,
                synergies_json TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ChipProfiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                stars INTEGER,
                bonus TEXT,
                role TEXT,
                raw_json TEXT NOT NULL,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS HeroProfileNotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_name TEXT NOT NULL UNIQUE,
                level INTEGER,
                beast TEXT,
                allies_json TEXT NOT NULL,
                enemies_json TEXT NOT NULL,
                skills_json TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS RosterDocuments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_type TEXT NOT NULL UNIQUE,
                raw_json TEXT NOT NULL,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS RosterBeasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                element TEXT,
                support_reason TEXT,
                strategic_roles_json TEXT NOT NULL,
                synergies_json TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_catalog_profiles_name ON CatalogProfiles (display_name COLLATE NOCASE);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_beast_profiles_name ON BeastProfiles (name COLLATE NOCASE);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chip_profiles_name ON ChipProfiles (name COLLATE NOCASE);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_roster_beasts_name ON RosterBeasts (name COLLATE NOCASE);")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
