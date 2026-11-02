#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec env -u PYTHONPATH /usr/bin/python3 "$ROOT/scripts/run-tests.py"
