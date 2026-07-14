"""Provider runtime for roster, rules, battle reports and external evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol

from doomsday.intelligence.evidence import ProviderContribution


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    provider_id: str
    provider_type: str
    label: str
    object_types: tuple[str, ...]
    fields: tuple[str, ...] = ()
    access_mode: str = "local"
    requires_human_activation: bool = False
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    provider_id: str
    available: bool
    message: str = ""
    checked_at: str = ""


@dataclass(frozen=True, slots=True)
class ProviderRunError:
    provider_id: str
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class ProviderRunResult:
    contributions: tuple[ProviderContribution, ...]
    errors: tuple[ProviderRunError, ...]
    providers_considered: tuple[str, ...]


class EnrichmentProvider(Protocol):
    """Object-agnostic extension of the shared crawler support contract."""

    def describe_provider(self) -> ProviderDescriptor: ...

    def supports(
        self,
        object_type: str,
        fields: tuple[str, ...],
        context: Mapping[str, Any],
    ) -> bool: ...

    def discover(
        self,
        seed: Mapping[str, Any],
        cursor: str | None = None,
    ) -> Iterable[Any]: ...

    def collect(self, candidate: Any) -> Any: ...

    def normalize(self, artifact: Any) -> Any: ...

    def emit_observations(self, normalized: Any) -> Iterable[ProviderContribution]: ...

    def health(self) -> ProviderHealth: ...


class ProviderOrchestrator:
    """Run independent providers without letting one failure abort the chain."""

    def __init__(self, providers: Iterable[EnrichmentProvider]) -> None:
        self.providers = tuple(providers)

    def list_providers(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(provider.describe_provider() for provider in self.providers)

    def run(
        self,
        *,
        object_type: str,
        fields: Iterable[str] = (),
        seed: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
        provider_filter: Iterable[str] | None = None,
    ) -> ProviderRunResult:
        requested_fields = tuple(str(item) for item in fields)
        runtime_context = dict(context or {})
        allowed = set(provider_filter or ())
        use_filter = provider_filter is not None
        contributions: list[ProviderContribution] = []
        errors: list[ProviderRunError] = []
        considered: list[str] = []

        for provider in self.providers:
            fallback_provider_id = provider.__class__.__name__
            try:
                descriptor = provider.describe_provider()
            except Exception as exc:
                errors.append(ProviderRunError(fallback_provider_id, "describe", str(exc)))
                continue
            if use_filter and descriptor.provider_id not in allowed:
                continue
            try:
                supported = provider.supports(object_type, requested_fields, runtime_context)
            except Exception as exc:
                errors.append(ProviderRunError(descriptor.provider_id, "supports", str(exc)))
                continue
            if not supported:
                continue
            considered.append(descriptor.provider_id)
            try:
                health = provider.health()
            except Exception as exc:
                errors.append(ProviderRunError(descriptor.provider_id, "health", str(exc)))
                continue
            if not health.available:
                errors.append(
                    ProviderRunError(
                        descriptor.provider_id,
                        "health",
                        health.message or "provider unavailable",
                    )
                )
                continue
            try:
                candidates = tuple(provider.discover(seed))
            except Exception as exc:
                errors.append(ProviderRunError(descriptor.provider_id, "discover", str(exc)))
                continue
            for candidate in candidates:
                try:
                    artifact = provider.collect(candidate)
                except Exception as exc:
                    errors.append(ProviderRunError(descriptor.provider_id, "collect", str(exc)))
                    continue
                try:
                    normalized = provider.normalize(artifact)
                except Exception as exc:
                    errors.append(ProviderRunError(descriptor.provider_id, "normalize", str(exc)))
                    continue
                try:
                    emitted = tuple(provider.emit_observations(normalized))
                    if not all(isinstance(item, ProviderContribution) for item in emitted):
                        raise TypeError("emit_observations must return ProviderContribution items")
                    contributions.extend(emitted)
                except Exception as exc:
                    errors.append(ProviderRunError(descriptor.provider_id, "emit", str(exc)))

        return ProviderRunResult(
            contributions=tuple(contributions),
            errors=tuple(errors),
            providers_considered=tuple(considered),
        )


__all__ = [
    "EnrichmentProvider",
    "ProviderDescriptor",
    "ProviderHealth",
    "ProviderOrchestrator",
    "ProviderRunError",
    "ProviderRunResult",
]
