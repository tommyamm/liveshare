#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtual environment not found: $VENV_DIR"
  echo "Create it first with: python3 -m venv venv"
  exit 1
fi

cd "$ROOT_DIR"
source "$VENV_DIR/bin/activate"

if ! python -c "import websockets" >/dev/null 2>&1; then
  echo "Installing Python dependencies..."
  python -m pip install -r requirements.txt
fi

exec python start_teacher.py
