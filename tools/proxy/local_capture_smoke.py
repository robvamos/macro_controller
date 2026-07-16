"""Harmless delayed request used to validate per-PID local capture."""

from __future__ import annotations

import argparse
import time
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--url", default="https://example.com")
    args = parser.parse_args()
    time.sleep(max(0.0, args.delay))
    with urllib.request.urlopen(args.url, timeout=15) as response:
        print(response.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
