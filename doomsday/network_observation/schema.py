"""Safe schemas for learning network shapes without retaining credentials.

This module is deliberately independent from mitmproxy.  The optional proxy
addon emits this schema, while the rest of DDassistant can test and consume it
without making a traffic interception tool a runtime dependency.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlsplit


SCHEMA = "doomsday.network-observation.v1"

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_HEX_RE = re.compile(r"^[0-9a-f]{16,}$", re.IGNORECASE)
_INTEGER_RE = re.compile(r"^\d+$")
_OPAQUE_RE = re.compile(r"^[A-Za-z0-9_-]{24,}={0,2}$")
_SENSITIVE_QUERY_RE = re.compile(
    r"(?:auth|bearer|credential|key|password|secret|session|signature|ticket|token)",
    re.IGNORECASE,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def normalize_path(path: str) -> str:
    """Replace likely identifiers while preserving a useful route template."""

    clean_path = urlsplit(path or "/").path or "/"
    normalized: list[str] = []
    for segment in clean_path.split("/"):
        if not segment:
            normalized.append(segment)
        elif _UUID_RE.fullmatch(segment):
            normalized.append("{uuid}")
        elif _HEX_RE.fullmatch(segment):
            normalized.append("{hex}")
        elif _INTEGER_RE.fullmatch(segment):
            normalized.append("{id}")
        elif _OPAQUE_RE.fullmatch(segment):
            normalized.append("{opaque}")
        else:
            normalized.append(segment)
    result = "/".join(normalized)
    return result if result.startswith("/") else f"/{result}"


def safe_query_keys(url: str) -> tuple[str, ...]:
    """Keep parameter names only; mask names that themselves disclose secrets."""

    keys: set[str] = set()
    for key, _value in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        keys.add("{sensitive}" if _SENSITIVE_QUERY_RE.search(key) else key[:80])
    return tuple(sorted(keys))


@dataclass(frozen=True, slots=True)
class MetadataRecord:
    event_type: str
    transport: str
    observed_at: str = field(default_factory=utc_now_iso)
    flow_id: str = ""
    server_host: str = ""
    server_port: int = 0
    sni: str = ""
    alpn: tuple[str, ...] = ()
    method: str = ""
    scheme: str = ""
    path_template: str = ""
    query_keys: tuple[str, ...] = ()
    status_code: int = 0
    request_content_type: str = ""
    response_content_type: str = ""
    request_bytes: int = 0
    response_bytes: int = 0
    message_count: int = 0
    duration_ms: int = 0
    error_class: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise ValueError("event_type is required")
        if self.server_port < 0 or self.server_port > 65535:
            raise ValueError("server_port must be between 0 and 65535")
        for value in (self.request_bytes, self.response_bytes, self.message_count, self.duration_ms):
            if value < 0:
                raise ValueError("size, count and duration fields cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, **asdict(self)}


def build_http_record(
    *,
    flow_id: str,
    method: str,
    url: str,
    status_code: int = 0,
    server_host: str = "",
    server_port: int = 0,
    request_content_type: str = "",
    response_content_type: str = "",
    request_bytes: int = 0,
    response_bytes: int = 0,
    duration_ms: int = 0,
) -> MetadataRecord:
    parsed = urlsplit(url)
    return MetadataRecord(
        event_type="http_response" if status_code else "http_request",
        transport="https" if parsed.scheme.casefold() == "https" else "http",
        flow_id=flow_id,
        server_host=(server_host or parsed.hostname or "").casefold(),
        server_port=server_port or parsed.port or (443 if parsed.scheme.casefold() == "https" else 80),
        method=method.upper(),
        scheme=parsed.scheme.casefold(),
        path_template=normalize_path(parsed.path),
        query_keys=safe_query_keys(url),
        status_code=status_code,
        request_content_type=request_content_type.split(";", 1)[0].strip().casefold(),
        response_content_type=response_content_type.split(";", 1)[0].strip().casefold(),
        request_bytes=request_bytes,
        response_bytes=response_bytes,
        duration_ms=duration_ms,
    )


@dataclass(frozen=True, slots=True)
class ObservationSummary:
    record_count: int
    transports: Mapping[str, int]
    endpoints: tuple[Mapping[str, Any], ...]
    servers: tuple[Mapping[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize_observations(
    records: Iterable[MetadataRecord | Mapping[str, Any]],
) -> ObservationSummary:
    """Aggregate shapes only; never infer a game action from temporal proximity."""

    transport_counts: dict[str, int] = {}
    endpoints: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    servers: dict[tuple[str, int, str], dict[str, Any]] = {}
    count = 0
    for item in records:
        data = item.to_dict() if isinstance(item, MetadataRecord) else dict(item)
        count += 1
        transport = str(data.get("transport", "unknown") or "unknown")
        transport_counts[transport] = transport_counts.get(transport, 0) + 1

        host = str(data.get("server_host", ""))
        port = int(data.get("server_port", 0) or 0)
        if host or port:
            server_key = (host, port, transport)
            server = servers.setdefault(
                server_key,
                {"server_host": host, "server_port": port, "transport": transport, "count": 0},
            )
            server["count"] += 1

        method = str(data.get("method", ""))
        path = str(data.get("path_template", ""))
        if method and path:
            endpoint_key = (host, method, path, transport)
            endpoint = endpoints.setdefault(
                endpoint_key,
                {
                    "server_host": host,
                    "method": method,
                    "path_template": path,
                    "transport": transport,
                    "count": 0,
                    "status_codes": set(),
                },
            )
            endpoint["count"] += 1
            status = int(data.get("status_code", 0) or 0)
            if status:
                endpoint["status_codes"].add(status)

    endpoint_rows = []
    for value in endpoints.values():
        row = dict(value)
        row["status_codes"] = sorted(row["status_codes"])
        endpoint_rows.append(row)
    endpoint_rows.sort(key=lambda item: (-item["count"], item["server_host"], item["path_template"]))
    server_rows = sorted(
        servers.values(), key=lambda item: (-item["count"], item["server_host"], item["server_port"])
    )
    return ObservationSummary(
        record_count=count,
        transports=dict(sorted(transport_counts.items())),
        endpoints=tuple(endpoint_rows),
        servers=tuple(server_rows),
    )


def content_length(parts: Sequence[bytes | bytearray | memoryview]) -> int:
    return sum(len(part) for part in parts)


__all__ = [
    "MetadataRecord",
    "ObservationSummary",
    "SCHEMA",
    "build_http_record",
    "content_length",
    "normalize_path",
    "safe_query_keys",
    "summarize_observations",
    "utc_now_iso",
]
