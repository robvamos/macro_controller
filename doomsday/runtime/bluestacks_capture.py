"""Adapter screenshot per una sessione ADB BlueStacks già esistente.

Questo modulo non contiene codice per avviare, connettere o riconnettere ADB.
Il trasporto deve essere creato e autenticato esplicitamente dall'esterno.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Protocol, Sequence

from PIL import Image

from doomsday.roster_live.artifact_store import MAX_PNG_BYTES, validate_png_bytes
from doomsday.services.live_roster_service import CaptureMethod
from doomsday.vision.desktop_capture import assess_frame_quality


@dataclass(frozen=True, slots=True)
class AdbSessionStatus:
    ready: bool
    instance_name: str
    endpoint: str
    serial: str
    player_process_running: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class CaptureProviderHealth:
    available: bool
    reason: str
    endpoint: str = ""
    serial: str = ""


class ExistingAdbSession(Protocol):
    """Trasporto già attivo; nessun metodo di lifecycle è ammesso."""

    def status(self) -> AdbSessionStatus: ...

    def exec_out(self, argv: Sequence[str], *, timeout: float, max_bytes: int) -> bytes: ...


class BlueStacksAdbCaptureProvider:
    runtime_id = "bluestacks5"
    capture_method = CaptureMethod.BLUESTACKS_ADB
    _ALLOWED_COMMAND = ("screencap", "-p")

    def __init__(
        self,
        session: ExistingAdbSession,
        *,
        expected_instance: str,
        expected_endpoint: str,
        expected_serial: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.session = session
        self.expected_instance = expected_instance
        self.expected_endpoint = expected_endpoint
        self.expected_serial = expected_serial
        self.timeout_seconds = max(0.5, min(15.0, float(timeout_seconds)))

    def health(self) -> CaptureProviderHealth:
        status = self.session.status()
        if not status.player_process_running:
            return CaptureProviderHealth(False, "Istanza BlueStacks non in esecuzione.")
        if not status.ready:
            return CaptureProviderHealth(False, status.reason or "Sessione ADB non pronta.")
        if status.instance_name != self.expected_instance:
            return CaptureProviderHealth(False, "Istanza ADB diversa da quella selezionata.")
        if status.endpoint != self.expected_endpoint:
            return CaptureProviderHealth(False, "Endpoint ADB non corrispondente.")
        if status.serial != self.expected_serial:
            return CaptureProviderHealth(False, "Seriale ADB non corrispondente.")
        return CaptureProviderHealth(True, "Sessione ADB preesistente verificata.", status.endpoint, status.serial)

    def capture_frame(self):
        health = self.health()
        if not health.available:
            raise RuntimeError(health.reason)
        payload = self.session.exec_out(
            self._ALLOWED_COMMAND,
            timeout=self.timeout_seconds,
            max_bytes=MAX_PNG_BYTES,
        )
        validate_png_bytes(payload)
        with Image.open(BytesIO(payload)) as image:
            frame = image.convert("RGB").copy()
        quality = assess_frame_quality(frame)
        if not quality.valid:
            raise RuntimeError(quality.reason)
        return frame


def resolve_unique_adb_endpoint(runtime_record: dict, instance_name: str) -> str:
    """Rifiuta configurazioni statiche in cui la porta non identifica l'istanza."""
    instances = runtime_record.get("instances") or []
    selected = next((item for item in instances if item.get("name") == instance_name), None)
    if selected is None:
        raise KeyError(f"Istanza BlueStacks non registrata: {instance_name}")
    port = selected.get("adb_port")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("Porta ADB non valida.")
    collisions = [item.get("name") for item in instances if item.get("adb_port") == port]
    if len(collisions) != 1:
        raise ValueError(
            f"Porta ADB {port} ambigua tra {', '.join(str(item) for item in collisions)}; "
            "serve una sessione preesistente con identità verificata."
        )
    return f"127.0.0.1:{port}"


__all__ = [
    "AdbSessionStatus",
    "BlueStacksAdbCaptureProvider",
    "CaptureProviderHealth",
    "ExistingAdbSession",
    "resolve_unique_adb_endpoint",
]
