# RolePrep Backend Deployment

## Production Layout

Use a stable runtime layout on the VPS:

```text
/opt/roleprep/
  repo/
  shared/.env
  venv/
```

## One-Time Server Setup

1. Clone the repository to `/opt/roleprep/repo`
2. Create a virtual environment at `/opt/roleprep/venv`
3. Put production environment variables in `/opt/roleprep/shared/.env`
4. Install the systemd service from `deploy/roleprep-backend.service.example`

## Deploy Command

`deploy.sh` is the only command the server needs to run:

```bash
cd /opt/roleprep/repo
bash deploy.sh
```

It will:

1. Pull the latest `main`
2. Install dependencies into `/opt/roleprep/venv`
3. Compile backend modules
4. Restart `roleprep-backend`
5. Run a health check

## GitHub Actions Secrets

Create these repository secrets:

- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_KEY`
- `VPS_APP_ROOT`
- `VPS_VENV_PATH`
- `VPS_SERVICE_NAME`

Suggested values:

- `VPS_APP_ROOT=/opt/roleprep/repo`
- `VPS_VENV_PATH=/opt/roleprep/venv`
- `VPS_SERVICE_NAME=roleprep-backend`

## Recommended Workflow

1. Make changes locally
2. Push to `main`
3. GitHub Actions deploys automatically
4. Never edit production code directly on the VPS
