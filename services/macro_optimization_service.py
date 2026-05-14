"""Utility per l'ottimizzazione delle macro."""

from __future__ import annotations

import datetime


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


def compress_consecutive_mouse_moves(events):
    """Comprime sequenze consecutive di mouse move in un solo evento.

    Per rendere la macro piu' rapida, l'evento mantenuto usa:
    - la posizione finale dell'ultimo move della sequenza
    - il timestamp del primo move della sequenza
    """
    optimized_events = []
    pending_move = None

    for event in events:
        is_mouse_move = event.get("type") == "mouse" and event.get("event") == "move"

        if is_mouse_move:
            if pending_move is None:
                pending_move = dict(event)
            else:
                pending_move["x"] = event.get("x")
                pending_move["y"] = event.get("y")
                pending_move["normalized_x"] = event.get("normalized_x")
                pending_move["normalized_y"] = event.get("normalized_y")
            continue

        if pending_move is not None:
            optimized_events.append(pending_move)
            pending_move = None

        optimized_events.append(dict(event))

    if pending_move is not None:
        optimized_events.append(pending_move)

    return optimized_events


def remove_redundant_pre_click_moves(events):
    """Rimuove move ridondanti subito prima di mouse down/up nella stessa posizione.

    Il playback esegue gia' un move implicito su down/up, quindi il move precedente
    con coordinate identiche non aggiunge effetto visibile.
    """
    optimized_events = []
    removed_count = 0

    for event in events:
        is_click_transition = (
            event.get("type") == "mouse"
            and event.get("event") in {"down", "up"}
        )
        if optimized_events and is_click_transition:
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


def optimize_macro_events(events):
    """Applica le ottimizzazioni automatiche e restituisce anche un report."""
    compressed_events = compress_consecutive_mouse_moves(events)
    reduced_events, removed_pre_click_moves = remove_redundant_pre_click_moves(compressed_events)

    report = {
        "original_count": len(events),
        "compressed_move_count": len(events) - len(compressed_events),
        "removed_pre_click_moves": removed_pre_click_moves,
        "optimized_count": len(reduced_events),
        "total_removed": len(events) - len(reduced_events),
        "before_stats": compute_macro_event_stats(events),
        "after_stats": compute_macro_event_stats(reduced_events),
    }
    return reduced_events, report


def build_optimized_macro_name(original_name):
    """Genera un nome leggibile per la macro ottimizzata."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{original_name}_optimized_{timestamp}"
