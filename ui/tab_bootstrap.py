"""Helper per creare e popolare le tab secondarie della finestra principale."""

from __future__ import annotations

from tkinter import ttk


def build_secondary_tabs(
    *,
    tab_control,
    setup_audio_samples_interface,
    setup_learning_lab_interface,
    setup_scheduled_tasks_interface,
    setup_game_elements_interface,
    setup_settings_tab,
):
    """Crea le tab secondarie e richiama i relativi builder."""
    audio_samples_tab = ttk.Frame(tab_control)
    tab_control.add(audio_samples_tab, text="Audio Campioni")
    setup_audio_samples_interface(audio_samples_tab)

    learning_lab_tab = ttk.Frame(tab_control)
    tab_control.add(learning_lab_tab, text="Learning Lab")
    setup_learning_lab_interface(learning_lab_tab)

    scheduled_tasks_tab = ttk.Frame(tab_control)
    tab_control.add(scheduled_tasks_tab, text="Scheduled Tasks")
    setup_scheduled_tasks_interface(scheduled_tasks_tab)

    elements_tab = ttk.Frame(tab_control)
    tab_control.add(elements_tab, text="🎮 Elementi")
    setup_game_elements_interface(elements_tab)

    settings_tab = ttk.Frame(tab_control)
    tab_control.add(settings_tab, text="⚙️ Settings")
    setup_settings_tab(settings_tab)

    return {
        "audio_samples_tab": audio_samples_tab,
        "learning_lab_tab": learning_lab_tab,
        "scheduled_tasks_tab": scheduled_tasks_tab,
        "elements_tab": elements_tab,
        "settings_tab": settings_tab,
    }
