"""Stato operativo condiviso dell'applicazione."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Thread


@dataclass
class AppState:
    running_loop: bool = False
    recording_flag: bool = False
    playing_flag: bool = False
    recording_timer_active: bool = False
    recording_start_time: float | None = None
    recording_duration: int = 0
    recording_timer_job: str | None = None
    focus_monitor_active: bool = False
    focus_monitor_thread: Thread | None = None
    last_focus_state: bool = True
    current_target_exe: str | None = None

