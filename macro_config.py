#!/usr/bin/env python3
"""
Configurazione avanzata per il sistema di macro.
Contiene impostazioni per migliorare la riproduzione e la gestione degli eventi.
"""

import json
import os
import logging

from core.paths import CONFIG_DIR

LOG_LEVEL_NAME_TO_VALUE = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Configurazione predefinita
DEFAULT_CONFIG = {
    "playback": {
        "focus_check_interval": 0.05,  # Controlla focus ogni 50ms
        "event_delay_tolerance": 0.01,  # Tolleranza per i delay (10ms)
        "mouse_coordinate_validation": True,
        "keyboard_event_validation": True,
        "max_playback_duration": 300,  # Massimo 5 minuti per macro
        "retry_on_focus_loss": True,
        "max_retry_attempts": 3,
        "visual_click_guard": {
            "enabled": True,
            "radius_px": 48,
            "resize_px": 32,
            "min_similarity": 0.8,
            "stop_on_mismatch": True
        }
    },
    "recording": {
        "min_event_interval": 0.01,  # Minimo 10ms tra eventi
        "coordinate_normalization": True,
        "backup_before_overwrite": True,
        "validate_events_during_recording": True
    },
    "window_management": {
        "focus_wait_timeout": 10.0,  # Timeout per attesa focus (10 secondi)
        "window_detection_retry": 3,
        "client_area_only": True,  # Usa solo area client (senza bordi)
        "fallback_window_size": {
            "width": 800,
            "height": 600
        }
    },
    "input_simulation": {
        "keyboard_delay": 0.01,  # Delay tra pressione e rilascio tasti
        "mouse_delay": 0.01,     # Delay tra movimenti mouse
        "use_absolute_coordinates": True,
        "coordinate_rounding": True,
        "scroll_sensitivity": 1.0
    },
    "debug": {
        "enable_logging": True,
        "log_level": "INFO",
        "save_playback_logs": False,
        "validate_events_before_playback": True
    }
}

