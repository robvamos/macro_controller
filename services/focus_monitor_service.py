"""Servizio per il monitoraggio del focus della finestra applicativa."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from core.app_state import AppState
from services.operation_state_service import OperationStateService


class FocusMonitorService:
    def __init__(self, state: AppState, state_service: OperationStateService):
        self.state = state
        self.state_service = state_service

    def check_app_focus(self, active_window_id: int | None, app_window_id: int) -> tuple[bool, bool]:
        """Restituisce (current_focus, changed) aggiornando lo stato quando serve."""
        current_focus = bool(active_window_id and active_window_id == app_window_id)
        changed = current_focus != self.state.last_focus_state
        if changed:
            self.state_service.set_focus_state(current_focus)
        return current_focus, changed

    def start_monitoring(
        self,
        *,
        is_gui_available: Callable[[], bool],
        poll_focus: Callable[[], None],
        on_error: Callable[[Exception], None],
        poll_interval: float = 0.1,
        error_interval: float = 1.0,
    ) -> bool:
        """Avvia il thread di monitoraggio se non gia' attivo."""
        if self.state.focus_monitor_active:
            return False

        self.state_service.set_focus_monitoring(True)

        def focus_monitor_loop():
            while self.state.focus_monitor_active:
                try:
                    if not is_gui_available():
                        break
                    poll_focus()
                    time.sleep(poll_interval)
                except Exception as exc:
                    on_error(exc)
                    time.sleep(error_interval)

        focus_monitor_thread = threading.Thread(target=focus_monitor_loop, daemon=True)
        focus_monitor_thread.start()
        self.state_service.set_focus_monitoring(True, focus_monitor_thread)
        return True

    def stop_monitoring(self, join_timeout: float = 0.5) -> bool:
        """Ferma il monitoraggio e attende brevemente il thread."""
        if not self.state.focus_monitor_active:
            return False

        focus_monitor_thread = self.state.focus_monitor_thread
        self.state_service.set_focus_monitoring(False, None)
        if focus_monitor_thread and focus_monitor_thread.is_alive():
            focus_monitor_thread.join(timeout=join_timeout)
        return True

    def mark_focus_in(self) -> bool:
        """Segna il ritorno del focus se necessario."""
        if self.state.last_focus_state:
            return False
        self.state_service.set_focus_state(True)
        return True

    def mark_focus_out(self) -> bool:
        """Segna la perdita del focus se necessario."""
        if not self.state.last_focus_state:
            return False
        self.state_service.set_focus_state(False)
        return True
