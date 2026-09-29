"""Bind supervised GUI learning evidence to metadata-only network observation."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

import psutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NETWORK_ROOT = PROJECT_ROOT / ".tools" / "network_observation"
START_SCRIPT = PROJECT_ROOT / "scripts" / "start_network_observation.ps1"
STOP_SCRIPT = PROJECT_ROOT / "scripts" / "stop_network_observation.ps1"
MITMDUMP_PATH = PROJECT_ROOT / ".tools" / "mitmproxy" / "Scripts" / "mitmdump.exe"


def find_process_pid(exe_name: str) -> int | None:
    target = (exe_name or "").casefold()
    candidates: list[tuple[float, int]] = []
    for process in psutil.process_iter(("name", "pid", "create_time")):
        try:
            if (process.info.get("name") or "").casefold() != target:
                continue
            candidates.append(
                (float(process.info.get("create_time") or 0.0), int(process.info["pid"]))
            )
        except (psutil.AccessDenied, psutil.NoSuchProcess, TypeError, ValueError):
            continue
    return max(candidates, default=(0.0, 0))[1] or None


def start_or_attach_learning_network_observation(
    *,
    target_pid: int,
    duration_seconds: int,
    enabled: bool = True,
    root: str | Path = DEFAULT_NETWORK_ROOT,
    startup_timeout_seconds: float = 12.0,
) -> dict[str, Any]:
    """Attach an active compatible observer or start one without blocking learning."""

    if not enabled:
        return _unavailable_binding(target_pid, "disabled_by_operator")
    if int(target_pid) <= 0:
        return _unavailable_binding(target_pid, "target_process_not_found")
    network_root = Path(root)
    active = discover_active_network_observation(target_pid=target_pid, root=network_root)
    if active is not None:
        return {**active, "owned_by_learning_session": False, "status": "active"}
    if _active_pid(network_root) is not None:
        return _unavailable_binding(target_pid, "active_observer_targets_another_process")
    if not MITMDUMP_PATH.is_file():
        return _unavailable_binding(target_pid, "mitmproxy_runtime_missing")
    if not START_SCRIPT.is_file():
        return _unavailable_binding(target_pid, "start_script_missing")

    existing_sessions = {path.name for path in _session_directories(network_root)}
    duration_minutes = max(1, int(math.ceil(max(10, duration_seconds) / 60)) + 1)
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        launcher = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(START_SCRIPT),
                "-TargetPid",
                str(int(target_pid)),
                "-Minutes",
                str(duration_minutes),
            ],
            cwd=str(PROJECT_ROOT),
            creationflags=creation_flags,
        )
    except OSError as exc:
        return _unavailable_binding(target_pid, f"observer_launch_failed:{type(exc).__name__}")

    deadline = time.monotonic() + max(1.0, float(startup_timeout_seconds))
    while time.monotonic() < deadline:
        binding = discover_active_network_observation(target_pid=target_pid, root=network_root)
        if binding is not None and binding["network_session_id"] not in existing_sessions:
            return {
                **binding,
                "owned_by_learning_session": True,
                "launcher_pid": launcher.pid,
                "status": "active",
            }
        if launcher.poll() is not None:
            break
        time.sleep(0.1)
    return _unavailable_binding(target_pid, "observer_startup_timeout_or_early_exit")


def discover_active_network_observation(
    *,
    target_pid: int,
    root: str | Path = DEFAULT_NETWORK_ROOT,
    pid_exists: Callable[[int], bool] = psutil.pid_exists,
) -> dict[str, Any] | None:
    network_root = Path(root)
    proxy_pid = _active_pid(network_root)
    if proxy_pid is None or not pid_exists(proxy_pid):
        return None
    for session_dir in reversed(_session_directories(network_root)):
        session_path = session_dir / "session.json"
        try:
            payload = json.loads(session_path.read_text(encoding="utf-8-sig"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        if int(payload.get("target_pid") or 0) != int(target_pid):
            continue
        events_path = Path(payload.get("events_path") or session_dir / "events.jsonl")
        if not events_path.is_absolute():
            events_path = session_dir / events_path
        return {
            "schema": "doomsday.learning.network-binding.v1",
            "capture_policy": "metadata-only-tls-passthrough",
            "target_pid": int(target_pid),
            "proxy_pid": proxy_pid,
            "network_session_id": session_dir.name,
            "network_session_dir": session_dir.resolve().as_posix(),
            "events_path": events_path.resolve().as_posix(),
            "annotations_path": (session_dir / "annotations.jsonl").resolve().as_posix(),
            "linked_at": _utc_now(),
        }
    return None


def capture_network_cursor(binding: dict[str, Any] | None) -> dict[str, Any]:
    if not binding or binding.get("status") != "active":
        return {"event_count": 0, "captured_at": _utc_now(), "available": False}
    path = Path(str(binding["events_path"]))
    try:
        event_count = _count_nonempty_lines(path)
    except OSError:
        return {"event_count": 0, "captured_at": _utc_now(), "available": False}
    return {
        "event_count": event_count,
        "captured_at": _utc_now(),
        "available": True,
    }


def build_network_correlation_window(
    *,
    binding: dict[str, Any] | None,
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    available = bool(before.get("available") and after.get("available") and binding)
    before_count = int(before.get("event_count") or 0)
    after_count = int(after.get("event_count") or 0)
    return {
        "schema": "doomsday.learning.network-correlation.v1",
        "available": available,
        "network_session_id": (binding or {}).get("network_session_id"),
        "event_index_start": before_count + 1 if available else None,
        "event_index_end": after_count if available else None,
        "event_count": max(0, after_count - before_count) if available else 0,
        "window_started_at": before.get("captured_at"),
        "window_ended_at": after.get("captured_at"),
        "semantic_status": "temporal_candidate_requires_repetition" if available else "unavailable",
    }


def append_learning_network_marker(
    *,
    binding: dict[str, Any] | None,
    learning_session_name: str,
    sequence_index: int,
    event_time_ms: int,
    ui_node_id: str,
    network_cursor: dict[str, Any],
) -> None:
    if not binding or binding.get("status") != "active":
        return
    payload = {
        "schema": "doomsday.network-observation-marker.v1",
        "observed_at": _utc_now(),
        "label": "learning_click",
        "learning_session_name": learning_session_name,
        "sequence_index": int(sequence_index),
        "event_time_ms": int(event_time_ms),
        "ui_node_id": ui_node_id,
        "event_count_before": int(network_cursor.get("event_count") or 0),
    }
    path = Path(str(binding["annotations_path"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def stop_owned_learning_network_observation(
    binding: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not binding:
        return None
    result = dict(binding)
    result["final_cursor"] = capture_network_cursor(binding)
    if not binding.get("owned_by_learning_session"):
        result["lifecycle"] = "attached_observer_left_running"
        return result
    if STOP_SCRIPT.is_file():
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(STOP_SCRIPT),
                ],
                cwd=str(PROJECT_ROOT),
                creationflags=creation_flags,
                check=False,
                timeout=15,
            )
            result["lifecycle"] = "owned_observer_stop_requested"
        except (OSError, subprocess.SubprocessError):
            result["lifecycle"] = "owned_observer_stop_failed"
    return result


def summarize_learning_network_correlations(
    session_dir: str | Path,
    *,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Materialize safe per-click traffic fingerprints from recorded index windows."""

    learning_dir = Path(session_dir)
    manifest = json.loads((learning_dir / "session.json").read_text(encoding="utf-8"))
    binding = manifest.get("network_observation") or {}
    events_path = binding.get("events_path")
    if not events_path:
        payload = _empty_correlation_summary(manifest, "network_events_unavailable")
        return _write_correlation_summary(learning_dir, payload, output_path)

    network_records = _read_jsonl(Path(events_path))
    learning_events = _read_jsonl(learning_dir / "events.jsonl")
    correlations: list[dict[str, Any]] = []
    for learning_event in learning_events:
        window = learning_event.get("network_correlation") or {}
        start = window.get("event_index_start")
        end = window.get("event_index_end")
        if not window.get("available") or start is None or end is None:
            records: list[dict[str, Any]] = []
        else:
            records = network_records[max(0, int(start) - 1) : max(0, int(end))]
        message_records = [
            record
            for record in records
            if record.get("event_type") in {"tcp_message", "udp_message"}
        ]
        application_messages = [
            record
            for record in message_records
            if max(
                int(record.get("request_bytes") or 0),
                int(record.get("response_bytes") or 0),
            )
            > 4
        ]
        shape = [_message_shape(record) for record in application_messages]
        correlations.append(
            {
                "sequence_index": int(learning_event.get("sequence_index") or 0),
                "event_time_ms": int(learning_event.get("time") or 0),
                "ui_node_id": learning_event.get("ui_node_id"),
                "game_element_id": learning_event.get("game_element_id"),
                "frame_paths": [
                    frame.get("path")
                    for frame in learning_event.get("learning_frames", [])
                    if frame.get("path")
                ],
                "network_event_index_start": start,
                "network_event_index_end": end,
                "network_record_count": len(records),
                "message_count": len(message_records),
                "application_message_count": len(application_messages),
                "application_shape": shape,
                "shape_fingerprint": _shape_fingerprint(shape),
                "first_response_latency_ms": _first_response_latency_ms(application_messages),
                "semantic_status": "candidate_requires_repetition_and_visual_validation",
            }
        )
    payload = {
        "schema": "doomsday.learning.network-correlation-summary.v1",
        "learning_session_name": manifest.get("session_name"),
        "scenario": manifest.get("scenario"),
        "domain": manifest.get("domain"),
        "network_session_id": binding.get("network_session_id"),
        "generated_at": _utc_now(),
        "correlations": correlations,
    }
    return _write_correlation_summary(learning_dir, payload, output_path)


