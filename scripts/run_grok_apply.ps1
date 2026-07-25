# Run one Grok job application on the self-hosted machine.
# Expects:
#   JOB_APPLY_WORKDIR  - private data dir (queue, ledger, CV)
#   GROK_APPLY_ROOT    - optional path/clone of grok_apply_with_report
#   COMPLETE_MAX       - default 1
#   CDP_URL            - default http://127.0.0.1:9223

$ErrorActionPreference = "Continue"
$workdir = if ($env:JOB_APPLY_WORKDIR) { $env:JOB_APPLY_WORKDIR } else {
  Join-Path $env:USERPROFILE "job-application-bot\data\etoro-apply-report"
}
$env:JOB_APPLY_WORKDIR = $workdir
$env:COMPLETE_MAX = if ($env:COMPLETE_MAX) { $env:COMPLETE_MAX } else { "1" }
$env:APPLY_BROWSER = if ($env:APPLY_BROWSER) { $env:APPLY_BROWSER } else { "chromium" }
$env:CDP_URL = if ($env:CDP_URL) { $env:CDP_URL } else { "http://127.0.0.1:9223" }
$env:OPEN_REPORT = if ($env:OPEN_REPORT) { $env:OPEN_REPORT } else { "0" }
$env:APPLY_BROWSER_FULLSCREEN = if ($env:APPLY_BROWSER_FULLSCREEN) { $env:APPLY_BROWSER_FULLSCREEN } else { "0" }
$env:ONE_PER_COMPANY = if ($env:ONE_PER_COMPANY) { $env:ONE_PER_COMPANY } else { "1" }
$env:SKIP_ATTEMPTED = if ($env:SKIP_ATTEMPTED) { $env:SKIP_ATTEMPTED } else { "1" }
$env:USE_CHATBOT = "0"
$env:SKIP_WORKDAY = if ($env:SKIP_WORKDAY) { $env:SKIP_WORKDAY } else { "1" }
$env:PYTHONUNBUFFERED = "1"

# Prefer queue produced by check_in_applications.py
$queueCsv = Join-Path $workdir "applications_resolved_ats.csv"
if (Test-Path $queueCsv) {
  $env:COMPLETE_QUEUE_CSV = $queueCsv
}

$grokRoot = $env:GROK_APPLY_ROOT
if (-not $grokRoot -or -not (Test-Path $grokRoot)) {
  $candidates = @(
    (Join-Path $env:USERPROFILE "grok_apply_with_report"),
    (Join-Path $env:USERPROFILE "deepline\src\grok_apply_with_report"),
    "C:\grok_apply_with_report"
  )
  foreach ($c in $candidates) {
    if (Test-Path (Join-Path $c "grok_apply_with_report.py")) {
      $grokRoot = $c
      break
    }
  }
}

# Clone if still missing
if (-not $grokRoot -or -not (Test-Path (Join-Path $grokRoot "grok_apply_with_report.py"))) {
  $grokRoot = Join-Path $env:USERPROFILE "grok_apply_with_report"
  if (-not (Test-Path $grokRoot)) {
    Write-Host "Cloning grok_apply_with_report into $grokRoot"
    git clone --depth 1 https://github.com/martibayoalemany9/grok_apply_with_report.git $grokRoot
  }
}
$env:GROK_APPLY_ROOT = $grokRoot
Write-Host "GROK_APPLY_ROOT=$grokRoot"
Write-Host "JOB_APPLY_WORKDIR=$workdir"
Write-Host "COMPLETE_QUEUE_CSV=$($env:COMPLETE_QUEUE_CSV)"
Write-Host "CDP_URL=$($env:CDP_URL)"

# Prefer workdir complete_apply if present (private full tree), else repo entrypoint
$py = "python"
if (Get-Command python -ErrorAction SilentlyContinue) { $py = "python" }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py -3" }

# Quick CDP probe before launching long browser automation
$cdp = if ($env:CDP_URL) { $env:CDP_URL } else { "http://127.0.0.1:9223" }
try {
  $null = Invoke-WebRequest -Uri "$cdp/json/version" -TimeoutSec 5 -UseBasicParsing
  Write-Host "CDP reachable: $cdp"
} catch {
  Write-Error "CDP not reachable at $cdp — start Chromium with --remote-debugging-port=9223"
  exit 3
}

$entry = Join-Path $grokRoot "grok_apply_with_report.py"
$privateApply = Join-Path $workdir "complete_apply.py"
if (Test-Path $privateApply) {
  Write-Host "Using private complete_apply.py in workdir"
  & python -u $privateApply
  $code = $LASTEXITCODE
} elseif (Test-Path $entry) {
  Write-Host "Using grok_apply_with_report.py"
  & python -u $entry --no-open
  $code = $LASTEXITCODE
} else {
  Write-Error "No apply entrypoint found (clone grok_apply_with_report or set GROK_APPLY_ROOT)"
  exit 2
}

Write-Host "apply_exit=$code"
exit $code
