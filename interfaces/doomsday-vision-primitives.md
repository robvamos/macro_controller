# doomsday-vision-primitives

## Purpose

Provide reusable external-automation primitives for Doomsday window capture and UI template matching without injecting code into the game process.

## Entry points

- [doomsday/vision/window_capture.py](../doomsday/vision/window_capture.py)
- [doomsday/vision/template_matcher.py](../doomsday/vision/template_matcher.py)
- [doomsday/vision/ui_graph.py](../doomsday/vision/ui_graph.py)

## Capabilities

- capture the game window as an image
- capture and compare local click-context snapshots during macro playback
- load registered semantic alternatives, such as the troop healing symbol, as additional visual references for matching macro context when the macro contains that element
- load legacy JSON-described templates
- find the best on-screen match above a threshold
- load graphic elements from the internal catalog and search them across the full game window with scale tolerance for recovery flows
- search one or more catalogued graphic elements across the whole game window and return a reusable result with `found`, `center`, `score`, `matched_element_name`, `condition_satisfied`, and window metadata
- model game views, panels, and blocking popups as graph nodes with reusable recognition conditions, recovery actions, and transitions between states
- enrich a growing knowledge layer that reconstructs how views, panels, overlays, and blocking popups relate to each other over time, including parent/child structure, seen frequency, confidence, and recovery paths
- link graph nodes and high-level intents to candidate macros so future orchestration can choose, combine, or generate the right macro flow for a requested in-game objective
- ingest pasted or loaded game elements in a lossless, non-distorted way with semantic hints suitable for UI graphs, matching, and recovery
- keep color or local variants of the same graphic element searchable as one semantic target by also checking suffixed catalog entries such as `element_name_2`
- recover from blocking popups by trying reusable semantic strategies such as a classic close symbol, a repeated back-return symbol in alto a sinistra, a crossed-circle popup symbol, or a learned empty-space dismiss band

Default matching guidance:
- for in-game graphic element search, matches above `0.85` are considered acceptable unless a caller overrides the threshold

## Notes

- This layer is intended to support external automation, OCR pre-processing, and modal detection.
- It is a low-level primitive layer and does not yet include a complete flow controller.
