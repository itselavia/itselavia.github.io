# Operational Runbook & Deployment Observability

This runbook covers deployment verification, monitoring dashboards, and incident response for `itselavia.github.io`.

## Observability & Dashboards

- **GitHub Actions Deployment Pipeline:** [https://github.com/itselavia/itselavia.github.io/actions/workflows/deploy.yml](https://github.com/itselavia/itselavia.github.io/actions/workflows/deploy.yml)
- **GitHub Pages Environment Status:** [https://github.com/itselavia/itselavia.github.io/deployments](https://github.com/itselavia/itselavia.github.io/deployments)
- **SonarQube Cloud Quality Gate Dashboard:** [https://sonarcloud.io/dashboard?id=itselavia_itselavia.github.io](https://sonarcloud.io/dashboard?id=itselavia_itselavia.github.io)
- **Live Site Health Endpoint:** `https://itselavia.github.io/health.json`

## Post-Deploy Verification

After a push to `master` completes the `Deploy to GitHub Pages` workflow:

```bash
# Verify health endpoint returns HTTP 200 and status "ok"
curl -fsSL https://itselavia.github.io/health.json

# Verify latest workflow run succeeded
gh run list --workflow=deploy.yml --limit 5
```

## Incident Playbooks

### 1. CI Validation or Build Failure

1. Inspect the failing job logs:
   ```bash
   gh run view --log-failed
   ```
2. Reproduce locally:
   ```bash
   python3 scripts/validate_site.py --check-format --check-docs
   python3 -m unittest discover -s tests -p "test_*.py" -v
   ```
3. If `docs/post-catalog.md` is out of date after adding/editing a post, run `python3 scripts/validate_site.py --generate-docs`.

### 2. Bad Production Deployment / Rollback

If a broken layout or post reaches `master`:

1. Revert the offending commit and push to `master` to trigger an automated redeploy:
   ```bash
   git revert HEAD --no-edit
   git push origin master
   ```
2. Alternatively, trigger a manual redeploy of a known-good state via GitHub Actions:
   ```bash
   gh workflow run deploy.yml --ref master
   ```
3. Confirm recovery via `https://itselavia.github.io/health.json`.
