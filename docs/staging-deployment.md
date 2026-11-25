# CivicFix AI staging deployment

Release candidate on 25 November 2026. Use synthetic reports and separate staging credentials and data.

## Release checklist

| Check | Observed result |
| --- | --- |
| Phase 8 gate | **Passed locally.** Chrome resolved `CF-2026-ACB1D2`. A new comparison of the original and restored databases matched the reference, `RESOLVED` status, 6 public history entries, 8 audit entries, and feedback. The Phase 8 browser used mocked external providers. |
| Render account and private source repository | **Pending.** `render login` reached the device authorization screen and timed out waiting for approval. The local checkout has no private Git remote. |
| Local staging-schema rehearsal | **Passed.** `alembic upgrade head`, `alembic current`, and `alembic check` ran on the empty `civicfix_ai_test_phase8_staging` database. The revision was `0006_publication (head)` with no schema drift. The synthetic account bootstrap ran successfully twice. |
| Local HTTP and HTTPS rehearsal | **Passed.** FastAPI liveness and database readiness returned 200, the application read 10 categories from PostgreSQL, and the CORS preflight rejected an unapproved origin. In Chrome, `/map` loaded directly and on refresh. A fresh citizen registered, signed in, and rotated the Secure, HttpOnly, SameSite=Strict cookie on reload. |
| Local application checks | **Passed.** `python -m pytest -q` passed 35 tests. `npm.cmd test` passed 7 tests. `npm.cmd run typecheck`, `npm.cmd run lint`, and `npm.cmd run build` passed. The Vite build reported a warning for the 925 kB lazy-loaded 3D chunk. |
| Backend packaging | **Passed.** `python -m pip wheel . --no-deps` built the backend wheel from `backend/pyproject.toml`. |
| Vercel staging project | **Configured.** `jeevan-gk-12/civicfix-ai-staging` exists and is linked to `frontend`. The project uses Vite, Node 24.x, `npm ci`, `npm run build`, and `dist`. |
| Vercel routing and local Vercel CLI build | **Routing configuration passed in Node.** The local `vercel build --prod --yes` failed on Windows first with `EPERM` unlinking the Rolldown binary held by a preview process, then with `EPERM` creating symlinks in the Vercel builder cache from an isolated copy. `npm install --no-audit --no-fund` restored the workspace dependencies and preserved the lockfile. Verify the hosted compiler in the Vercel deployment logs. |
| Managed staging PostgreSQL and migration | **Pending.** Expected revision is `0006_publication (head)`. |
| Deployed Render health and readiness URLs | **Pending.** Record `https://<render-host>/api/v1/health` and `https://<render-host>/api/v1/ready` after each returns HTTP 200. |
| Deployed Vercel URL and direct `/map` refresh | **Pending.** Record the stable domain shown in the staging project’s Domains tab and verify both navigations in a fresh browser. |
| Hosted registration, login, refresh, and complaint workflow | **Pending.** |
| Live Gemini analysis, Cloudinary upload, public map and tiles | **Pending.** |

## 1. Connect the source and provision Render resources

