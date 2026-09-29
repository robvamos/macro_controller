"""mitmproxy addon that persists only redacted protocol metadata.

TLS passthrough is enabled by default.  In that mode the addon observes the
ClientHello shape (SNI/ALPN and destination) and then asks mitmproxy to forward
the encrypted connection untouched.  Request bodies, response bodies, cookies,
authorization headers and raw TCP/UDP messages are never written to disk.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import threading
from typing import Any

from mitmproxy import ctx, http, tcp, tls, udp
from mitmproxy.proxy import server_hooks

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from doomsday.network_observation.schema import (
    MetadataRecord,
    build_http_record,
    build_stream_message_record,
    content_length,
)


class MetadataOnlyObserver:
    def __init__(self) -> None:
        self._output_path: Path | None = None
        self._lock = threading.Lock()

    def load(self, loader) -> None:
        loader.add_option(
            "dd_observation_output",
            str,
            "",
            "JSONL destination for redacted Doomsday network metadata.",
        )
        loader.add_option(
            "dd_observation_tls_passthrough",
            bool,
            True,
            "Forward TLS untouched after recording ClientHello metadata.",
        )

    def configure(self, updated) -> None:
        if "dd_observation_output" not in updated:
            return
        raw_path = str(ctx.options.dd_observation_output or "").strip()
        self._output_path = Path(raw_path).resolve() if raw_path else None
        if self._output_path is not None:
            self._output_path.parent.mkdir(parents=True, exist_ok=True)

    def running(self) -> None:
        self._write(MetadataRecord(event_type="session_start", transport="observer"))

    def done(self) -> None:
        self._write(MetadataRecord(event_type="session_end", transport="observer"))

    def server_connect(self, data: server_hooks.ServerConnectionHookData) -> None:
        host, port = _address(data.server.address)
        self._write(
            MetadataRecord(
                event_type="server_connect",
                transport=data.server.transport_protocol,
                flow_id=_safe_id(data.server.id),
                server_host=host,
                server_port=port,
            )
        )

    def tls_clienthello(self, data: tls.ClientHelloData) -> None:
        server = data.context.server
        host, port = _address(server.address)
        hello = data.client_hello
        alpn = tuple(value.decode("ascii", errors="replace")[:40] for value in hello.alpn_protocols)
        self._write(
            MetadataRecord(
                event_type="tls_clienthello",
                transport="tls",
                flow_id=_safe_id(server.id),
                server_host=host,
                server_port=port,
                sni=(hello.sni or "").casefold(),
                alpn=alpn,
                metadata={"passthrough": bool(ctx.options.dd_observation_tls_passthrough)},
            )
        )
        if ctx.options.dd_observation_tls_passthrough:
            data.ignore_connection = True

    def request(self, flow: http.HTTPFlow) -> None:
        host, port = _flow_server(flow)
        self._write(
            build_http_record(
                flow_id=_safe_id(flow.id),
                method=flow.request.method,
                url=flow.request.pretty_url,
                server_host=host,
                server_port=port,
                request_content_type=flow.request.headers.get("content-type", ""),
                request_bytes=len(flow.request.raw_content or b""),
            )
        )

    def response(self, flow: http.HTTPFlow) -> None:
        host, port = _flow_server(flow)
        started = flow.request.timestamp_start or flow.client_conn.timestamp_start
        finished = flow.response.timestamp_end or flow.response.timestamp_start
        duration_ms = _duration_ms(started, finished)
        self._write(
            build_http_record(
                flow_id=_safe_id(flow.id),
                method=flow.request.method,
                url=flow.request.pretty_url,
                status_code=flow.response.status_code,
                server_host=host,
                server_port=port,
                request_content_type=flow.request.headers.get("content-type", ""),
                response_content_type=flow.response.headers.get("content-type", ""),
                request_bytes=len(flow.request.raw_content or b""),
                response_bytes=len(flow.response.raw_content or b""),
                duration_ms=duration_ms,
            )
        )

    def tcp_start(self, flow: tcp.TCPFlow) -> None:
        self._write(_stream_record("tcp_start", "tcp", flow))

    def tcp_message(self, flow: tcp.TCPFlow) -> None:
        self._write(_stream_message_record("tcp", flow))

    def tcp_end(self, flow: tcp.TCPFlow) -> None:
        self._write(_stream_record("tcp_end", "tcp", flow))

    def udp_start(self, flow: udp.UDPFlow) -> None:
        self._write(_stream_record("udp_start", "udp", flow))

    def udp_message(self, flow: udp.UDPFlow) -> None:
        self._write(_stream_message_record("udp", flow))

    def udp_end(self, flow: udp.UDPFlow) -> None:
        self._write(_stream_record("udp_end", "udp", flow))

    def error(self, flow) -> None:
        host, port = _flow_server(flow)
        self._write(
            MetadataRecord(
                event_type="flow_error",
                transport=getattr(flow.server_conn, "transport_protocol", "unknown"),
                flow_id=_safe_id(flow.id),
                server_host=host,
                server_port=port,
                error_class=type(flow.error).__name__ if flow.error is not None else "unknown",
            )
        )

    def _write(self, record: MetadataRecord) -> None:
        if self._output_path is None:
            return
        encoded = json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True, default=str)
        with self._lock:
            with self._output_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded)
                handle.write("\n")


def _safe_id(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def _address(value: Any) -> tuple[str, int]:
    if not value:
        return "", 0
    try:
        return str(value[0]).casefold(), int(value[1])
    except (IndexError, TypeError, ValueError):
        return "", 0


def _flow_server(flow) -> tuple[str, int]:
    return _address(getattr(flow.server_conn, "address", None))


def _duration_ms(started: float | None, finished: float | None) -> int:
    if started is None or finished is None or finished < started:
        return 0
    return int(round((finished - started) * 1000))


def _stream_record(event_type: str, transport: str, flow) -> MetadataRecord:
    host, port = _flow_server(flow)
    client_parts = [message.content for message in flow.messages if message.from_client]
    server_parts = [message.content for message in flow.messages if not message.from_client]
    return MetadataRecord(
        event_type=event_type,
        transport=transport,
        flow_id=_safe_id(flow.id),
        server_host=host,
        server_port=port,
        request_bytes=content_length(client_parts),
        response_bytes=content_length(server_parts),
        message_count=len(flow.messages),
        duration_ms=_duration_ms(flow.client_conn.timestamp_start, flow.client_conn.timestamp_end),
    )


def _stream_message_record(transport: str, flow) -> MetadataRecord:
    host, port = _flow_server(flow)
    message = flow.messages[-1]
    return build_stream_message_record(
        flow_id=_safe_id(flow.id),
        transport=transport,
        from_client=bool(message.from_client),
        message_bytes=len(message.content),
        message_index=len(flow.messages),
        server_host=host,
        server_port=port,
    )


addons = [MetadataOnlyObserver()]
