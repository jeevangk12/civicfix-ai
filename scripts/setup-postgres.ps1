param(
    [string]$PostgresBin = (Join-Path $env:ProgramFiles 'PostgreSQL\18\bin')
)

$ErrorActionPreference = 'Stop'
$pgRoot = Join-Path $env:LOCALAPPDATA 'CivicFixAI\PostgreSQL'
$pgData = Join-Path $pgRoot 'data'
$pgLog = Join-Path $pgRoot 'postgres.log'
$adminPasswordFile = Join-Path $pgRoot 'admin-password'
$appPasswordFile = Join-Path $pgRoot 'app-password'
$initdb = Join-Path $PostgresBin 'initdb.exe'
$pgCtl = Join-Path $PostgresBin 'pg_ctl.exe'
$psql = Join-Path $PostgresBin 'psql.exe'
$port = 55432

function New-LocalSecret {
    $bytes = New-Object byte[] 32
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $random.GetBytes($bytes)
    } finally {
        $random.Dispose()
    }
    return [System.BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
}

function Get-LocalPassword([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        Set-Content -LiteralPath $Path -Value (New-LocalSecret) -Encoding ascii
    }
    return (Get-Content -LiteralPath $Path -Raw).Trim()
}

if (-not (Test-Path -LiteralPath $initdb)) {
    throw "PostgreSQL was not found at $PostgresBin. Pass the installed bin directory as -PostgresBin."
}

New-Item -ItemType Directory -Path $pgRoot -Force | Out-Null
$adminPassword = Get-LocalPassword $adminPasswordFile
$appPassword = Get-LocalPassword $appPasswordFile

if (-not (Test-Path -LiteralPath (Join-Path $pgData 'PG_VERSION'))) {
    & $initdb -D $pgData --username=civicfix_local_admin --auth=scram-sha-256 "--pwfile=$adminPasswordFile" --encoding=UTF8
    if ($LASTEXITCODE -ne 0) { throw "initdb failed with exit code $LASTEXITCODE." }
}

& $pgCtl status -D $pgData | Out-Null
if ($LASTEXITCODE -ne 0) {
    & $pgCtl start -D $pgData -l $pgLog -o "-h 127.0.0.1 -p $port" -w
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL could not start. See $pgLog." }
}

$previousPgPassword = $env:PGPASSWORD
$previousAppPassword = $env:CIVICFIX_SETUP_APP_PASSWORD
try {
    $env:PGPASSWORD = $adminPassword
    $env:CIVICFIX_SETUP_APP_PASSWORD = $appPassword
    @'
\getenv app_password CIVICFIX_SETUP_APP_PASSWORD
SELECT format('CREATE ROLE civicfix_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'civicfix_app')
\gexec
SELECT 'CREATE DATABASE civicfix_ai OWNER civicfix_app'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'civicfix_ai')
\gexec
'@ | & $psql -X -w -h 127.0.0.1 -p $port -U civicfix_local_admin -d postgres -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) { throw "Database setup failed with exit code $LASTEXITCODE." }
} finally {
    $env:PGPASSWORD = $previousPgPassword
    $env:CIVICFIX_SETUP_APP_PASSWORD = $previousAppPassword
}

$backend = Join-Path (Split-Path -Parent $PSScriptRoot) 'backend'
$envFile = Join-Path $backend '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    $example = Get-Content -LiteralPath (Join-Path $backend '.env.example') -Raw
    $config = $example.Replace('replace-with-local-password', $appPassword).Replace('replace-with-long-random-secret', (New-LocalSecret))
    Set-Content -LiteralPath $envFile -Value $config -Encoding utf8
    Write-Output 'Created backend/.env.'
} else {
    $config = Get-Content -LiteralPath $envFile -Raw
    $placeholder = '(?m)^SECRET_KEY=replace-with-long-random-secret(?=\r?$)'
    if ($config -match $placeholder) {
        Set-Content -LiteralPath $envFile -Value ($config -replace $placeholder, ('SECRET_KEY=' + (New-LocalSecret))) -Encoding utf8 -NoNewline
        Write-Output 'Replaced the Phase 1 signing-key placeholder in backend/.env.'
    }
}
Write-Output "PostgreSQL is running on 127.0.0.1:$port with database civicfix_ai."
