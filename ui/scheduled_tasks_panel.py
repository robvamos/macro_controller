"""Helper UI per il pannello degli scheduled tasks."""

import datetime
import tkinter as tk
from tkinter import ttk


ACTION_BUTTON_KEYWORDS = ("Modifica", "Elimina", "Duplica", "Attiva/Disattiva")


def format_schedule_type(task):
    """Restituisce la descrizione utente del tipo di schedulazione."""
    if task["schedulazione_tipo"] != "intervallo":
        return "Ora fissa"

    if task["intervallo_ore"] and task["intervallo_minuti"]:
        return f"Ogni {task['intervallo_ore']}h {task['intervallo_minuti']}m"
    if task["intervallo_ore"]:
        return f"Ogni {task['intervallo_ore']}h"
    if task["intervallo_minuti"]:
        return f"Ogni {task['intervallo_minuti']}m"
    return "Intervallo"


def format_task_status(task):
    """Restituisce la label di stato per la lista scheduled tasks."""
    stato_task = task.get("stato", "stopped")
    if stato_task == "running":
        return "▶️ Running"
    if stato_task == "completed":
        return "✅ Completato"
    if task["attivo"]:
        return "🟢 Attivo"
    return "🔴 Disattivo"


def build_scheduled_task_row(task):
    """Restituisce la tupla valori per l'inserimento nella TreeView."""
    prossima_esecuzione_str = task["prossima_esecuzione"] if task["prossima_esecuzione"] else "N/A"
    ultima_esecuzione_str = task["data_ultima_esecuzione"] if task["data_ultima_esecuzione"] else "Mai"
    return (
        task["nome"],
        task["macro_nome"] or "N/A",
        format_schedule_type(task),
        prossima_esecuzione_str,
        format_task_status(task),
        ultima_esecuzione_str,
    )


def update_action_buttons_state(buttons_parent, has_selection):
    """Aggiorna lo stato dei pulsanti di azione dello scheduled tasks panel."""
    for widget in buttons_parent.winfo_children():
        if isinstance(widget, ttk.Frame):
            for button in widget.winfo_children():
                if isinstance(button, ttk.Button):
                    button_text = button.cget("text")
                    if any(text in button_text for text in ACTION_BUTTON_KEYWORDS):
                        button.config(state=tk.NORMAL if has_selection else tk.DISABLED)


def format_countdown(seconds):
    """Formatta i secondi in un countdown leggibile."""
    if seconds < 0:
        return "⚠️ Scaduto"

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days}g")
    if hours > 0 or days > 0:
        parts.append(f"{hours:02d}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes:02d}m")
    parts.append(f"{secs:02d}s")
    return " ".join(parts)


def _coerce_datetime(value):
    if not value:
        return None
    if isinstance(value, str):
        return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return value


def build_countdown_entries(active_tasks, get_task_macro_sequence, now=None, error_callback=None):
    """Costruisce il contenuto testuale del pannello countdown."""
    now = now or datetime.datetime.now()
    entries = []

    if not active_tasks:
        entries.append(("Nessun task attivo al momento.\n\n", None))
        entries.append(("I task attivi appariranno qui\n", None))
        entries.append(("ordinati per prossima esecuzione.", None))
        return entries

    entries.append((f"📋 {len(active_tasks)} task attivo/i\n", None))
    entries.append(("=" * 40 + "\n\n", None))

    for idx, task in enumerate(active_tasks, 1):
        countdown_str = "N/A"
        prossima_esecuzione_str = "N/A"

        if task["prossima_esecuzione"]:
            try:
                prossima_esecuzione = _coerce_datetime(task["prossima_esecuzione"])
                delta = prossima_esecuzione - now
                countdown_str = format_countdown(int(delta.total_seconds()))
                prossima_esecuzione_str = prossima_esecuzione.strftime("%H:%M:%S")
            except Exception as e:
                countdown_str = "❌ Errore calcolo"
                prossima_esecuzione_str = task["prossima_esecuzione"]
                if error_callback:
                    error_callback(task, e)

        macro_sequence = get_task_macro_sequence(task["id"])
        if macro_sequence:
            macro_name = macro_sequence[0].get("macro_nome", "N/A")
        else:
            macro_name = task.get("macro_nome", "N/A")

        entries.append((f"🔹 {idx}. {task['nome']}\n", "task_name"))
        entries.append((f"   Macro: {macro_name}\n", None))
        entries.append((f"   ⏰ {prossima_esecuzione_str}\n", None))
        entries.append((f"   ⏳ {countdown_str}\n", "countdown"))
        if idx < len(active_tasks):
            entries.append(("\n", None))

    return entries
