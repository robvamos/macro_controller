"""Analyze annotated metadata-only game traffic without decoding or replaying it."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


MESSAGE_TYPES = {"tcp_message", "udp_message"}
HEARTBEAT_MAX_BYTES = 4
EXCHANGE_TIMEOUT_MS = 2_000
SERVER_PUSH_MIN_BYTES = 256


def analyze_annotated_network_session(
    session_dir: str | Path,
    *,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build safe traffic-shape candidates for consecutive semantic markers."""

    base = Path(session_dir)
    events = _read_jsonl(base / "events.jsonl")
    annotations = _read_jsonl(base / "annotations.jsonl")
    session = json.loads((base / "session.json").read_text(encoding="utf-8-sig"))
    messages = [record for record in events if record.get("event_type") in MESSAGE_TYPES]
    shape_counts = Counter(_shape_key(record) for record in messages)
    recurring_background = {
        shape
        for shape, count in shape_counts.items()
        if _shape_bytes(shape) <= HEARTBEAT_MAX_BYTES and count >= 3
    }

    windows = []
    for index, marker in enumerate(annotations):
        start = _marker_cursor(marker)
        has_closing_marker = index + 1 < len(annotations)
        end = _marker_cursor(annotations[index + 1]) if has_closing_marker else start
        window_records = events[max(0, start) : max(start, end)]
        window_messages = [
            record for record in window_records if record.get("event_type") in MESSAGE_TYPES
        ]
        application_messages = [
            record
            for record in window_messages
            if _shape_key(record) not in recurring_background
            and _record_bytes(record) > HEARTBEAT_MAX_BYTES
        ]
        exchanges = _candidate_exchanges(application_messages)
        pushes = _candidate_server_pushes(application_messages)
        windows.append(
            {
                "declared_semantic_label": marker.get("label"),
                "marker_observed_at": marker.get("observed_at"),
                "event_index_start": start + 1,
                "event_index_end": end,
                "record_count": len(window_records),
                "message_count": len(window_messages),
                "application_message_count": len(application_messages),
                "channel_summary": _channel_summary(window_messages),
                "application_shape": _aggregate_shapes(application_messages),
                "shape_fingerprint": _shape_fingerprint(application_messages),
                "candidate_exchanges": exchanges,
                "candidate_server_pushes": pushes,
                "semantic_status": (
                    "unbounded_missing_next_marker"
                    if not has_closing_marker
                    else (
                        "candidate_requires_repetition_and_visual_validation"
                        if application_messages
                        else "no_distinct_application_shape_observed"
                    )
                ),
            }
        )

    payload = {
        "schema": "doomsday.annotated-network-analysis.v1",
        "network_session_id": base.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "capture_policy": {
            "capture_level": session.get("capture_level"),
            "tls_passthrough": bool(session.get("tls_passthrough")),
            "payloads_persisted": bool(session.get("payloads_persisted")),
            "replay_allowed": False,
        },
        "record_count": len(events),
        "message_count": len(messages),
        "channel_inventory": _channel_summary(messages),
        "recurring_background_shapes": [
            {
                "transport": shape[0],
                "server_port": shape[1],
                "direction": shape[2],
                "bytes": shape[3],
                "count": shape_counts[shape],
            }
            for shape in sorted(recurring_background)
        ],
        "semantic_windows": windows,
        "interpretation_policy": (
            "Manual markers declare operator intent. Traffic shapes remain candidates until the "
            "same fingerprint is repeated with visual confirmation in independent sessions."
        ),
    }
    target = (
        Path(output_path)
        if output_path
        else base / "annotated_network_analysis.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return {**payload, "path": target.resolve().as_posix()}


def _candidate_exchanges(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exchanges = []
    for index, request in enumerate(records):
        if _direction(request) != "client_to_server":
            continue
        request_bytes = _record_bytes(request)
        if request_bytes <= HEARTBEAT_MAX_BYTES:
            continue
        request_time = _parse_time(request.get("observed_at"))
        if request_time is None:
            continue
        for response in records[index + 1 :]:
            if _direction(response) != "server_to_client":
                continue
            if int(response.get("server_port") or 0) != int(request.get("server_port") or 0):
                continue
            response_time = _parse_time(response.get("observed_at"))
            if response_time is None:
                continue
            latency_ms = int(round((response_time - request_time).total_seconds() * 1000))
            if latency_ms < 0:
                continue
            if latency_ms > EXCHANGE_TIMEOUT_MS:
                break
            exchanges.append(
                {
                    "transport": request.get("transport"),
                    "server_port": int(request.get("server_port") or 0),
                    "request_bytes": request_bytes,
                    "response_bytes": _record_bytes(response),
                    "latency_ms": latency_ms,
                    "status": "shape_candidate_not_replayable",
                }
            )
            break
    return exchanges


def _candidate_server_pushes(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pushes = []
    for index, response in enumerate(records):
        if _direction(response) != "server_to_client":
            continue
        response_bytes = _record_bytes(response)
        if response_bytes < SERVER_PUSH_MIN_BYTES:
            continue
        response_time = _parse_time(response.get("observed_at"))
        if response_time is None:
            continue
        matched_request = False
        for request in reversed(records[:index]):
            if _direction(request) != "client_to_server":
                continue
            if _record_bytes(request) <= HEARTBEAT_MAX_BYTES:
                continue
            if int(request.get("server_port") or 0) != int(response.get("server_port") or 0):
                continue
            request_time = _parse_time(request.get("observed_at"))
            if request_time is None:
                continue
            latency_ms = int(round((response_time - request_time).total_seconds() * 1000))
            if 0 <= latency_ms <= EXCHANGE_TIMEOUT_MS:
                matched_request = True
            break
        if not matched_request:
            pushes.append(
                {
                    "transport": response.get("transport"),
                    "server_port": int(response.get("server_port") or 0),
                    "response_bytes": response_bytes,
                    "status": "unmatched_server_push_candidate",
                }
            )
    return pushes


def _channel_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[tuple[str, int], dict[str, Any]] = {}
    for record in records:
        key = (str(record.get("transport") or ""), int(record.get("server_port") or 0))
        item = totals.setdefault(
            key,
            {
                "transport": key[0],
                "server_port": key[1],
                "message_count": 0,
                "client_to_server_messages": 0,
                "server_to_client_messages": 0,
                "client_to_server_bytes": 0,
                "server_to_client_bytes": 0,
            },
        )
        item["message_count"] += 1
        direction = _direction(record)
        if direction == "client_to_server":
            item["client_to_server_messages"] += 1
            item["client_to_server_bytes"] += _record_bytes(record)
        elif direction == "server_to_client":
            item["server_to_client_messages"] += 1
            item["server_to_client_bytes"] += _record_bytes(record)
    return sorted(totals.values(), key=lambda item: (-item["message_count"], item["server_port"]))


def _aggregate_shapes(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(_shape_key(record) for record in records)
    return [
        {
            "transport": shape[0],
            "server_port": shape[1],
            "direction": shape[2],
            "bytes": shape[3],
            "count": count,
        }
        for shape, count in sorted(counts.items())
    ]


def _shape_fingerprint(records: list[dict[str, Any]]) -> str:
    shape = _aggregate_shapes(records)
    if not shape:
        return "no_distinct_application_shape"
    canonical = json.dumps(shape, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _marker_cursor(marker: dict[str, Any]) -> int:
    for key in ("event_count_before", "event_count", "event_count_after"):
        value = marker.get(key)
        if value is not None:
            return max(0, int(value))
    return 0


def _shape_key(record: dict[str, Any]) -> tuple[str, int, str, int]:
    return (
        str(record.get("transport") or ""),
        int(record.get("server_port") or 0),
        _direction(record),
        _record_bytes(record),
    )


def _shape_bytes(shape: tuple[str, int, str, int]) -> int:
    return int(shape[3])


def _record_bytes(record: dict[str, Any]) -> int:
    return int(record.get("request_bytes") or record.get("response_bytes") or 0)


def _direction(record: dict[str, Any]) -> str:
    return str((record.get("metadata") or {}).get("direction") or "")


def _parse_time(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


__all__ = ["analyze_annotated_network_session"]
