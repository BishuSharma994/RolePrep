#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/root/RolePrep}"
SERVICE_NAME="${SERVICE_NAME:-roleprep-backend}"
VENV_PATH="${VENV_PATH:-$APP_ROOT/backend/venv}"

cd "$APP_ROOT"
source "$VENV_PATH/bin/activate"

python -m compileall backend
sudo systemctl restart "$SERVICE_NAME"
sleep 2
curl --fail http://127.0.0.1:8000/healthz