def _message_shape(record: dict[str, Any]) -> dict[str, Any]:
    request_bytes = int(record.get("request_bytes") or 0)
    response_bytes = int(record.get("response_bytes") or 0)
    return {
        "transport": record.get("transport"),
        "server_port": int(record.get("server_port") or 0),
        "direction": (record.get("metadata") or {}).get("direction"),
        "bytes": request_bytes or response_bytes,
    }


def _shape_fingerprint(shape: list[dict[str, Any]]) -> str:
    if not shape:
        return "no_application_messages"
    canonical = json.dumps(shape, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _first_response_latency_ms(records: list[dict[str, Any]]) -> int | None:
    client_time: datetime | None = None
    for record in records:
        direction = (record.get("metadata") or {}).get("direction")
        try:
            observed_at = datetime.fromisoformat(str(record.get("observed_at")))
        except (TypeError, ValueError):
            continue
        if direction == "client_to_server" and client_time is None:
            client_time = observed_at
        elif direction == "server_to_client" and client_time is not None:
            return max(0, int(round((observed_at - client_time).total_seconds() * 1000)))
    return None


def _empty_correlation_summary(manifest: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "schema": "doomsday.learning.network-correlation-summary.v1",
        "learning_session_name": manifest.get("session_name"),
        "scenario": manifest.get("scenario"),
        "domain": manifest.get("domain"),
        "generated_at": _utc_now(),
        "status": "partial",
        "reason": reason,
        "correlations": [],
    }


def _write_correlation_summary(
    learning_dir: Path,
    payload: dict[str, Any],
    output_path: str | Path | None,
) -> dict[str, Any]:
    target = Path(output_path) if output_path else learning_dir / "network_correlation_summary.json"
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return {**payload, "path": target.resolve().as_posix()}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _active_pid(root: Path) -> int | None:
    try:
        return int((root / "active.pid").read_text(encoding="ascii").strip())
    except (FileNotFoundError, OSError, TypeError, ValueError):
        return None


def _session_directories(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        (
            path
            for path in root.iterdir()
            if path.is_dir()
            and len(path.name) == 15
            and path.name[:8].isdigit()
            and path.name[8] == "_"
            and path.name[9:].isdigit()
        ),
        key=lambda path: path.name,
    )


def _count_nonempty_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig") as handle:
        return sum(1 for line in handle if line.strip())


def _unavailable_binding(target_pid: int, reason: str) -> dict[str, Any]:
    return {
        "schema": "doomsday.learning.network-binding.v1",
        "status": "unavailable",
        "target_pid": int(target_pid),
        "reason": reason,
        "linked_at": _utc_now(),
        "owned_by_learning_session": False,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "append_learning_network_marker",
    "build_network_correlation_window",
    "capture_network_cursor",
    "discover_active_network_observation",
    "find_process_pid",
    "start_or_attach_learning_network_observation",
    "stop_owned_learning_network_observation",
    "summarize_learning_network_correlations",
]
