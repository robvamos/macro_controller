# doomsday-vision-primitives

## Purpose

Provide reusable external-automation primitives for Doomsday window capture and UI template matching without injecting code into the game process.

## Entry points

- [doomsday/vision/window_capture.py](/F:/_CODEX/AI-WORKSPACE/DDGameAss/doomsday/vision/window_capture.py)
- [doomsday/vision/template_matcher.py](/F:/_CODEX/AI-WORKSPACE/DDGameAss/doomsday/vision/template_matcher.py)

## Capabilities

- capture the game window as an image
- load legacy JSON-described templates
- find the best on-screen match above a threshold

## Notes

- This layer is intended to support external automation, OCR pre-processing, and modal detection.
- It is a low-level primitive layer and does not yet include a complete flow controller.
