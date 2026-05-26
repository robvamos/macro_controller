"""Configurazione condivisa per i moduli Doomsday."""

from core.paths import (
    DOOMSDAY_CATALOG_DIR,
    DOOMSDAY_OCR_OUTPUT_DIR,
    DOOMSDAY_ROSTER_DIR,
    DOOMSDAY_SCREENSHOTS_DIR,
)


DEFAULT_DEBUG_LEVEL = 1

DEFAULT_STAT_VALUES = {
    "ATK": 0,
    "DEF": 0,
    "HP": 0,
    "Squadre": 0,
    "EXP": 0,
    "SPD": 0,
    "CRT": 0.0,
    "CRTD": 0.0,
    "ACC": 0.0,
    "EVA": 0.0,
    "EFF": 0.0,
    "RES": 0.0,
    "nome_completo_eroe": "",
    "titolo_eroe": "",
    "livello": 0,
    "rarita_stelle": 0,
    "talenti": [],
    "rami_talenti_trovati": [],
    "nome_eroe_determinato": "",
}

DEFAULT_TALENT_BRANCHES = [
    "offensivo",
    "difensivo",
    "tattico",
    "curativo",
    "supporto",
    "protezione",
    "resistenza",
    "provocazione",
    "contrattacco",
    "controllo",
    "tecnologico",
    "precisione",
    "mobilita",
    "utilita",
    "immunologia",
    "scienza",
    "infiltrazione",
    "assassinio",
    "incendiario",
    "purificazione",
    "difesa",
    "velocita",
    "base",
    "generale",
    "abilita",
    "squadra a distanza",
    "squadra di fanteria",
    "rider",
    "siege",
    "infantry",
]

CATALOG_MARKET_DIR = DOOMSDAY_CATALOG_DIR / "market_profiles"
CATALOG_PROFILE_PACK_DIR = DOOMSDAY_CATALOG_DIR / "profile_pack"

__all__ = [
    "CATALOG_MARKET_DIR",
    "CATALOG_PROFILE_PACK_DIR",
    "DEFAULT_DEBUG_LEVEL",
    "DEFAULT_STAT_VALUES",
    "DEFAULT_TALENT_BRANCHES",
    "DOOMSDAY_OCR_OUTPUT_DIR",
    "DOOMSDAY_ROSTER_DIR",
    "DOOMSDAY_SCREENSHOTS_DIR",
]

