# doomsday-vision-primitives

## Purpose

Provide reusable external-automation primitives for Doomsday window capture and UI template matching without injecting code into the game process.

## Entry points

- [doomsday/vision/window_capture.py](/F:/_CODEX/DDassistant/doomsday/vision/window_capture.py)
- [doomsday/vision/template_matcher.py](/F:/_CODEX/DDassistant/doomsday/vision/template_matcher.py)

## Capabilities

- capture the game window as an image
- capture and compare local click-context snapshots during macro playback
- load legacy JSON-described templates
- find the best on-screen match above a threshold
- load graphic elements from the internal catalog and search them across the full game window with scale tolerance for recovery flows

## Notes

- This layer is intended to support external automation, OCR pre-processing, and modal detection.
- It is a low-level primitive layer and does not yet include a complete flow controller.
