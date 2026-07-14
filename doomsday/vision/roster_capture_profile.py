"""Versioned, client-relative capture regions for the Doomsday roster workflow."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE_PATH = (
    PROJECT_ROOT
    / "data"
    / "doomsday"
    / "vision"
    / "roster_capture_profiles"
    / "windows-1.58.0-3440x1440.json"
)


@dataclass(frozen=True, slots=True)
class NormalizedRegion:
    region_id: str
    left: float
    top: float
    right: float
    bottom: float
    status: str
    purpose: str

    def to_pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        if self.status != "calibrated":
            raise ValueError(f"Region {self.region_id} is not calibrated")
        return (
            round(self.left * width),
            round(self.top * height),
            round(self.right * width),
            round(self.bottom * height),
        )


@dataclass(frozen=True, slots=True)
class RosterCaptureProfile:
    profile_id: str
    game_version: str
    reference_width: int
    reference_height: int
    locale: str
    source_sha256: str
    regions: dict[str, NormalizedRegion]
    stage_status: dict[str, str]

    def region_pixels(self, region_id: str, *, client_size: tuple[int, int]) -> tuple[int, int, int, int]:
        width, height = client_size
        if width <= 0 or height <= 0:
            raise ValueError("Client size must be positive")
        reference_aspect = self.reference_width / self.reference_height
        actual_aspect = width / height
        if abs(reference_aspect - actual_aspect) / reference_aspect > 0.02:
            raise ValueError("Client aspect ratio is incompatible with capture profile")
        try:
            region = self.regions[region_id]
        except KeyError as exc:
            raise KeyError(f"Unknown capture region: {region_id}") from exc
        return region.to_pixels(width, height)


def load_roster_capture_profile(path: str | Path = DEFAULT_PROFILE_PATH) -> RosterCaptureProfile:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "doomsday.roster_capture_profile.v1":
        raise ValueError("Unsupported roster capture profile schema")
    client = payload["reference_client"]
    regions = {}
    for item in payload.get("regions", []):
        bounds = item.get("normalized_ltrb")
        if not isinstance(bounds, list) or len(bounds) != 4:
            raise ValueError(f"Invalid normalized bounds for {item.get('region_id')}")
        left, top, right, bottom = (float(value) for value in bounds)
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            raise ValueError(f"Out-of-bounds normalized region: {item.get('region_id')}")
        region = NormalizedRegion(
            region_id=item["region_id"],
            left=left,
            top=top,
            right=right,
            bottom=bottom,
            status=item["status"],
            purpose=item.get("purpose", ""),
        )
        regions[region.region_id] = region
    return RosterCaptureProfile(
        profile_id=payload["profile_id"],
        game_version=payload["game_version"],
        reference_width=int(client["width"]),
        reference_height=int(client["height"]),
        locale=payload["locale"],
        source_sha256=payload["source"]["sha256"],
        regions=regions,
        stage_status={item["stage"]: item["status"] for item in payload.get("stages", [])},
    )


__all__ = [
    "DEFAULT_PROFILE_PATH",
    "NormalizedRegion",
    "RosterCaptureProfile",
    "load_roster_capture_profile",
]
