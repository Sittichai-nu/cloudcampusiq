<#
.SYNOPSIS
    Developer entry point for CloudCampusIQ.

.DESCRIPTION
    One script for every routine task, so the commands live in the repo instead
    of in someone's shell history.

      .\dev.ps1            rebuild content, then serve on http://localhost:5000
      .\dev.ps1 serve      same as above
      .\dev.ps1 rebuild    rebuild the content database from content/*.yaml
      .\dev.ps1 test       run the test suite
      .\dev.ps1 check      rebuild + test + scan for banned strings
      .\dev.ps1 install    install runtime and dev dependencies
#>

param(
    [ValidateSet("serve", "rebuild", "test", "check", "install", "help")]
    [string]$Command = "serve"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $Root

# Strings that must never reappear in the repo. The project was renamed away
# from an internal course code; this is what stops it creeping back in.
$BannedStrings = @("D324")

function Get-Python {
    foreach ($candidate in @(".venv\Scripts\python.exe", "venv\Scripts\python.exe")) {
        if (Test-Path $candidate) { return (Resolve-Path $candidate).Path }
    }
    $found = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $found) { throw "python not found on PATH" }
    return $found.Source
}

function Invoke-Rebuild {
    param([string]$Python)
    Write-Host "==> Rebuilding content database" -ForegroundColor Cyan
    & $Python -m flask --app app.py rebuild-content
    if ($LASTEXITCODE -ne 0) { throw "content rebuild failed" }
}

function Invoke-Tests {
    param([string]$Python)
    Write-Host "==> Running tests" -ForegroundColor Cyan
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "tests failed" }
}

function Invoke-BannedScan {
    Write-Host "==> Scanning for banned strings" -ForegroundColor Cyan
    # .claude/ is excluded because the skill documents the rule and has to be
    # able to name the string it bans.
    $files = Get-ChildItem -Recurse -File -Force |
        Where-Object { $_.FullName -notmatch '\\(\.git|\.claude|__pycache__|instance|\.venv|venv|node_modules)\\' } |
        Where-Object { $_.Name -notin @("dev.ps1", "dev.sh") }

    $hits = @()
    foreach ($banned in $BannedStrings) {
        $hits += $files | Select-String -Pattern $banned -SimpleMatch
    }

    if ($hits.Count -gt 0) {
        $hits | ForEach-Object { Write-Host "    $($_.Path):$($_.LineNumber): $($_.Line.Trim())" -ForegroundColor Red }
        throw "found $($hits.Count) banned string reference(s)"
    }
    Write-Host "    clean" -ForegroundColor Green
}

$Python = Get-Python

switch ($Command) {
    "install" {
        Write-Host "==> Installing dependencies" -ForegroundColor Cyan
        & $Python -m pip install -r requirements.txt
        & $Python -m pip install -r requirements-dev.txt
    }
    "rebuild" {
        Invoke-Rebuild -Python $Python
    }
    "test" {
        Invoke-Tests -Python $Python
    }
    "check" {
        Invoke-Rebuild -Python $Python
        Invoke-Tests -Python $Python
        Invoke-BannedScan
        Write-Host "==> All checks passed" -ForegroundColor Green
    }
    "serve" {
        Invoke-Rebuild -Python $Python
        Write-Host "==> Serving on http://localhost:5000  (Ctrl+C to stop)" -ForegroundColor Cyan
        & $Python app.py
    }
    "help" {
        Get-Help $PSCommandPath -Detailed
    }
}
