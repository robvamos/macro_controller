# doomsday-vision-primitives

## Purpose

Provide reusable external-automation primitives for Doomsday window capture and UI template matching without injecting code into the game process.

## Entry points

- [doomsday/vision/window_capture.py](/F:/_CODEX/DDassistant/doomsday/vision/window_capture.py)
- [doomsday/vision/template_matcher.py](/F:/_CODEX/DDassistant/doomsday/vision/template_matcher.py)
- [doomsday/vision/ui_graph.py](/F:/_CODEX/DDassistant/doomsday/vision/ui_graph.py)

## Capabilities

- capture the game window as an image
- capture and compare local click-context snapshots during macro playback
- load legacy JSON-described templates
- find the best on-screen match above a threshold
- load graphic elements from the internal catalog and search them across the full game window with scale tolerance for recovery flows
- search one or more catalogued graphic elements across the whole game window and return a reusable result with `found`, `center`, `score`, `matched_element_name`, `condition_satisfied`, and window metadata
- model game views, panels, and blocking popups as graph nodes with reusable recognition conditions, recovery actions, and transitions between states
- enrich a growing knowledge layer that reconstructs how views, panels, overlays, and blocking popups relate to each other over time, including parent/child structure, seen frequency, confidence, and recovery paths
- link graph nodes and high-level intents to candidate macros so future orchestration can choose, combine, or generate the right macro flow for a requested in-game objective
- ingest pasted or loaded game elements in a lossless, non-distorted way with semantic hints suitable for UI graphs, matching, and recovery

Default matching guidance:
- for in-game graphic element search, matches above `0.85` are considered acceptable unless a caller overrides the threshold

## Notes

- This layer is intended to support external automation, OCR pre-processing, and modal detection.
- It is a low-level primitive layer and does not yet include a complete flow controller.
