#!/usr/bin/env bash
set -euo pipefail
export MDR_INVOCATION_PWD="$PWD"
exec ~/dev/mdr/.venv/bin/python ~/dev/mdr/main.py "$@"
