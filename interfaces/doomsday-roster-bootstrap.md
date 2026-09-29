# doomsday-roster-bootstrap

## Purpose

Prepare and refresh the local Doomsday roster database from the bundled catalog and roster datasets shipped with this project.

## Entry points

- [bootstrap_doomsday_data.py](../bootstrap_doomsday_data.py)
- [doomsday/services/bootstrap_service.py](../doomsday/services/bootstrap_service.py)

## Inputs

- bundled catalog datasets in [data/doomsday/catalog](../data/doomsday/catalog)
- bundled roster datasets in [data/doomsday/roster](../data/doomsday/roster)

## Outputs

- initialized workstation-local SQLite database at `workstation/local/<profile>/runtime/doomsday/doomsday_roster.db`
- imported catalog profiles, roster documents, and roster beasts

## Notes

- This is designed for local offline bootstrap, not live extraction from the game.
- Consumers can reuse the repositories after bootstrap:
  [doomsday/repositories/catalog_repository.py](../doomsday/repositories/catalog_repository.py)
  and
  [doomsday/repositories/roster_repository.py](../doomsday/repositories/roster_repository.py)
