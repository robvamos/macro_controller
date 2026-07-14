# Project Agent Instructions

This project is part of the shared AI workspace and now lives at
`F:\_CODEX\DDassistant`.

Default shared skills:

- use `attivasviluppo` when the work concerns project setup, GitHub connection, or persistent assets
- use `sviluppo-conoscenza` for workspace-aware development and knowledge coordination

Shared knowledge root:

- [codex-knowledge-hub](/F:/_CODEX/Knowledge/codex-knowledge-hub)

Before implementing new features:

1. read shared registries in the knowledge hub
2. check reusable skills and exposed interfaces from sibling projects
3. avoid duplicating logic that is already published elsewhere
4. update [project-manifest.json](/F:/_CODEX/DDassistant/project-manifest.json) when version, capabilities, interfaces, or status change
5. sync the manifest back to the knowledge hub after meaningful project changes

Project-specific reusable areas:

- macro playback, recording, focus monitoring, and scheduled execution
- Doomsday roster bootstrap from bundled local datasets
- Doomsday OCR parsers for hero stats and talents
- Doomsday window capture and template matching primitives

Useful shared resources:

- [projects-index.yaml](/F:/_CODEX/Knowledge/codex-knowledge-hub/registry/projects-index.yaml)
- [skills-index.yaml](/F:/_CODEX/Knowledge/codex-knowledge-hub/registry/skills-index.yaml)
- [interfaces-index.yaml](/F:/_CODEX/Knowledge/codex-knowledge-hub/registry/interfaces-index.yaml)
- [capabilities-index.yaml](/F:/_CODEX/Knowledge/codex-knowledge-hub/registry/capabilities-index.yaml)

Local interface notes:

- [doomsday-roster-bootstrap](/F:/_CODEX/DDassistant/interfaces/doomsday-roster-bootstrap.md)
- [doomsday-vision-primitives](/F:/_CODEX/DDassistant/interfaces/doomsday-vision-primitives.md)
