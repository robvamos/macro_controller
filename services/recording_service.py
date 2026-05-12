"""Servizio di orchestrazione per registrazione e re-registrazione macro."""

from __future__ import annotations

from collections.abc import Callable

from core.app_state import AppState
from services.operation_state_service import OperationStateService


class RecordingService:
    def __init__(self, state: AppState, state_service: OperationStateService):
        self.state = state
        self.state_service = state_service

    def start_recording_session(self, *, target_exe: str, duration_sec: int) -> bool:
        """Prenota una sessione di registrazione se non ce n'e' gia' una attiva."""
        if self.state.recording_flag:
            return False
        self.state_service.start_recording(target_exe)
        if duration_sec > 0:
            self.state.recording_duration = duration_sec
        return True

    def run_new_macro_recording(
        self,
        *,
        macro_name: str,
        macro_desc: str,
        macro_duration: int,
        macro_exe: str,
        registra_eventi: Callable[..., list | None],
        save_macro: Callable[..., None],
        log_callback: Callable[[str, str], None],
        on_recording_started: Callable[[], None],
        on_empty_recording: Callable[[], None],
        on_save_error: Callable[[Exception], None],
        on_cancelled: Callable[[str], None],
        on_unhandled_error: Callable[[Exception], None],
        on_finished: Callable[[], None],
    ) -> None:
        """Esegue registrazione e salvataggio di una nuova macro."""
        try:
            log_callback(
                f"DEBUG: Chiamata a registra_eventi con nome='{macro_name}', durata={macro_duration}, exe='{macro_exe}'",
                "INFO",
            )
            on_recording_started()
            returned_events = registra_eventi(
                nome_macro=macro_name,
                durata_sec=macro_duration,
                target_exe=macro_exe,
                log_callback=log_callback,
            )

            log_callback(
                "DEBUG: registra_eventi ha restituito. Tipo di 'returned_events': "
                f"{type(returned_events)}. Lunghezza: "
                f"{len(returned_events) if isinstance(returned_events, list) else 'N/A'}",
                "INFO",
            )

            if returned_events is not None:
                if len(returned_events) == 0:
                    log_callback(
                        "⚠️ Attenzione: Nessun evento registrato durante l'intervallo specificato.",
                        "WARNING",
                    )
                    on_empty_recording()
                    return

                log_callback("DEBUG: Eventi registrati. Tentativo di salvataggio.", "INFO")
                try:
                    save_macro(macro_name, macro_desc, macro_duration, macro_exe, returned_events, log_callback)
                    log_callback(
                        f"✅ Macro '{macro_name}' salvata con successo con {len(returned_events)} eventi.",
                        "INFO",
                    )
                except Exception as exc:
                    on_save_error(exc)
            else:
                log_callback("⚠️ Registrazione annullata o processo target non trovato.", "WARNING")
                on_cancelled(macro_exe)

        except Exception as exc:
            on_unhandled_error(exc)
        finally:
            self.state_service.stop_recording()
            on_finished()

    def run_rerecording(
        self,
        *,
        macro_id: int,
        macro_name: str,
        macro_duration: int,
        macro_exe: str,
        registra_eventi: Callable[..., list | None],
        update_events_only: Callable[[int, list], None],
        log_callback: Callable[[str, str], None],
        on_update_error: Callable[[Exception], None],
        on_cancelled: Callable[[], None],
        on_unhandled_error: Callable[[Exception], None],
        on_finished: Callable[[], None],
    ) -> None:
        """Esegue la re-registrazione degli eventi di una macro esistente."""
        try:
            log_callback(
                f"DEBUG: Avvio re-registrazione per macro ID {macro_id}, nome '{macro_name}'...",
                "INFO",
            )
            new_events = registra_eventi(
                nome_macro=macro_name,
                durata_sec=macro_duration,
                target_exe=macro_exe,
                log_callback=log_callback,
            )

            if new_events is not None:
                log_callback(f"DEBUG: Nuovi eventi registrati: {len(new_events)}. Tentativo di aggiornamento.", "INFO")
                try:
                    update_events_only(macro_id, new_events)
                    log_callback(
                        f"✅ Macro '{macro_name}' re-registrata e aggiornata con successo con {len(new_events)} eventi.",
                        "INFO",
                    )
                except Exception as exc:
                    on_update_error(exc)
            else:
                log_callback("⚠️ Re-registrazione annullata o nessun evento acquisito.", "WARNING")
                on_cancelled()

        except Exception as exc:
            on_unhandled_error(exc)
        finally:
            self.state_service.stop_recording()
            on_finished()