class MacroConfig:
    """Gestisce la configurazione del sistema di macro."""
    
    def __init__(self, config_file=None):
        if config_file is None:
            config_file = str(CONFIG_DIR / "macro_config.json")
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """Carica la configurazione dal file o usa quella predefinita."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Unisci con configurazione predefinita per campi mancanti
                    return self.merge_configs(DEFAULT_CONFIG, config)
            else:
                # Crea file di configurazione predefinito
                self.save_config(DEFAULT_CONFIG)
                return DEFAULT_CONFIG
        except Exception as e:
            print(f"⚠️ Errore caricamento configurazione: {e}")
            print("💡 Usando configurazione predefinita")
            return DEFAULT_CONFIG
    
    def save_config(self, config=None):
        """Salva la configurazione nel file."""
        if config is None:
            config = self.config
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Errore salvataggio configurazione: {e}")
            return False
    
    def merge_configs(self, default_config, user_config):
        """Unisce configurazione predefinita con quella utente."""
        merged = default_config.copy()
        
        def merge_recursive(default, user):
            for key, value in user.items():
                if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                    merge_recursive(default[key], value)
                else:
                    default[key] = value
        
        merge_recursive(merged, user_config)
        return merged
    
    def get(self, key_path, default=None):
        """Ottiene un valore di configurazione usando un percorso (es. 'playback.focus_check_interval')."""
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path, value):
        """Imposta un valore di configurazione usando un percorso."""
        keys = key_path.split('.')
        config = self.config
        
        # Naviga fino al penultimo livello
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Imposta il valore finale
        config[keys[-1]] = value
    
    def validate_config(self):
        """Valida la configurazione corrente."""
        errors = []
        
        # Validazione playback
        focus_interval = self.get('playback.focus_check_interval')
        if focus_interval <= 0 or focus_interval > 1.0:
            errors.append("playback.focus_check_interval deve essere tra 0.001 e 1.0 secondi")
        
        max_duration = self.get('playback.max_playback_duration')
        if max_duration <= 0 or max_duration > 3600:
            errors.append("playback.max_playback_duration deve essere tra 1 e 3600 secondi")
        
        # Validazione window management
        focus_timeout = self.get('window_management.focus_wait_timeout')
        if focus_timeout <= 0 or focus_timeout > 60:
            errors.append("window_management.focus_wait_timeout deve essere tra 1 e 60 secondi")
        
        # Validazione input simulation
        keyboard_delay = self.get('input_simulation.keyboard_delay')
        if keyboard_delay < 0 or keyboard_delay > 1.0:
            errors.append("input_simulation.keyboard_delay deve essere tra 0 e 1.0 secondi")
        
        return errors
    
    def get_playback_settings(self):
        """Restituisce le impostazioni di riproduzione."""
        return {
            'focus_check_interval': self.get('playback.focus_check_interval'),
            'event_delay_tolerance': self.get('playback.event_delay_tolerance'),
            'mouse_coordinate_validation': self.get('playback.mouse_coordinate_validation'),
            'keyboard_event_validation': self.get('playback.keyboard_event_validation'),
            'max_playback_duration': self.get('playback.max_playback_duration'),
            'retry_on_focus_loss': self.get('playback.retry_on_focus_loss'),
            'max_retry_attempts': self.get('playback.max_retry_attempts')
        }
    
    def get_recording_settings(self):
        """Restituisce le impostazioni di registrazione."""
        return {
            'min_event_interval': self.get('recording.min_event_interval'),
            'coordinate_normalization': self.get('recording.coordinate_normalization'),
            'backup_before_overwrite': self.get('recording.backup_before_overwrite'),
            'validate_events_during_recording': self.get('recording.validate_events_during_recording')
        }
    
    def get_window_settings(self):
        """Restituisce le impostazioni di gestione finestre."""
        return {
            'focus_wait_timeout': self.get('window_management.focus_wait_timeout'),
            'window_detection_retry': self.get('window_management.window_detection_retry'),
            'client_area_only': self.get('window_management.client_area_only'),
            'fallback_window_size': self.get('window_management.fallback_window_size')
        }
    
    def get_input_settings(self):
        """Restituisce le impostazioni di simulazione input."""
        return {
            'keyboard_delay': self.get('input_simulation.keyboard_delay'),
            'mouse_delay': self.get('input_simulation.mouse_delay'),
            'use_absolute_coordinates': self.get('input_simulation.use_absolute_coordinates'),
            'coordinate_rounding': self.get('input_simulation.coordinate_rounding'),
            'scroll_sensitivity': self.get('input_simulation.scroll_sensitivity')
        }
    
    def get_debug_settings(self):
        """Restituisce le impostazioni di debug."""
        return {
            'enable_logging': self.get('debug.enable_logging'),
            'log_level': self.get('debug.log_level'),
            'save_playback_logs': self.get('debug.save_playback_logs'),
            'validate_events_before_playback': self.get('debug.validate_events_before_playback')
        }

# Configurazione globale
macro_config = MacroConfig()

def get_config():
    """Restituisce l'istanza globale della configurazione."""
    return macro_config

def get_playback_config():
    """Restituisce la configurazione di riproduzione."""
    return macro_config.get_playback_settings()

def get_recording_config():
    """Restituisce la configurazione di registrazione."""
    return macro_config.get_recording_settings()

def get_window_config():
    """Restituisce la configurazione di gestione finestre."""
    return macro_config.get_window_settings()

def get_input_config():
    """Restituisce la configurazione di simulazione input."""
    return macro_config.get_input_settings()

def get_debug_config():
    """Restituisce la configurazione di debug."""
    return macro_config.get_debug_settings()

# Funzioni di utilità per la configurazione
def is_debug_enabled():
    """Verifica se il debug è abilitato."""
    return macro_config.get('debug.enable_logging', False)

def get_log_level():
    """Restituisce il livello di log configurato."""
    return macro_config.get('debug.log_level', 'INFO')


