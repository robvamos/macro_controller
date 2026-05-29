"""Helper per creare e popolare le tab secondarie della finestra principale."""

from __future__ import annotations

from tkinter import ttk


def build_secondary_tabs(
    *,
    tab_control,
    setup_ui_graph_browser_interface,
    setup_scheduled_tasks_interface,
    setup_game_elements_interface,
    setup_settings_tab,
):
    """Crea le tab secondarie e richiama i relativi builder."""
    ui_graph_tab = ttk.Frame(tab_control)
    tab_control.add(ui_graph_tab, text="🧭 Grafo UI")
    setup_ui_graph_browser_interface(ui_graph_tab)

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
        "ui_graph_tab": ui_graph_tab,
        "scheduled_tasks_tab": scheduled_tasks_tab,
        "elements_tab": elements_tab,
        "settings_tab": settings_tab,
    }
