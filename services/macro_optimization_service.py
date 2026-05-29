"""Utility per l'ottimizzazione delle macro."""

from __future__ import annotations

import datetime
import math


MIN_SETTLE_DELAY_MS = 25
MIN_KEY_HOLD_MS = 20
MIN_KEY_GAP_MS = 15


def compute_macro_event_stats(events):
    """Restituisce statistiche sintetiche sugli eventi della macro."""
    total_events = len(events)
    duration_ms = max((event.get("time") or 0) for event in events) if events else 0
    mouse_moves = sum(1 for event in events if event.get("type") == "mouse" and event.get("event") == "move")
    mouse_clicks = sum(
        1
        for event in events
        if event.get("type") == "mouse" and event.get("event") in {"down", "up"}
    )
    scroll_events = sum(
        1
        for event in events
        if event.get("type") == "mouse" and event.get("event") == "scroll"
    )
    keyboard_events = sum(
        1
        for event in events
        if event.get("type") in {"keyboard", "key"}
    )
    return {
        "total_events": total_events,
        "duration_ms": duration_ms,
        "mouse_moves": mouse_moves,
        "mouse_clicks": mouse_clicks,
        "scroll_events": scroll_events,
        "keyboard_events": keyboard_events,
    }


def compress_consecutive_mouse_moves(events, min_settle_delay_ms=MIN_SETTLE_DELAY_MS):
    """Comprime sequenze consecutive di mouse move e recupera il tempo di trascinamento.

    Regole:
    - mantiene la posizione finale dell'ultimo move della sequenza
    - mantiene il timestamp del primo move della sequenza
    - anticipa gli eventi successivi rimuovendo il tempo speso nel trascinamento
    - conserva un piccolo margine minimo prima dell'azione successiva per dare
      all'interfaccia il tempo di reagire
    """
    optimized_events = []
    index = 0
    removed_time_ms = 0
    time_shift_ms = 0

    while index < len(events):
        event = events[index]
        is_mouse_move = event.get("type") == "mouse" and event.get("event") == "move"

        if not is_mouse_move:
            shifted_event = dict(event)
            shifted_event["time"] = max(0, (event.get("time") or 0) - time_shift_ms)
            optimized_events.append(shifted_event)
            index += 1
            continue

        sequence_start = index
        sequence_end = index
        while sequence_end + 1 < len(events):
            next_event = events[sequence_end + 1]
            next_is_move = next_event.get("type") == "mouse" and next_event.get("event") == "move"
            if not next_is_move:
                break
            sequence_end += 1

        first_move = events[sequence_start]
        last_move = events[sequence_end]
        pending_move = dict(first_move)
        pending_move["time"] = max(0, (first_move.get("time") or 0) - time_shift_ms)
        pending_move["x"] = last_move.get("x")
        pending_move["y"] = last_move.get("y")
        pending_move["normalized_x"] = last_move.get("normalized_x")
        pending_move["normalized_y"] = last_move.get("normalized_y")
        optimized_events.append(pending_move)

        if sequence_end + 1 < len(events):
            next_event = events[sequence_end + 1]
            first_time = first_move.get("time") or 0
            last_time = last_move.get("time") or first_time
            next_time = next_event.get("time") or last_time
            move_duration_ms = max(0, last_time - first_time)
            post_move_gap_ms = max(0, next_time - last_time)
            preserved_gap_ms = max(post_move_gap_ms, min_settle_delay_ms)
            removable_ms = max(0, (next_time - first_time) - preserved_gap_ms)
            time_shift_ms += removable_ms
            removed_time_ms += removable_ms

        index = sequence_end + 1

    return optimized_events, removed_time_ms


