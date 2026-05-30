$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $RepoRoot "logs"
$DataDir = Join-Path $RepoRoot "data"
$RejectsDir = Join-Path $DataDir "rejects"

New-Item -ItemType Directory -Force -Path $LogDir, $DataDir, $RejectsDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogFile = Join-Path $LogDir "scheduled-crawl-$Timestamp.log"

if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found at $Python"
}

Set-Location $RepoRoot

& $Python -m ingestion.cli scheduled-crawl `
    --profile conservative `
    --canonical-output "data\scheduled_crawl_latest.jsonl" `
    --rejects-dir "data\rejects" `
    --insecure-skip-tls-verify *> $LogFile

exit $LASTEXITCODE
