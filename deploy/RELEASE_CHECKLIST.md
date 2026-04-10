# RolePrep Release Checklist

## Standard Release Order

Use this order when backend and frontend changes are related:

1. Finish backend changes locally
2. Run backend tests locally
3. Push backend to `main`
4. Confirm GitHub Actions backend deploy passed
5. Verify backend production health
6. Deploy frontend changes
7. Verify full live flow in browser

If frontend depends on a new API or backend behavior, backend must go first.

## Backend Release Checklist

Before push:

- confirm code changes are local and committed
- run relevant tests
- confirm `.env` changes are not accidentally committed
- confirm no local-only debug code is left behind

Push:

```bash
git push origin main
```

After push:

- open GitHub `Actions`
- confirm `Deploy Backend` passed

Production checks:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/buildz
```

Expected:

```json
{"status":"ok"}
{"status":"ok","deployment":"github-actions"}
```

If release affects auth, payments, resume, or sessions, also verify the relevant live endpoint flow.

## Frontend Release Checklist

Before deploy:

- confirm frontend points to the correct production backend URL
- confirm API contract matches backend changes
- confirm auth and payment flows are aligned with backend behavior

After deploy:

- open live site
- test on desktop
- test on mobile if UI or auth flow changed

## Full-Flow Checks

Use the relevant checks for the feature being released:

- OTP send
- OTP verify
- device sync
- session refresh after audio submit
- payment link flow
- payment return flow
- resume paid gating
- resume generate for paid users
- free-user blocking where expected

## Rollback Rule

If a release is bad:

```bash
git revert <bad_commit_sha>
git push origin main
```

Then confirm:

- GitHub Actions deploy passed
- production health is back to normal

## Rules

- do not use SFTP for backend deployment
- do not edit backend code directly on VPS
- use GitHub as the source of truth
- backend deploy first when frontend depends on backend changes