1. Authorize the Render CLI in the browser and select the staging workspace if prompted. In [Render Account Settings](https://dashboard.render.com/u/settings), under **Account Security → Git Deployment Credentials → Add credential**, connect the Git provider. Grant repository access to the private CivicFix AI repository. [Render Git provider instructions](https://render.com/docs/git-provider#setup)
2. In Render, choose **New → Postgres**. Use a distinct name and database name such as `civicfix-ai-staging-db` and `civicfix_ai_staging`. Select the same region for the web service. Review the plan before creating it. Paid Render PostgreSQL provides point-in-time recovery and on-demand logical exports. Free PostgreSQL expires after 30 days and provides no managed backups. [Render Postgres setup](https://render.com/docs/postgresql-creating-connecting) · [Free PostgreSQL limits](https://render.com/docs/free#free-postgres)
3. Choose **New → Web Service → Git Provider**, select the staging source branch, and enter the following values. Use manual deploys while setting up the staging release. [Render FastAPI guide](https://render.com/docs/deploy-fastapi)

| Render setting | Value from the repository |
| --- | --- |
| Root Directory | `backend` |
| Language | Python. `backend/.python-version` selects 3.11. |
| Build Command | `python -m pip install .` |
| Pre-Deploy Command | `python -m alembic upgrade head && python -m alembic current && python -m alembic check` |
| Start Command | `python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/api/v1/ready` |

Render’s pre-deploy command is available on paid web services. For a free smoke environment, run the same three Alembic commands as a separate release step from a machine authorized to connect to the staging database, then deploy. From `backend`, Alembic uses `alembic.ini`, `alembic/env.py`, and the versions in `alembic/versions`. Confirm the release log reports `0006_publication (head)`. [Render pre-deploy command](https://render.com/docs/deploys#pre-deploy-command)

### Render environment

Enter values in **Environment** for the staging web service. Use the same values for the migration step.

| Key | Value |
| --- | --- |
| `APP_ENV` | `staging` |
| `DATABASE_URL` | The staging PostgreSQL Internal Database URL from Render’s **Connect** panel. The backend normalizes Render’s plain PostgreSQL scheme to the psycopg driver. |
| `SECRET_KEY` | A unique random signing secret of at least 32 bytes. |
| `CORS_ORIGINS` | The exact stable Vercel staging origin, including `https://`, with no path or trailing slash. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | A staging Gemini key and a model available to that key that supports structured JSON. |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Credentials for the staging Cloudinary product environment. |

`PORT` comes from Render. The API prefix defaults to `/api/v1`. After deploy, run these checks with the public origin shown in Render.

```powershell
$renderOrigin = 'https://<actual-render-host>'
curl.exe --fail --silent --show-error "$renderOrigin/api/v1/health"
curl.exe --fail --silent --show-error "$renderOrigin/api/v1/ready"
curl.exe --fail --silent --show-error "$renderOrigin/api/v1/public/categories"
```

Liveness should return `{"status":"ok"}`. Readiness should return `{"status":"ready"}` after a live PostgreSQL query. The categories response should contain migrated application records.

## 2. Set up and deploy the Vercel frontend

Open the [CivicFix AI staging project](https://vercel.com/jeevan-gk-12/civicfix-ai-staging). Under **Settings → Environment Variables**, set these values for the stable deployment target of this staging-only project.

| Key | Value |
| --- | --- |
| `RENDER_API_ORIGIN` | The deployed Render HTTPS origin with no path or trailing slash. |
| `VITE_API_BASE_URL` | The stable Vercel staging HTTPS origin followed by `/api/v1`. For initial domain assignment, `/api/v1` resolves to the deployed origin in the browser. |
| `VITE_MAP_TILE_URL` | The approved OpenStreetMap-compatible staging tile URL, if configured. The map also offers a public list. |

`frontend/vercel.mjs` forwards `/api/v1/*` to Render and serves the SPA entry point for deep links such as `/map`. Keeping API requests on the Vercel origin preserves the Secure, HttpOnly, SameSite=Strict refresh cookie. Match the exact stable origin in Render’s CORS allowlist before browser verification. Provider secrets belong in Render’s environment settings. Vite exposes `VITE_` values to the browser. [Vercel rewrites](https://vercel.com/docs/routing/rewrites) · [Vercel Vite SPA routing](https://vercel.com/docs/frameworks/frontend/vite#using-vite-to-make-spas)

For a Git import, set **Root Directory** to `frontend`. For the linked CLI project, run the following from `frontend`. The CLI uploads this directory as the project root. Its production target is the stable alias of the separate staging project.

```powershell
vercel.cmd link --yes --project civicfix-ai-staging --scope jeevan-gk-12
vercel.cmd deploy --prod --yes --scope jeevan-gk-12
```

If Vercel has yet to assign a stable domain, use `/api/v1` for the first build. Confirm the assigned alias in **Settings → Domains**. Set Render’s exact `CORS_ORIGINS` for that alias and redeploy the backend environment settings before testing authentication. [Vercel domain settings](https://vercel.com/docs/domains/working-with-domains) · [Vercel build environment variables](https://vercel.com/docs/environment-variables/managing-environment-variables)

## 3. Seed and verify the hosted workflow

Run this in the Render service shell, or from `backend` with a controlled connection to the migrated staging database. Use the prompted passwords for the synthetic staging accounts. The command creates the organization, water department, and service boundary and assigns the reviewer the matching scope.

```sh
python -m app.bootstrap_staging --admin-email civicfix-stage-admin@example.com --staff-email civicfix-stage-staff@example.com
```

1. In a fresh browser profile, open `/map` directly and reload. Record the HTTP result and verify the public map page displays.
2. Register a unique synthetic citizen, sign out, sign in, and reload the citizen dashboard. In browser developer tools, confirm `POST /api/v1/auth/refresh` returns 200 and the session remains signed in.
3. Report a synthetic water leak at latitude `12.345678`, longitude `76.543210`. Include a generated JPEG or PNG with no personal data. Save the tracking reference and verify the report shows **Photo attached privately**. The upload request should return HTTP 201.
4. Sign in as the staging reviewer. Open the report in the scoped queue and inspect Gemini’s recommendations. Verify the analysis reaches `SUCCEEDED`. Review, assign, start work, post a public update, and resolve the report. Verify the report actor and timestamps in the admin audit.
5. As the citizen, open the resolution notification and confirm it links to the same report and shows the dated public progress. Sign out and inspect `/api/v1/public/complaints/map`. A private report should be absent. If verifying an approved marker, approve a separate synthetic report as `APPROXIMATE` via the staff visibility endpoint and compare its public summary, status, dates, and approximate coordinates against its private detail.

Use Render’s **Events** and **Logs** and Vercel’s **Deployments** view to record deploy outcomes. If a release fails, select the prior working application deploy in the provider dashboard and check its compatibility with the current Alembic revision. Keep staging backup and restore evidence separate from the Phase 8 local restore.
