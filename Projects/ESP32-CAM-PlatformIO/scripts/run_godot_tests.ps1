## Run all Godot tests headless.
## Usage from repo root: scripts\run_godot_tests.ps1 [-GodotPath "path\to\godot.exe"]

param(
    [string]$GodotPath = "godot"
)

$ErrorActionPreference = "Stop"
$projectDir = Join-Path $PSScriptRoot "..\Godot"
$testDir = Join-Path $projectDir "test"
$testFiles = Get-ChildItem -Path $testDir -Filter "test_*.gd"
$totalPass = 0
$totalFail = 0

Write-Host "=== Running Godot Tests ===" -ForegroundColor Cyan
Write-Host "Project: $projectDir"
Write-Host ""

foreach ($tf in $testFiles) {
    $scriptPath = "res://test/$($tf.Name)"
    Write-Host "--- $($tf.Name) ---" -ForegroundColor Yellow

    $output = & $GodotPath --headless --path $projectDir --script $scriptPath 2>&1
    $exitCode = $LASTEXITCODE

    foreach ($line in $output) {
        if ($line -match "\[PASS\]") {
            Write-Host $line -ForegroundColor Green
            $totalPass++
        } elseif ($line -match "\[FAIL\]") {
            Write-Host $line -ForegroundColor Red
            $totalFail++
        } else {
            Write-Host $line
        }
    }

    if ($exitCode -ne 0) {
        Write-Host "  EXIT CODE: $exitCode" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "=== Total: $totalPass passed, $totalFail failed ===" -ForegroundColor Cyan
if ($totalFail -gt 0) {
    exit 1
}
exit 0
