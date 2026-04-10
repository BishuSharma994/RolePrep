# RolePrep Production Backend Runbook

## Production Runtime

RolePrep backend runs from these stable VPS paths:

```text
/opt/roleprep/repo
/opt/roleprep/venv
/opt/roleprep/shared/.env
```

Systemd service:

```text
roleprep-backend
```

The backend should not be edited directly on the VPS. Local development and GitHub are the source of truth.

## Deployment Flow

Backend deploys are automated through GitHub Actions.

Daily workflow:

1. Make backend changes locally
2. Test locally
3. Push to `main`
4. GitHub Actions runs `Deploy Backend`
5. The VPS pulls latest code and restarts the backend

## GitHub Actions Secrets

Repository secrets required:

- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_KEY_B64`
- `VPS_APP_ROOT`
- `VPS_VENV_PATH`
- `VPS_SERVICE_NAME`

Expected values:

- `VPS_APP_ROOT=/opt/roleprep/repo`
- `VPS_VENV_PATH=/opt/roleprep/venv`
- `VPS_SERVICE_NAME=roleprep-backend`

## Server Deploy Script

The VPS uses:

```bash
cd /opt/roleprep/repo
bash deploy.sh
```

`deploy.sh` will:

1. Pull latest `main`
2. Ensure the virtualenv exists
3. Install/update dependencies
4. Compile backend modules
5. Restart `roleprep-backend`
6. Retry health checks until backend is ready

## Production Verification

Backend health:

```bash
curl http://127.0.0.1:8000/healthz
```

Expected:

```json
{"status":"ok"}
```

Deployment verification marker:

```bash
curl http://127.0.0.1:8000/buildz
```

Expected:

```json
{"status":"ok","deployment":"github-actions"}
```

## Logs

Check backend logs with:

```bash
journalctl -u roleprep-backend -n 100 --no-pager
```

Check service status:

```bash
systemctl status roleprep-backend --no-pager
```

## Rollback

Preferred rollback:

```bash
git revert <bad_commit_sha>
git push origin main
```

This keeps Git history clean and lets GitHub Actions redeploy automatically.

Emergency temporary rollback on VPS:

```bash
cd /opt/roleprep/repo
git checkout <last_good_commit>
systemctl restart roleprep-backend
```

Important:

- this is temporary only
- the next normal deploy will reset the repo back to `main`
- after emergency rollback, do a proper `git revert` and push

## Rules

- Do not use VS Code SFTP for backend deploys
- Do not edit live backend code directly on VPS
- Do not use `/root/RolePrep` as runtime path
- Keep secrets in:
  - VPS `.env`
  - GitHub repository secrets

## Legacy Note

Old backend path `/root/RolePrep` has been removed from runtime use.

Legacy backup is stored at:

```text
/root/RolePrep_legacy_backup
```