def remove_redundant_pre_click_moves(events):
    """Rimuove solo i move ridondanti prima del rilascio del click.

    Il move finale prima del ``down`` viene mantenuto: anche se il playback sposta
    gia' il cursore sul click, molte interfacce rispondono meglio se vedono prima
    un posizionamento stabile e poi il click. Invece il move subito prima dello
    ``up`` e' davvero superfluo, perche' il cursore si trova gia' nella posizione
    corretta dalla pressione appena eseguita.
    """
    optimized_events = []
    removed_count = 0

    for event in events:
        is_click_release = (
            event.get("type") == "mouse"
            and event.get("event") == "up"
        )
        if optimized_events and is_click_release:
            previous_event = optimized_events[-1]
            same_position = (
                previous_event.get("type") == "mouse"
                and previous_event.get("event") == "move"
                and previous_event.get("normalized_x") == event.get("normalized_x")
                and previous_event.get("normalized_y") == event.get("normalized_y")
            )
            if same_position:
                optimized_events.pop()
                removed_count += 1

        optimized_events.append(dict(event))

    return optimized_events, removed_count


def accelerate_keyboard_sequences(
    events,
    min_key_hold_ms=MIN_KEY_HOLD_MS,
    min_key_gap_ms=MIN_KEY_GAP_MS,
):
    """Accorcia i tempi morti tra eventi tastiera consecutivi.

    Mantiene una breve pressione minima per down/up dello stesso tasto e un
    piccolo gap per sequenze di digitazione, anticipando di conseguenza anche
    gli eventi successivi nella timeline.
    """
    optimized_events = []
    removed_time_ms = 0
    accelerated_events = 0
    time_shift_ms = 0
    previous_shifted_event = None

    for event in events:
        shifted_event = dict(event)
        original_time = event.get("time") or 0
        shifted_time = max(0, original_time - time_shift_ms)
        shifted_event["time"] = shifted_time

        is_keyboard_event = event.get("type") in {"keyboard", "key"}
        previous_is_keyboard = (
            previous_shifted_event is not None
            and previous_shifted_event.get("type") in {"keyboard", "key"}
        )

        if is_keyboard_event and previous_is_keyboard:
            same_key_hold = (
                previous_shifted_event.get("name") == event.get("name")
                and previous_shifted_event.get("event") == "down"
                and event.get("event") == "up"
            )
            required_gap_ms = min_key_hold_ms if same_key_hold else min_key_gap_ms
            minimum_time = (previous_shifted_event.get("time") or 0) + required_gap_ms

            if shifted_time > minimum_time:
                removable = shifted_time - minimum_time
                time_shift_ms += removable
                removed_time_ms += removable
                accelerated_events += 1
                shifted_time = minimum_time
                shifted_event["time"] = shifted_time

        optimized_events.append(shifted_event)
        previous_shifted_event = shifted_event

    return optimized_events, removed_time_ms, accelerated_events


def optimize_macro_events(events, optimize_keyboard_input=False):
    """Applica le ottimizzazioni automatiche e restituisce anche un report."""
    compressed_events, removed_move_time_ms = compress_consecutive_mouse_moves(events)
    reduced_events, removed_pre_click_moves = remove_redundant_pre_click_moves(compressed_events)
    optimized_events = reduced_events
    removed_keyboard_time_ms = 0
    accelerated_keyboard_events = 0

    if optimize_keyboard_input:
        optimized_events, removed_keyboard_time_ms, accelerated_keyboard_events = accelerate_keyboard_sequences(
            reduced_events
        )

    report = {
        "original_count": len(events),
        "compressed_move_count": len(events) - len(compressed_events),
        "removed_move_time_ms": removed_move_time_ms,
        "removed_pre_click_moves": removed_pre_click_moves,
        "removed_keyboard_time_ms": removed_keyboard_time_ms,
        "accelerated_keyboard_events": accelerated_keyboard_events,
        "optimized_count": len(optimized_events),
        "total_removed": len(events) - len(optimized_events),
        "before_stats": compute_macro_event_stats(events),
        "after_stats": compute_macro_event_stats(optimized_events),
    }
    return optimized_events, report


def compute_macro_duration_seconds(events, minimum_seconds=1):
    """Converte la timeline eventi in una durata pratica in secondi."""
    duration_ms = compute_macro_event_stats(events)["duration_ms"]
    if duration_ms <= 0:
        return minimum_seconds
    return max(minimum_seconds, math.ceil(duration_ms / 1000))


def build_optimized_macro_name(original_name):
    """Genera un nome leggibile per la macro ottimizzata."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{original_name}_optimized_{timestamp}"
