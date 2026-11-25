# CivicFix AI

The React, Vite, and TypeScript frontend opens with the CivicFix AI public homepage. FastAPI exposes a health endpoint, and local PostgreSQL has a separate command-line check.

## Windows PowerShell setup

Install Git, Node.js 24, Python 3.11, and PostgreSQL 18 with its command-line tools. Run the blocks below in Windows PowerShell. Use the path to your checkout if it differs from the workspace path shown.

### From the project root

```powershell
Set-Location 'C:\Users\Jeevan G K\OneDrive\My folder\CivicFix AI'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-postgres.ps1
```

The script starts a dedicated PostgreSQL instance on `127.0.0.1:55432`, creates `civicfix_ai` with the `civicfix_app` login, and creates `backend/.env` if needed. It uses `%LOCALAPPDATA%\CivicFixAI\PostgreSQL` for the data, log, and generated passwords. Run the same command after a restart to bring the database back up. If PostgreSQL is installed elsewhere, pass `-PostgresBin 'C:\path\to\PostgreSQL\bin'` after the script path.

### From the backend folder

```powershell
Set-Location 'C:\Users\Jeevan G K\OneDrive\My folder\CivicFix AI\backend'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
```

### From the frontend folder

```powershell
Set-Location 'C:\Users\Jeevan G K\OneDrive\My folder\CivicFix AI\frontend'
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
npm.cmd ci
```

The examples in `backend/.env.example` and `frontend/.env.example` document the settings. The backend uses `DATABASE_URL` and accepts a comma-separated `CORS_ORIGINS` allowlist. Open the frontend using `localhost` to match that allowlist. Git ignores real `.env` files. Vite exposes all `VITE_` settings to the browser, so use them for public values only.

## Start the apps

Leave each command running in its own PowerShell window.

**Backend window**

```powershell
Set-Location 'C:\Users\Jeevan G K\OneDrive\My folder\CivicFix AI\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

**Frontend window**

```powershell
Set-Location 'C:\Users\Jeevan G K\OneDrive\My folder\CivicFix AI\frontend'
npm.cmd run dev
```

| Open in the browser | Expected result |
| --- | --- |
| [Frontend](http://localhost:5173/) | CivicFix AI homepage with How It Works and an illustrative city |
| [Backend health](http://localhost:8000/api/v1/health) | HTTP 200 with `{"status":"ok"}` |
| [FastAPI docs](http://localhost:8000/docs) | Development API documentation |

## Verify Phase 1

**From any folder**, with the backend running, check the live health endpoint.

```powershell
curl.exe --noproxy "*" --include --fail --silent --show-error http://localhost:8000/api/v1/health
```

**From `backend`**, run the health test and independently execute `SELECT 1` through the configured SQLAlchemy connection. The second command prints `1`.

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m app.db.check
```

**From `frontend`**, run the TypeScript check, ESLint, and production build.

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

### Local verification on 25 November 2026

| Check | Observed result |
| --- | --- |
| Chrome headless at `http://localhost:5173/` | Rendered **CivicFix AI** and **API is online** |
| Live `GET /api/v1/health` | HTTP 200 with `{"status":"ok"}` |
| `python -m app.db.check` | Returned `1` from the configured `civicfix_ai` connection |
| `npm.cmd run typecheck` | Exited successfully |
| `npm.cmd run build` | Vite produced `dist/index.html` and bundled assets |
| `python -m pytest` | 1 passed |
| `git check-ignore -v backend/.env frontend/.env` | Both local environment files matched `.gitignore` |

## Stop the apps

Use Ctrl+C in each app window to stop that server. To stop the dedicated PostgreSQL instance, run these commands from any folder.

```powershell
$pgBin = Join-Path $env:ProgramFiles 'PostgreSQL\18\bin'
$pgData = Join-Path $env:LOCALAPPDATA 'CivicFixAI\PostgreSQL\data'
& (Join-Path $pgBin 'pg_ctl.exe') stop -D $pgData -m fast -w
```

