# doomsday-crawler

## Purpose

Describe the emerging Doomsday crawler service for heroes and roster knowledge, centered on:

- discovering which heroes are available on a live account or runtime session
- enriching hero records through an extensible provider list
- preserving provider provenance so later consumers can inspect where each enrichment came from

## Current local building blocks

- [doomsday/services/bootstrap_service.py](/F:/_CODEX/DDassistant/doomsday/services/bootstrap_service.py)
- [doomsday/repositories/roster_repository.py](/F:/_CODEX/DDassistant/doomsday/repositories/roster_repository.py)
- [doomsday/repositories/catalog_repository.py](/F:/_CODEX/DDassistant/doomsday/repositories/catalog_repository.py)
- [doomsday/ocr/hero_extractor.py](/F:/_CODEX/DDassistant/doomsday/ocr/hero_extractor.py)

## Intended service shape

The target service is not only an offline roster bootstrap.

It should evolve toward a provider-aware runtime that can:

- crawl or reconstruct the currently available hero roster from game-derived signals
- normalize hero identity against local catalog records
- enrich hero records through a pluggable provider list
- store source-level provenance for each enrichment step
- let future consumers choose or rank providers instead of hardwiring one source

## Intended provider families

- local bundled catalog datasets
- OCR-derived hero extraction
- future game-specific crawler profiles
- future external knowledge providers or curated registries

## Why this matters to sibling projects

This crawler service is a natural integration point for `Knowledge`, because `Knowledge` already exposes:

- provider-driven runtime patterns
- source registry concepts
- crawler profile concepts
- external source brokering

## Draft integration ask

`Knowledge` is asked to support and help integrate this service by contributing:

- provider list modeling
- provenance and source ranking conventions
- crawler-profile compatibility
- a reusable enrichment orchestration pattern

## Status

Draft interface.
The direction is already visible in this project's roster bootstrap, OCR, and catalog modules, but the crawler runtime itself is not yet fully formalized as a standalone module.
