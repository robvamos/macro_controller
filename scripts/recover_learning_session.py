"""Recover an interrupted learning session from element metadata, read-only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.learning_session_recovery_service import recover_learning_session


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_name")
    parser.add_argument("--workflow-id")
    parser.add_argument("--objective")
    parser.add_argument("--database")
    parser.add_argument("--output-root")
    args = parser.parse_args()
    kwargs = {"declared_workflow_id": args.workflow_id, "objective": args.objective}
    if args.database:
        kwargs["db_path"] = args.database
    if args.output_root:
        kwargs["output_root"] = args.output_root
    result = recover_learning_session(args.session_name, **kwargs)
    print(json.dumps({key: result[key] for key in ("path", "session_name", "click_count", "image_count")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