## Phase 2 authentication

If you set up Phase 1 previously, rerun `scripts/setup-postgres.ps1` from the project root. It replaces the original `SECRET_KEY` placeholder in `backend/.env` with a random signing key. Keep that key private. Restart Uvicorn after changing the environment.

From `backend`, install the updated dependencies. To enable authentication on the local development database, run the following commands with your development `DATABASE_URL`.

```powershell
$python = '.\.venv\Scripts\python.exe'
& $python -m pip install -e '.[test]'
& $python -m alembic upgrade head
& $python -m app.bootstrap_admin --email 'admin@example.com' --name 'Local Administrator'
```

The last command prompts for a password. Use your own email and password for the administrator. To provision staff, submit `POST /api/v1/admin/staff` with an administrator access token and the account fields `full_name`, `email`, `password`, and `organization_id`. Include at least one ID in each of `department_ids` and `service_area_ids`. The organization and these memberships must exist and be active in the same organization. `staff_title` is optional. Staff can check their effective membership at `GET /api/v1/authority/scope/{organization_id}`.

Citizens register with `POST /api/v1/auth/register`. Login and refresh return a bearer token in `data.access_token` and set the HttpOnly refresh cookie. Keep the access token in memory and send it in the `Authorization: Bearer <token>` header for protected requests. Send `X-CivicFix-CSRF: 1` and include credentials for `/auth/login`, `/auth/refresh`, and `/auth/logout`. Refresh once per session at a time. Reusing a rotated token invalidates that login session. Logout revokes the session associated with the access token and clears the cookie.

The cookie uses `SameSite=Strict` and requires HTTPS in staging and production. Host the frontend and API on the same site for browser cookie access. Login and other sensitive write routes have per-process IP rate limits.

### Verify against the dedicated test database

Create the test database once from any PowerShell folder while the PostgreSQL instance is running.

```powershell
$psql = Join-Path $env:ProgramFiles 'PostgreSQL\18\bin\psql.exe'
$priorPassword = $env:PGPASSWORD
try {
    $passwordFile = Join-Path $env:LOCALAPPDATA 'CivicFixAI\PostgreSQL\admin-password'
    $env:PGPASSWORD = (Get-Content -Raw -LiteralPath $passwordFile).Trim()
    & $psql -X -w -h 127.0.0.1 -p 55432 -U civicfix_local_admin -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE civicfix_ai_test OWNER civicfix_app TEMPLATE template0'
    if ($LASTEXITCODE -ne 0) { throw 'Test database creation failed.' }
} finally {
    $env:PGPASSWORD = $priorPassword
}
```

Run the migrations and tests from `backend`. The database URL override is restored when the block finishes.

```powershell
$python = '.\.venv\Scripts\python.exe'
$priorTestUrl = $env:TEST_DATABASE_URL
$priorUrl = $env:DATABASE_URL
try {
    $env:TEST_DATABASE_URL = & $python -c "from dotenv import dotenv_values; from sqlalchemy.engine import make_url; print(make_url(dotenv_values('.env', encoding='utf-8-sig')['DATABASE_URL']).set(database='civicfix_ai_test').render_as_string(hide_password=False))"
    if ($LASTEXITCODE -ne 0) { throw 'Could not load the test database URL.' }
    $env:DATABASE_URL = $env:TEST_DATABASE_URL
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Migration failed.' }
    & $python -m alembic check
    if ($LASTEXITCODE -ne 0) { throw 'Migration check failed.' }
    & $python -m pytest -ra
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
} finally {
    $env:TEST_DATABASE_URL = $priorTestUrl
    $env:DATABASE_URL = $priorUrl
}
```

### Phase 2 verification on 25 November 2026

The test database started with zero tables. Revision `0001_auth` applied, downgraded to base, and applied again. `alembic check` reported no schema changes. The backend suite passed 12 tests against PostgreSQL, including the Phase 1 health test. Chrome rendered the frontend with the API online, the live health endpoint returned HTTP 200, and the development database connection returned `1`. TypeScript checking and the Vite production build also passed.

