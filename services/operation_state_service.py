"""Helper per le transizioni di stato di registrazione/riproduzione."""

from __future__ import annotations

import time

from core.app_state import AppState


class OperationStateService:
    def __init__(self, state: AppState):
        self.state = state

    def reset_playback(self) -> None:
        self.state.playing_flag = False
        self.state.running_loop = False
        self.state.current_target_exe = None

    def start_playback(self, *, loop_enabled: bool, target_exe: str | None = None) -> None:
        self.state.playing_flag = True
        self.state.running_loop = loop_enabled
        self.state.current_target_exe = target_exe

    def start_recording(self, target_exe: str) -> None:
        self.state.recording_flag = True
        self.state.current_target_exe = target_exe

    def stop_recording(self) -> None:
        self.state.recording_flag = False
        self.state.current_target_exe = None

    def set_target_exe(self, target_exe: str | None) -> None:
        self.state.current_target_exe = target_exe

    def start_recording_timer(self, duration_sec: int) -> None:
        self.state.recording_timer_active = True
        self.state.recording_start_time = time.time()
        self.state.recording_duration = duration_sec

    def stop_recording_timer(self) -> None:
        self.state.recording_timer_active = False
        self.state.recording_start_time = None
        self.state.recording_duration = 0
        self.state.recording_timer_job = None

    def set_recording_timer_job(self, job_id) -> None:
        self.state.recording_timer_job = job_id

    def set_focus_monitoring(self, active: bool, thread=None) -> None:
        self.state.focus_monitor_active = active
        if thread is not None or not active:
            self.state.focus_monitor_thread = thread

    def set_focus_state(self, has_focus: bool) -> None:
        self.state.last_focus_state = has_focus
