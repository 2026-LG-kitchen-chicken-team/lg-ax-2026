# Linux CI browser regression

`uv run python scripts/ci_web_e2e.py --report REPORT.json` runs the existing two fixture browser cases and the real synthetic API browser case in `apps/web/e2e/planner-flow.spec.ts`. It succeeds only if all three pass with zero skipped, failed, or flaky cases. This is browser/API regression, not a live planning Agent or customer-effect evaluation.

Install Python dependencies with `uv sync --locked --dev`, web dependencies with `npm ci --prefix apps/web`, and official Playwright Chromium with `npx playwright install --with-deps chromium` from `apps/web`. The GitHub web job does this and uploads only its sanitized summary.

The helper selects three separate unused numeric-loopback ports. Its temporary Vite config uses those private APIs; its temporary Playwright config explicitly selects bundled Chromium and the isolated web URL. It does not edit the tracked app configs or reuse/stop existing development services. The owned CI workspace allows only the exact temporary web origin, retains all credential/owner checks, and contains only the synthetic demo dataset.

Ephemeral editor/viewer tokens, the credentials registry (hashed tokens), SQLite DB, configs, process output, raw Playwright report, downloads and browser output stay in a newly created private directory. The helper reaps its own child process groups and removes that directory on success/failure/interruption. Traces, screenshots and videos are disabled because they could record the credential input. No raw console, token, DB, test result directory or private files are CI artifacts. The summary contains only boolean readiness/security/cleanup checks and numeric browser counts.

For a local API-only readiness/auth/origin/cleanup check, use:

```text
uv run python scripts/ci_web_e2e.py --probe
uv run python -m unittest discover -s tests -p test_ci_web_e2e.py -v
```

`--probe` does not start Vite, Playwright or a browser. Full browser execution by this helper is limited to Linux CI. Existing local browser verification uses the project's approved computer-use path. The three browser case definitions must not be silently dropped or skipped; if their intended count changes, update the explicit helper gate and review that change with PM.

The cleanup summary's `isolated_ports_released` means that the helper's TCP listeners no longer accept connections. An explicit loopback connection refusal is required; timeout and other connection errors fail closed. OS TCP `TIME_WAIT` after a graceful shutdown is not a live service and does not fail this check. The independent child-process reap check remains required; no process is killed merely to make a port check pass.
