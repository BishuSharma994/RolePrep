#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/roleprep/repo}"
SERVICE_NAME="${SERVICE_NAME:-roleprep-backend}"
VENV_PATH="${VENV_PATH:-/opt/roleprep/venv}"
BRANCH="${BRANCH:-main}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8000/healthz}"

cd "$APP_ROOT"

git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

if [ ! -d "$VENV_PATH" ]; then
  python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m compileall backend

systemctl daemon-reload
systemctl restart "$SERVICE_NAME"
systemctl --no-pager --full status "$SERVICE_NAME"

curl --fail "$HEALTHCHECK_URL"
