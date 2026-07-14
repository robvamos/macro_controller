"""Storage immutabile degli artifact di cattura roster."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from io import BytesIO
from pathlib import Path
import re
from uuid import uuid4

from PIL import Image


MAX_PNG_BYTES = 32 * 1024 * 1024
MAX_DIMENSION = 12000


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    path: Path
    sha256: str
    width: int
    height: int
    byte_size: int
    captured_at: str


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", value.casefold()).strip("-") or "unknown"


def validate_png_bytes(payload: bytes) -> tuple[int, int]:
    if not payload or len(payload) > MAX_PNG_BYTES:
        raise ValueError("PNG vuoto o oltre il limite consentito.")
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Firma PNG non valida.")
    try:
        with Image.open(BytesIO(payload)) as image:
            image.verify()
        with Image.open(BytesIO(payload)) as image:
            width, height = image.size
    except Exception as exc:
        raise ValueError("PNG corrotto o troncato.") from exc
    if width <= 0 or height <= 0 or width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValueError("Dimensioni PNG non valide.")
    return width, height


class RosterArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def store_image(self, *, session_id: str, stage: str, hero_id: str, image) -> StoredArtifact:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return self.store_png_bytes(
            session_id=session_id,
            stage=stage,
            hero_id=hero_id,
            payload=buffer.getvalue(),
        )

    def store_png_bytes(
        self,
        *,
        session_id: str,
        stage: str,
        hero_id: str,
        payload: bytes,
    ) -> StoredArtifact:
        width, height = validate_png_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        directory = self.root / _slug(session_id)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{_slug(stage)}-{_slug(hero_id)}-{digest[:16]}.png"
        if not destination.exists():
            temporary = directory / f".{destination.name}.{uuid4().hex}.tmp"
            temporary.write_bytes(payload)
            temporary.replace(destination)
        captured_at = datetime.now(timezone.utc).isoformat()
        return StoredArtifact(
            path=destination.resolve(),
            sha256=digest,
            width=width,
            height=height,
            byte_size=len(payload),
            captured_at=captured_at,
        )


__all__ = [
    "MAX_DIMENSION",
    "MAX_PNG_BYTES",
    "RosterArtifactStore",
    "StoredArtifact",
    "validate_png_bytes",
]
