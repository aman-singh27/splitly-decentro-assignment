# Hosting the complete app

The assignment demo uses one free Render Docker web service in Singapore. The image builds React, then runs Django migrations, collects local Swagger assets and starts Waitress on Render's assigned port. The website and API share one HTTPS origin; a separate Vercel frontend is unnecessary for this deployment.

App: [Splitly](https://splitly-decentro.onrender.com). API explorer: [Swagger](https://splitly-decentro.onrender.com/api/docs/).

**Temporary storage:** this is the free demonstration chosen by the owner. Render can idle the service after 15 minutes without traffic. A first request after idling can take about one minute. Local SQLite data, sessions and uploaded bill photographs are lost on idle/restart/redeployment. Old group links may stop working after a reset. Create a fresh group to evaluate the app. Do not use this demonstration as durable financial storage.

## Configuration

`render.yaml` records the deployment recipe and validates against Render's official Blueprint JSON schema. The live service can also be created directly from the GitHub repository with runtime Docker, plan Free, branch main and region Singapore. Its environment contains:

- `DJANGO_DEBUG=false` and a generated private `DJANGO_SECRET_KEY`.
- `DJANGO_HTTPS=true` and `DJANGO_SECURE_COOKIES=true`.
- `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`; Render's provided external hostname is added by the application.
- `SQLITE_PATH=/app/data/db.sqlite3` and `MEDIA_ROOT=/app/data/receipts`.

The production secret belongs in Render's environment, never in Git. Startup migrations run at runtime, so no database is baked into the image. User workspaces start empty; there is no automatic demo seed.

Render terminates TLS before connecting to the container. Django's Render-specific configuration and Waitress's HTTPS URL scheme preserve secure cookies, CSRF origin checks and HTTPS redirects. Local Docker retains HTTP settings. Forwarded headers supplied by arbitrary clients are cleared by Waitress.

Automatic deploys follow commits to main. `/health/ready` checks the migrated ledger database, and `/health/live` checks the running process. The Blueprint specifies readiness as its health check; direct creation uses Render's default health behavior unless changed in the Dashboard.

## Verify a live deployment

Wait for Render to report the deploy as live, then check the app, both health probes, `/api/docs/`, bundled Swagger assets and the exported API artifacts. Run the browser journeys against the actual HTTPS origin:

```powershell
$env:E2E_BASE_URL = 'https://YOUR-SERVICE.onrender.com'
npm run test:e2e --prefix frontend
.\.venv\Scripts\python.exe scripts/verify_artifacts.py --base-url $env:E2E_BASE_URL
```

Setting `E2E_BASE_URL` prevents Playwright from starting local Django/Vite servers. The tests create isolated workspaces, including real expense/photo/settlement records. Remove the variable before running local browser tests again.

For permanent storage, choose a paid service and attach a persistent disk at `/app/data`, or implement PostgreSQL plus object storage with explicit concurrency/storage tests. With SQLite on a disk, run one service instance and test disk write permissions. Paid infrastructure is outside this free demo's configuration.

References: [Render free service limits](https://render.com/docs/free), [default environment variables](https://render.com/docs/environment-variables), [Docker deployment](https://render.com/docs/docker).
