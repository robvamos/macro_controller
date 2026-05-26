# doomsday-roster-bootstrap

## Purpose

Prepare and refresh the local Doomsday roster database from the bundled catalog and roster datasets shipped with this project.

## Entry points

- [bootstrap_doomsday_data.py](/F:/_CODEX/AI-WORKSPACE/DDGameAss/bootstrap_doomsday_data.py)
- [doomsday/services/bootstrap_service.py](/F:/_CODEX/AI-WORKSPACE/DDGameAss/doomsday/services/bootstrap_service.py)

## Inputs

- bundled catalog datasets in [data/doomsday/catalog](/F:/_CODEX/AI-WORKSPACE/DDGameAss/data/doomsday/catalog)
- bundled roster datasets in [data/doomsday/roster](/F:/_CODEX/AI-WORKSPACE/DDGameAss/data/doomsday/roster)

## Outputs

- initialized local SQLite database at [data/doomsday/doomsday_roster.db](/F:/_CODEX/AI-WORKSPACE/DDGameAss/data/doomsday/doomsday_roster.db)
- imported catalog profiles, roster documents, and roster beasts

## Notes

- This is designed for local offline bootstrap, not live extraction from the game.
- Consumers can reuse the repositories after bootstrap:
  [doomsday/repositories/catalog_repository.py](/F:/_CODEX/AI-WORKSPACE/DDGameAss/doomsday/repositories/catalog_repository.py)
  and
  [doomsday/repositories/roster_repository.py](/F:/_CODEX/AI-WORKSPACE/DDGameAss/doomsday/repositories/roster_repository.py)
