"""Pattern mining leggero sulle sessioni di learning UI del gioco."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from repositories.macro_repository import get_all_macros, load_macro_events


LEARNING_SYSTEM_KEYS = {
    "general_click_elements_learning",
    "launch_game_boot_click_elements",
    "launch_game_popup_cleanup",
}


@dataclass(slots=True)
class LearnedActionPattern:
    element_ids: tuple[int, ...]
    count: int
    confidence: float
    source_macro_ids: tuple[int, ...]
    suggested_macro_name: str
    notes: str


def collect_learning_click_sequences(*, system_keys=None):
    """Return click-element sequences from learning macros, preserving macro boundaries."""
    allowed_keys = set(system_keys or LEARNING_SYSTEM_KEYS)
    sequences = []
    for macro in get_all_macros():
        if macro.get("system_key") not in allowed_keys:
            continue
        events = load_macro_events(macro["id"])
        sequence = [
            int(event["game_element_id"])
            for event in events
            if event.get("type") == "mouse"
            and event.get("event") == "down"
            and event.get("game_element_id") is not None
        ]
        if sequence:
            sequences.append({"macro_id": macro["id"], "macro_name": macro["nome"], "element_ids": tuple(sequence)})
    return sequences


def suggest_repeated_learning_patterns(*, min_count=2, max_pattern_length=4):
    """Find repeated click sequences that are good candidates for future macro suggestions."""
    sequences = collect_learning_click_sequences()
    pattern_counts: Counter[tuple[int, ...]] = Counter()
    source_macro_ids: dict[tuple[int, ...], set[int]] = {}

    for sequence_record in sequences:
        element_ids = sequence_record["element_ids"]
        macro_id = sequence_record["macro_id"]
        for pattern_length in range(2, max_pattern_length + 1):
            if len(element_ids) < pattern_length:
                continue
            for index in range(0, len(element_ids) - pattern_length + 1):
                pattern = element_ids[index : index + pattern_length]
                pattern_counts[pattern] += 1
                source_macro_ids.setdefault(pattern, set()).add(macro_id)

    total_occurrences = sum(pattern_counts.values()) or 1
    suggestions = []
    for pattern, count in pattern_counts.items():
        if count < min_count:
            continue
        confidence = count / total_occurrences
        suggestions.append(
            LearnedActionPattern(
                element_ids=pattern,
                count=count,
                confidence=round(confidence, 4),
                source_macro_ids=tuple(sorted(source_macro_ids.get(pattern, set()))),
                suggested_macro_name=build_suggested_macro_name(pattern),
                notes=(
                    "Pattern non vincolante emerso da sessioni learning elevate. "
                    "Da proporre come macro candidata solo dopo conferma umana del significato."
                ),
            )
        )

    suggestions.sort(key=lambda item: (item.count, len(item.element_ids), item.confidence), reverse=True)
    return suggestions


def build_suggested_macro_name(element_ids):
    compact = "_".join(str(element_id) for element_id in element_ids[:4])
    return f"Macro candidata pattern elementi {compact}"


__all__ = [
    "LEARNING_SYSTEM_KEYS",
    "LearnedActionPattern",
    "build_suggested_macro_name",
    "collect_learning_click_sequences",
    "suggest_repeated_learning_patterns",
]
