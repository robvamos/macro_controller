"""Adapter over the shared Knowledge SourceRegistry ranking service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


class SharedSourceRegistry(Protocol):
    def find(
        self,
        query: str,
        *,
        category: str | None = None,
        usage_mode: str | None = None,
        domain: str | None = None,
        limit: int = 10,
    ) -> list[object]: ...


@dataclass(frozen=True, slots=True)
class RankedSourceHint:
    source_id: str
    label: str
    category: str
    trust_score: float
    signal_score: float
    noise_score: float
    access_mode: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


class KnowledgeSourceSelector:
    """Delegate ranking to Knowledge and expose a stable local read model."""

    def __init__(self, registry: SharedSourceRegistry) -> None:
        self.registry = registry

    def rank(
        self,
        query: str,
        *,
        usage_mode: str | None = None,
        category: str | None = None,
        domain: str = "doomsday_last_survivors",
        limit: int = 10,
    ) -> tuple[RankedSourceHint, ...]:
        entries = self.registry.find(
            query,
            category=category,
            usage_mode=usage_mode,
            domain=domain,
            limit=limit,
        )
        return tuple(
            RankedSourceHint(
                source_id=str(getattr(entry, "source_id")),
                label=str(getattr(entry, "label")),
                category=str(getattr(entry, "category")),
                trust_score=float(getattr(entry, "trust_score")),
                signal_score=float(getattr(entry, "signal_score")),
                noise_score=float(getattr(entry, "noise_score")),
                access_mode=str(getattr(entry, "access_mode", "unknown")),
                metadata=dict(getattr(entry, "metadata", {}) or {}),
            )
            for entry in entries
        )


__all__ = ["KnowledgeSourceSelector", "RankedSourceHint", "SharedSourceRegistry"]