def normalize_log_level(level, default="INFO"):
    """Normalizza il livello di log in una stringa supportata."""
    if isinstance(level, int):
        return logging.getLevelName(level) if level in LOG_LEVEL_NAME_TO_VALUE.values() else default
    if isinstance(level, str):
        normalized = level.strip().upper()
        if normalized in LOG_LEVEL_NAME_TO_VALUE:
            return normalized
    return default


def get_log_level_value(level=None):
    """Restituisce il valore numerico del livello richiesto o configurato."""
    level_name = normalize_log_level(level or get_log_level())
    return LOG_LEVEL_NAME_TO_VALUE.get(level_name, logging.INFO)


def should_emit_log_level(level):
    """Indica se un messaggio deve essere emesso secondo la soglia configurata."""
    return get_log_level_value(level) >= get_log_level_value()

def should_validate_events():
    """Verifica se gli eventi devono essere validati prima della riproduzione."""
    return macro_config.get('debug.validate_events_before_playback', True)

def get_focus_check_interval():
    """Restituisce l'intervallo di controllo del focus."""
    return macro_config.get('playback.focus_check_interval', 0.05)


def get_visual_click_guard_config():
    """Restituisce la configurazione del controllo visivo sui click."""
    return macro_config.get('playback.visual_click_guard', DEFAULT_CONFIG["playback"]["visual_click_guard"])

def get_focus_wait_timeout():
    """Restituisce il timeout per l'attesa del focus."""
    return macro_config.get('window_management.focus_wait_timeout', 10.0)

def get_fallback_window_size():
    """Restituisce le dimensioni di fallback per le finestre."""
    return macro_config.get('window_management.fallback_window_size', {'width': 800, 'height': 600})

def should_use_client_area():
    """Verifica se usare solo l'area client delle finestre."""
    return macro_config.get('window_management.client_area_only', True)

def get_keyboard_delay():
    """Restituisce il delay per gli eventi tastiera."""
    return macro_config.get('input_simulation.keyboard_delay', 0.01)

def get_mouse_delay():
    """Restituisce il delay per gli eventi mouse."""
    return macro_config.get('input_simulation.mouse_delay', 0.01)

def should_round_coordinates():
    """Verifica se arrotondare le coordinate."""
    return macro_config.get('input_simulation.coordinate_rounding', True)

def get_scroll_sensitivity():
    """Restituisce la sensibilità dello scroll."""
    return macro_config.get('input_simulation.scroll_sensitivity', 1.0)

if __name__ == "__main__":
    # Test della configurazione
    config = get_config()
    
    print("🔧 Configurazione Macro System")
    print("=" * 40)
    
    # Mostra configurazione corrente
    print("\n📋 Configurazione Playback:")
    for key, value in config.get_playback_settings().items():
        print(f"   {key}: {value}")
    
    print("\n📋 Configurazione Recording:")
    for key, value in config.get_recording_settings().items():
        print(f"   {key}: {value}")
    
    print("\n📋 Configurazione Window Management:")
    for key, value in config.get_window_settings().items():
        print(f"   {key}: {value}")
    
    print("\n📋 Configurazione Input Simulation:")
    for key, value in config.get_input_settings().items():
        print(f"   {key}: {value}")
    
    print("\n📋 Configurazione Debug:")
    for key, value in config.get_debug_settings().items():
        print(f"   {key}: {value}")
    
    # Validazione
    errors = config.validate_config()
    if errors:
        print(f"\n❌ Errori di configurazione trovati:")
        for error in errors:
            print(f"   - {error}")
    else:
        print(f"\n✅ Configurazione valida!")
    
    # Test funzioni di utilità
    print(f"\n🧪 Test funzioni di utilità:")
    print(f"   Debug abilitato: {is_debug_enabled()}")
    print(f"   Livello log: {get_log_level()}")
    print(f"   Intervallo focus: {get_focus_check_interval()}s")
    print(f"   Timeout focus: {get_focus_wait_timeout()}s")
    print(f"   Delay tastiera: {get_keyboard_delay()}s")
    print(f"   Delay mouse: {get_mouse_delay()}s")
