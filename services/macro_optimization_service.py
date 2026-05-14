"""Utility per l'ottimizzazione delle macro."""

from __future__ import annotations

import datetime


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


def build_optimized_macro_name(original_name):
    """Genera un nome leggibile per la macro ottimizzata."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{original_name}_optimized_{timestamp}"
