<#
.SYNOPSIS
    Run the monthly sales workflow for one period; intended for the Windows Task Scheduler.

.DESCRIPTION
    By default the period is the previous month (YYYY-MM), so a task scheduled at the start
    of a month processes the month that just ended. The script returns the exit code of
    data-automate unchanged, so the Task Scheduler shows it as "Last Run Result":
    0 success, 1 run failed, 3 refused before running (e.g. the output already exists),
    4 partial run, 130 interrupted.

.PARAMETER Period
    Month to process (YYYY-MM). Default: the previous month.

.PARAMETER DataAutomate
    Path of the data-automate executable (default: data-automate.exe of the project's .venv).

.PARAMETER Overwrite
    Replace the outputs of a period that was already processed.

.EXAMPLE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\scheduling\run_monthly_sales.ps1 -Period 2026-09
#>
param(
    [ValidatePattern('^\d{4}-(0[1-9]|1[0-2])$')]
    [string]$Period = (Get-Date).AddMonths(-1).ToString('yyyy-MM'),
    [string]$DataAutomate = '',
    [switch]$Overwrite
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $DataAutomate) {
    $DataAutomate = Join-Path $projectRoot '.venv\Scripts\data-automate.exe'
}
$workflow = Join-Path $projectRoot 'config\examples\monthly_sales.yaml'

$arguments = @('run', $workflow, '--param', "period=$Period")
if ($Overwrite) { $arguments += '--overwrite' }

& $DataAutomate @arguments
exit $LASTEXITCODE