## Phase 3 complaint workflow

### Repeat the leaking-pipe workflow in Windows PowerShell

From the project root, start the local PostgreSQL instance with the setup command above. Then create the dedicated Phase 3 test database if needed. This preserves the Phase 2 test database and any existing Phase 3 test data.

```powershell
$psql = Join-Path $env:ProgramFiles 'PostgreSQL\18\bin\psql.exe'
$priorPassword = $env:PGPASSWORD
try {
    $passwordFile = Join-Path $env:LOCALAPPDATA 'CivicFixAI\PostgreSQL\admin-password'
    $env:PGPASSWORD = (Get-Content -Raw -LiteralPath $passwordFile).Trim()
    $exists = & $psql -X -w -h 127.0.0.1 -p 55432 -U civicfix_local_admin -d postgres -v ON_ERROR_STOP=1 -Atc "SELECT 1 FROM pg_database WHERE datname = 'civicfix_ai_test_phase3'"
    if ($LASTEXITCODE -ne 0) { throw 'Could not check for the Phase 3 test database.' }
    if ($exists -ne '1') {
        & $psql -X -w -h 127.0.0.1 -p 55432 -U civicfix_local_admin -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE civicfix_ai_test_phase3 OWNER civicfix_app TEMPLATE template0'
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Phase 3 test database.' }
    }
} finally {
    $env:PGPASSWORD = $priorPassword
}
```

From `backend`, run the following block. The targeted test starts FastAPI in-process, seeds synthetic accounts and a service area, and prints the tracking reference and status history. The last command runs the full suite.

```powershell
$python = '.\.venv\Scripts\python.exe'
$priorTestUrl = $env:TEST_DATABASE_URL
$priorUrl = $env:DATABASE_URL
try {
    $env:TEST_DATABASE_URL = & $python -c "from dotenv import dotenv_values; from sqlalchemy.engine import make_url; print(make_url(dotenv_values('.env', encoding='utf-8-sig')['DATABASE_URL']).set(database='civicfix_ai_test_phase3').render_as_string(hide_password=False))"
    if ($LASTEXITCODE -ne 0) { throw 'Could not load the Phase 3 test database URL.' }
    $env:DATABASE_URL = $env:TEST_DATABASE_URL
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Migration failed.' }
    & $python -m alembic check
    if ($LASTEXITCODE -ne 0) { throw 'Migration check failed.' }
    & $python -m pytest tests/api/test_complaints.py::test_leaking_pipe_workflow -q -s
    if ($LASTEXITCODE -ne 0) { throw 'Workflow test failed.' }
    & $python -m pytest -ra
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
} finally {
    $env:TEST_DATABASE_URL = $priorTestUrl
    $env:DATABASE_URL = $priorUrl
}
```

To repeat the Phase 2 prerequisite on a freshly created test database, run `& $python -m alembic upgrade 0001_auth` and `& $python -m pytest tests/api/test_auth.py -q` after setting the test URL and before upgrading to head.

### Repeat the workflow over live HTTP

Open two PowerShell windows in `backend`. Run the `$python`, `TEST_DATABASE_URL`, and `DATABASE_URL` assignments from the preceding block in both windows. In the first window, start Uvicorn on the test database.

```powershell
$env:APP_ENV = 'test'
& $python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8001
```

In the second window, run the workflow using the live HTTP address.

```powershell
@'
from runpy import run_path

import httpx2
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import create_database_engine

settings = Settings()
assert settings.database_url.path == "/civicfix_ai_test_phase3"
engine = create_database_engine(settings)
try:
    workflow = run_path("tests/api/test_complaints.py")["test_leaking_pipe_workflow"]
    with Session(engine, expire_on_commit=False) as db, httpx2.Client(
        base_url="http://127.0.0.1:8001", trust_env=False
    ) as client:
        workflow(client, db)
finally:
    engine.dispose()
'@ | & $python -
```

