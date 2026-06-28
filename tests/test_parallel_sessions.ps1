# paw parallel session simulation
# 2 processes communicate via shared ICM blackboard
# orchestrator = wait + merge

$ErrorActionPreference = "Stop"
$tmp = Join-Path $env:TEMP "paw-parallel-test-$(Get-Random)"
$db  = Join-Path $tmp "session.db"
$runId = "parallel-smoke-$(Get-Date -Format 'HHmmss')"
$project = "test-parallel"
$waits = 0; $maxWaits = 15
$pass = $true

New-Item -ItemType Directory -Path $tmp -Force | Out-Null

Write-Host "=== PAW PARALLEL SESSION SIMULATION ===" -ForegroundColor Cyan
Write-Host "run_id : $runId"
Write-Host "db     : $db"
Write-Host ""

# --- SESSION A: planner ---
Write-Host "[Planner] writing plan..." -ForegroundColor Yellow
py -m paw blackboard write `
    --project $project --run-id $runId `
    --role planner --kind plan `
    --content "Refactor parser: extract tokenize() to its own module, then run existing tests." `
    --artifact "plan-parser-refactor.md" `
    --importance high `
    --db $db --json 2>$null

if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: planner write" -ForegroundColor Red; $pass = $false; exit 1 }
Write-Host "[Planner] OK" -ForegroundColor Green

# --- orchestrator: wait for planner ---
Write-Host "[Orchestrator] waiting for plan to land..." -ForegroundColor Cyan
do {
    $result = py -m paw blackboard read --project $project --run-id $runId --role planner --kind plan --limit 3 --db $db --json 2>$null | ConvertFrom-Json
    $waits++
    if ($waits -ge $maxWaits) { Write-Host "TIMEOUT waiting for plan" -ForegroundColor Red; $pass = $false; exit 1 }
    if ($result.status -ne "success" -or $result.entries.Count -eq 0) { Start-Sleep -Milliseconds 300 }
} while ($result.status -ne "success" -or $result.entries.Count -eq 0)
Write-Host "[Orchestrator] plan found after $waits polls" -ForegroundColor Green

# --- SESSION B: implementer ---
Write-Host "[Implementer] reading plan, writing result..." -ForegroundColor Yellow
$plan = $result.entries[0].content
Write-Host "[Implementer] received: '$($plan.Substring(0, [Math]::Min(40, $plan.Length)))...'" -ForegroundColor Gray

py -m paw blackboard write `
    --project $project --run-id $runId `
    --role implementer --kind result `
    --content "Done: created tokenizer.py, moved tokenize() over, all existing 12 tests green." `
    --artifact "patch-1.diff" `
    --importance high `
    --db $db --json 2>$null

if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: implementer write" -ForegroundColor Red; $pass = $false; exit 1 }
Write-Host "[Implementer] OK" -ForegroundColor Green

# --- SESSION C: reviewer (in parallel with implementer — simulate concurrent) ---
Start-Job -Name "reviewer-job" -ScriptBlock {
    param($proj, $rid, $dbPath)
    Start-Sleep -Seconds 1
    py -m paw blackboard write --project $proj --run-id $rid --role reviewer --kind review --content "PASS: tokenizer extraction clean, tests pass." --db $dbPath --json 2>$null
} -ArgumentList $project, $runId, $db | Out-Null

# --- orchestrator: wait for implementer + reviewer ---
Write-Host "[Orchestrator] waiting for implementer + reviewer..." -ForegroundColor Cyan

$waits = 0
do {
    $all = py -m paw blackboard read --project $project --run-id $runId --limit 10 --db $db --json 2>$null | ConvertFrom-Json
    $waits++
    if ($waits -ge $maxWaits) { Write-Host "TIMEOUT waiting for peers" -ForegroundColor Red; $pass = $false; exit 1 }
    $roles = $all.entries | ForEach-Object { $_.role } | Sort-Object -Unique
    if ($roles -notcontains "implementer" -or $roles -notcontains "reviewer") { Start-Sleep -Milliseconds 300 }
} while ($roles -notcontains "implementer" -or $roles -notcontains "reviewer")

Write-Host "[Orchestrator] all $($all.entries.Count) entries after $waits polls:" -ForegroundColor Green

$all.entries | ForEach-Object {
    $c = $_.content
    $trunc = if ($c.Length -gt 50) { $c.Substring(0, 47) + "..." } else { $c }
    Write-Host "  [$($_.role):$($_.kind)] $trunc" -ForegroundColor Gray
}

# validate
$artifactCount = ($all.entries | Where-Object { $_.artifact }).Count
Write-Host ""
Write-Host "=== RESULT ===" -ForegroundColor Cyan
Write-Host "entries     : $($all.entries.Count)" -ForegroundColor $(if ($all.entries.Count -ge 3) { "Green" } else { "Red" })
Write-Host "artifacts   : $artifactCount"
Write-Host "pass        : $pass"
Write-Host "run_id      : $runId"

# cleanup
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue

if (-not $pass) { exit 1 }
