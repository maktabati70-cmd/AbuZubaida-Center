#!/usr/bin/env bash
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then echo "Python 3 is not installed: https://www.python.org/downloads/"; exit 1; fi
"$PY" start.py