On 25 November 2026, the live run printed `CF-2026-13CC5B | SUBMITTED -> UNDER_REVIEW -> ASSIGNED -> IN_PROGRESS -> RESOLVED | citizen retrieved 6 visible history entries`. The full backend suite passed 19 tests. The first Phase 2 test run stopped at the fixture's single database name check. All 11 authentication and access tests passed after the fixture allowed the new dedicated database.

### Complaint API

Use the bearer token for the appropriate account. Paths below start at `/api/v1`.

| Action | Method and path | Request fields |
| --- | --- | --- |
| Submit | `POST /complaints` | `title`, `description`, `latitude`, `longitude`. Optional `category_id` and `location_label`. Send an `Idempotency-Key` to safely retry a submission. |
| List and read own reports | `GET /complaints/mine`, `GET /complaints/{complaint_id}` | Use the returned UUID for the detail and history paths. |
| View staff queue | `GET /authority/complaints` | Optional `status` and `category_id` filters. |
| Review | `POST /authority/complaints/{complaint_id}/review` | `reason` and optional `public_message`. |
| Assign | `POST /authority/complaints/{complaint_id}/assignments` | `department_id`, `reason`, optional `assigned_staff_id` and `public_message`. The initial assignment moves the report to `ASSIGNED`. |
| Change status | `POST /authority/complaints/{complaint_id}/status` | `status`, `reason`, optional `public_message`. Setting `RESOLVED` also requires `resolution_description`. |
| Add a note | `POST /authority/complaints/{complaint_id}/updates` | `message` and `visibility` of `PUBLIC` or `INTERNAL`. A `PUBLIC` note is visible in the citizen's signed-in history. |
| Read progress | `GET /complaints/{complaint_id}/updates` | Citizen history includes statuses, timestamps, and messages explicitly shared with the citizen. |
| Read public complaint detail | `GET /public/complaints/{public_reference}` | Public or approximate visibility and an approved public summary are required. The response includes the reference, approved summary, category, status, and dates. |

List endpoints accept `page` and `page_size` and cap the page size at 100.

For staff intake, configure active service areas with GeoJSON `Polygon` or `MultiPolygon` boundaries in `service_areas.boundary_geojson`. Coordinates use longitude then latitude in the GeoJSON. Reports matching exactly one active area are routed to its organization. Reports outside all boundaries or inside overlapping areas stay private and unrouted. The test sets up a synthetic boundary automatically. After department assignment, staff access also requires membership in that department.

To enable these routes on the development database, run `.\.venv\Scripts\python.exe -m alembic upgrade head` from `backend` with the development database URL, then start or restart Uvicorn using the startup command above.

## Phase 5 and Phase 6

Set `GEMINI_MODEL` and `GEMINI_API_KEY` in `backend/.env` to enable analysis for new reports. The API commits the report before contacting Gemini. An unavailable or invalid response records a failed analysis and staff can continue reviewing the complaint. Duplicate suggestions use recent reports in the same service area and remain available with Gemini disabled.

