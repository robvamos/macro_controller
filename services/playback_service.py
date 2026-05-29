"""Servizio di orchestrazione per il playback delle macro."""

from __future__ import annotations

from collections.abc import Callable

from core.app_state import AppState
from services.operation_state_service import OperationStateService


class PlaybackService:
    def __init__(self, state: AppState, state_service: OperationStateService):
        self.state = state
        self.state_service = state_service

    def _finish_playback(self, stop_focus_monitoring: Callable[[], None]) -> None:
        """Ripulisce sempre lo stato operativo a fine playback."""
        self.state_service.reset_playback()
        if not self.state.recording_flag:
            stop_focus_monitoring()

    def start_playback(self, *, loop_enabled: bool) -> bool:
        """Prenota lo stato di playback se nessuna riproduzione e' attiva."""
        if self.state.playing_flag:
            return False
        self.state_service.start_playback(loop_enabled=loop_enabled, target_exe=None)
        return True

    def run_playback(
        self,
        *,
        macro_events,
        target_exe: str,
        loop_enabled: bool,
        loop_delay: float,
        max_repetitions,
        gui_log: Callable[[str, str], None],
        event_callback,
        wait_for_app_window: Callable[..., bool],
        play_macro_events: Callable[..., None],
        is_playback_stop_requested: Callable[[], bool],
        start_focus_monitoring: Callable[[], None],
        stop_focus_monitoring: Callable[[], None],
        on_target_wait_cancelled: Callable[[], None],
        on_target_wait_failed: Callable[[str], None],
        on_before_playback: Callable[[], None],
        on_playback_finished: Callable[[], None],
    ) -> None:
        """Esegue l'attesa target e la riproduzione vera e propria."""
        window_found = wait_for_app_window(
            target_exe,
            gui_log,
            max_wait_time=15,
            check_recording_flag=False,
            should_cancel=is_playback_stop_requested,
        )

        if not window_found:
            self._finish_playback(stop_focus_monitoring)

            if is_playback_stop_requested():
                on_target_wait_cancelled()
                return

            on_target_wait_failed(target_exe)
            return

        self.state_service.set_target_exe(target_exe)
        start_focus_monitoring()
        try:
            on_before_playback()
            play_macro_events(
                macro_events,
                target_exe,
                log_callback=gui_log,
                loop_enabled=loop_enabled,
                loop_delay=loop_delay,
                max_repetitions=max_repetitions,
                event_callback=event_callback,
            )
        finally:
            self._finish_playback(stop_focus_monitoring)
            on_playback_finished()