Run the migrations from `backend` and `npm.cmd ci` from `frontend`, then start both apps with the commands above. Open [Sign in](http://localhost:5173/login). Staff open the [complaint queue](http://localhost:5173/authority/complaints). Administrators provision staff in [Users](http://localhost:5173/admin/users), manage [Departments](http://localhost:5173/admin/departments) and [Categories](http://localhost:5173/admin/categories), and review [Audit history](http://localhost:5173/admin/audit-logs).

Staff can open a routed water-leak report, move it to **Under review**, assign a department and optional staff member, and move it to **In progress** then **Resolved** with resolution details. Use the **Public progress message** field for text the citizen should read. Use **Internal reason** and **Internal staff only** for staff records. In **Audit history**, use the complaint UUID from its detail URL to find assignment, category, priority, and status events.

### Phase 5 and Phase 6 backend checks

Create a dedicated `civicfix_ai_test_phase6` database using the PowerShell database creation block above and substitute that name for `civicfix_ai_test` in the test URL block. From `backend`, with `DATABASE_URL` and `TEST_DATABASE_URL` set to that test database, run these commands. The tests seed synthetic scoped accounts and reports, and mock Gemini.

```powershell
$python = '.\.venv\Scripts\python.exe'
& $python -m alembic upgrade head
& $python -m alembic check
& $python -m pytest tests/api/test_intelligence.py tests/api/test_authority.py -q
& $python -m pytest -q
```

## Phase 7 dashboards and citizen workflow

Citizens sign in at `/login`, then use `/citizen/dashboard`, `/citizen/complaints`, and `/citizen/notifications`. Staff and admins have separate dashboards at `/authority/dashboard` and `/admin/dashboard`. Dashboard counts come from PostgreSQL. Open means submitted, under review, assigned, or in progress. Resolved totals include closed reports. The admin resolution-time average uses the elapsed time between submission and the latest resolution of currently resolved or closed reports.

After migrating the dedicated test database to head, run `& $python -m pytest tests/api/test_engagement.py tests/api/test_dashboards.py -q` from `backend` and `npm.cmd test` from `frontend`.

## Phase 8 Windows PowerShell verification

Use synthetic accounts only. Start the local PostgreSQL instance with `scripts/setup-postgres.ps1` as described above. Use separate, empty database names for the test and restore steps. If a name below already exists, append a unique suffix to it and update the matching commands.

### 1. Create the source and restore databases

From the project root, run this with the PostgreSQL instance running.

```powershell
$pgBin = Join-Path $env:ProgramFiles 'PostgreSQL\18\bin'
$source = 'civicfix_ai_test_phase8'
$restore = 'civicfix_ai_test_phase8_restore'
$previousPgPassword = $env:PGPASSWORD
try {
    $passwordFile = Join-Path $env:LOCALAPPDATA 'CivicFixAI\PostgreSQL\admin-password'
    $env:PGPASSWORD = (Get-Content -Raw -LiteralPath $passwordFile).Trim()
    foreach ($name in @($source, $restore)) {
        & (Join-Path $pgBin 'psql.exe') -X -w -h 127.0.0.1 -p 55432 -U civicfix_local_admin -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $name OWNER civicfix_app TEMPLATE template0"
        if ($LASTEXITCODE -ne 0) { throw "Could not create $name" }
    }
} finally {
    $env:PGPASSWORD = $previousPgPassword
}
```

### 2. Migrate, test, and start the fixture API

In a PowerShell window in `backend`, select the source database and run the tests. The final command serves the real API while replacing calls to Gemini and Cloudinary.

```powershell
$python = '.\.venv\Scripts\python.exe'
$source = 'civicfix_ai_test_phase8'
$fixture = Join-Path $env:TEMP 'civicfix-phase8-fixture.json'
& $python -m pip install -e '.[test]'
$env:TEST_DATABASE_URL = & $python -c "import sys; from dotenv import dotenv_values; from sqlalchemy.engine import make_url; print(make_url(dotenv_values('.env', encoding='utf-8-sig')['DATABASE_URL']).set(database=sys.argv[1]).render_as_string(hide_password=False))" $source
$env:DATABASE_URL = $env:TEST_DATABASE_URL
& $python -m alembic upgrade head
& $python -m alembic current
& $python -m alembic check
& $python -m pytest -q
& $python ..\scripts\phase8_fixture.py seed $fixture
& $python ..\scripts\phase8_fixture.py serve $fixture
```

### 3. Build the frontend and run the Chrome checks

In a second PowerShell window in `frontend`, run the checks and leave the production preview running. The synthetic tile URL is intercepted by the browser check.

```powershell
npm.cmd ci
npm.cmd test
npm.cmd run typecheck
npm.cmd run lint
$env:VITE_API_BASE_URL = 'http://localhost:8004/api/v1'
$env:VITE_MAP_TILE_URL = 'http://localhost:5188/phase8-tile.png?z={z}&x={x}&y={y}'
npm.cmd run build
npm.cmd exec -- vite preview --host localhost --port 5188 --strictPort
```

In a third PowerShell window from the project root, run Chrome. Set `CHROME_PATH` if Chrome is installed outside `C:\Program Files\Google\Chrome\Application\chrome.exe`. The script writes synthetic screenshots and the verified complaint reference to your temporary directory.

```powershell
$fixture = Join-Path $env:TEMP 'civicfix-phase8-fixture.json'
$report = Join-Path $env:TEMP 'civicfix-phase8-report.json'
node.exe .\scripts\check-phase8.mjs http://localhost:5188 http://localhost:8004/api/v1 $fixture $report
```

The browser starts on [the preview homepage](http://localhost:5188/). The [public map](http://localhost:5188/map) includes an accessible list. To rerun the browser script, stop the fixture API, run the seed command again, and restart the API with the new fixture. The first citizen registers in the browser.

### 4. Back up and verify the restored database

Run this from `backend` after the browser script completes. Use a newly created restore database. The comparison includes the complaint reference, status, dated public history, audit entries, and feedback retrieved through FastAPI.

```powershell
$python = '.\.venv\Scripts\python.exe'
$pgBin = Join-Path $env:ProgramFiles 'PostgreSQL\18\bin'
$source = 'civicfix_ai_test_phase8'
$restore = 'civicfix_ai_test_phase8_restore'
$fixture = Join-Path $env:TEMP 'civicfix-phase8-fixture.json'
$report = Join-Path $env:TEMP 'civicfix-phase8-report.json'
$dump = Join-Path $env:TEMP ('civicfix-phase8-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.dump')
$previousPgPassword = $env:PGPASSWORD
$previousDatabaseUrl = $env:DATABASE_URL
try {
    $passwordFile = Join-Path $env:LOCALAPPDATA 'CivicFixAI\PostgreSQL\app-password'
    $env:PGPASSWORD = (Get-Content -Raw -LiteralPath $passwordFile).Trim()
    $tableCount = & (Join-Path $pgBin 'psql.exe') -X -w -h 127.0.0.1 -p 55432 -U civicfix_app -d $restore -v ON_ERROR_STOP=1 -Atc "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"
    if ($LASTEXITCODE -ne 0 -or $tableCount -ne '0') { throw 'Restore database is not empty.' }
    & (Join-Path $pgBin 'pg_dump.exe') -Fc --no-owner --no-privileges -w -h 127.0.0.1 -p 55432 -U civicfix_app -d $source -f $dump
    if ($LASTEXITCODE -ne 0) { throw 'Database backup failed.' }
    & (Join-Path $pgBin 'pg_restore.exe') --exit-on-error --single-transaction --no-owner --no-privileges -w -h 127.0.0.1 -p 55432 -U civicfix_app -d $restore $dump
    if ($LASTEXITCODE -ne 0) { throw 'Database restore failed.' }
    $snapshots = foreach ($name in @($source, $restore)) {
        $env:DATABASE_URL = & $python -c "import sys; from dotenv import dotenv_values; from sqlalchemy.engine import make_url; print(make_url(dotenv_values('.env', encoding='utf-8-sig')['DATABASE_URL']).set(database=sys.argv[1]).render_as_string(hide_password=False))" $name
        & $python ..\scripts\phase8_fixture.py snapshot $fixture --report $report
        if ($LASTEXITCODE -ne 0) { throw "Could not verify $name" }
    }
    if ($snapshots.Count -ne 2 -or $snapshots[0] -cne $snapshots[1]) { throw 'Restored application data differs.' }
    $result = $snapshots[1] | ConvertFrom-Json
    "Restore verified for $($result.reference): $($result.status), $($result.history.Count) history entries, $($result.audit.Count) audit entries, rating $($result.feedback.rating)."
    & $python -m alembic current
    if ($LASTEXITCODE -ne 0) { throw 'Could not verify restored migration revision.' }
} finally {
    $env:PGPASSWORD = $previousPgPassword
    $env:DATABASE_URL = $previousDatabaseUrl
}
```

### Verification results on 25 November 2026

| Check | Result |
| --- | --- |
| Phase 7 acceptance | **Passed.** The backend suite passed 30 tests on `civicfix_ai_test_phase7`. The Chrome workflow passed for `CF-2026-222C68`, including unread counts of 5, 4, and 0, feedback, recipient isolation, and chart totals of 1 for the reporter, 2 for scoped staff, and 2 for the selected admin organization. The earlier cross-account return to a private report was fixed and covered by a frontend regression test. |
| Empty database and migrations | **Passed.** `alembic upgrade head` applied to `civicfix_ai_test_phase8`. `alembic current` reported `0006_publication (head)` and `alembic check` reported no new operations. |
| Chrome report and audit workflow | **Passed.** The citizen registered and submitted `CF-2026-ACB1D2`. Staff reviewed the Gemini recommendation, assigned the report, added a public update, and resolved it. The reporter opened the resolution notification, read the dated history, and submitted feedback. Admin audit entries showed the staff actor and UTC timestamp. |
| Permissions and public map | **Passed.** A second citizen received HTTP 404 for the first citizen’s notification and feedback write. Staff in a second area of the same organization received HTTP 404 for history and a priority change. The private report stayed off the map. `CF-2026-D67EAD` appeared with an approved summary and approximate coordinates. Reporter details and internal notes were absent. |
| Provider failures and optional photo | **Passed.** The mocked Gemini timeout left `CF-2026-EEB91E` in `SUBMITTED` with a tracking reference and failed analysis. The mocked Cloudinary outage returned HTTP 503. Chrome showed the upload error and continued to the saved report without a photo. |
| Homepage and form accessibility | **Passed.** Chrome checked the orange-and-black homepage and form at 1440 × 900 and 390 × 844, keyboard focus, reduced motion, and WebGL-disabled fallback. Both hero actions worked with the city module held. |
| Mobile loading | **Passed in local emulation.** With a cold cache, 150 ms latency, 1.6 Mbps down, 0.75 Mbps up, and 4× CPU slowdown, the first run showed usable hero actions at 2.66 s and live 3D at 4.22 s. The final run measured 4.47 s and 11.99 s respectively. |
| Backup and restore | **Passed.** `pg_dump -Fc` created a 169,936-byte archive. `pg_restore` restored it into the empty `civicfix_ai_test_phase8_restore`. FastAPI returned identical records for `CF-2026-ACB1D2` with status `RESOLVED`, 6 public history entries, 8 audit entries, and rating 5. |
| Backend tests | **Passed.** `& $python -m pytest tests/api/test_publication.py -q` passed 3 tests. `& $python -m pytest -q` passed 33 tests. |
| Frontend tests and build | **Passed.** `npm.cmd test` passed 7 tests. `npm.cmd run typecheck`, `npm.cmd run lint`, and `npm.cmd run build` exited successfully. Vite warned about the 925 kB minified homepage 3D chunk. |
| Local HTTP smoke checks | **Passed.** `Invoke-WebRequest -UseBasicParsing` returned HTTP 200 for `http://localhost:8004/api/v1/health` and `http://localhost:5188/`. |
| Live services and physical mobile hardware | **Unverified.** The browser used mocked Gemini, Cloudinary, and map tiles. Mobile results are from Chrome emulation. |

### Pilot checks still pending

Live Gemini and Cloudinary calls and a live tile provider require separate verification with pilot-approved configuration. The Chrome check uses a synthetic Gemini response and timeout, a synthetic Cloudinary outage, and local tile responses. The database restore covers PostgreSQL metadata and records. Evidence files stored by a configured provider need their own retention and recovery procedure.

## Phase 9 staging

The [staging deployment checklist](docs/staging-deployment.md) tracks the Render, PostgreSQL, and Vercel setup and verification results.
