# Scheduling

The toolkit has **no scheduler of its own**. A run is one command with documented exit
codes, so any external scheduler can start it and react to the result. Only the Windows
Task Scheduler is documented, because Windows is the only tested system; cron and other
schedulers will be documented after their platform has been tested.

## The wrapper script

[scripts/scheduling/run_monthly_sales.ps1](../scripts/scheduling/run_monthly_sales.ps1)
runs the monthly example for one period and returns the exit code of `data-automate`
unchanged:

| Parameter | Default | Meaning |
| --- | --- | --- |
| `-Period` | previous month (`YYYY-MM`) | Month to process; validated before anything runs |
| `-DataAutomate` | `.venv\Scripts\data-automate.exe` of the project | Executable to use |
| `-Overwrite` | off | Replace the outputs of a period already processed |

A task scheduled on the 1st of each month therefore processes the month that just ended.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\scheduling\run_monthly_sales.ps1 -Period 2026-09
```

**Tested** (`tests/cli/test_cli_run.py::test_task_scheduler_wrapper_script`, on Windows 11
with Windows PowerShell): the script runs the workflow in a copy of the project, returns
0 and produces the expected file; a second run returns 3 (already processed, nothing
touched); with `-Overwrite` it returns 0 again.

## Creating the task

The command below creates a monthly task. It is **documented, not executed** during
development (creating a task changes the system configuration); adapt the paths first.

```powershell
schtasks /Create /TN "Data automation - monthly sales" /SC MONTHLY /D 1 /ST 06:00 `
  /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"C:\path\to\python-data-automation-toolkit\scripts\scheduling\run_monthly_sales.ps1\""
```

Or in the Task Scheduler window: *Create Task* → *Triggers*: monthly, day 1 → *Actions*:
program `powershell.exe`, arguments
`-NoProfile -ExecutionPolicy Bypass -File "C:\path\to\...\run_monthly_sales.ps1"`.
Choose *Run whether user is logged on or not* only if the account can read the data
folders.

## Reading the result

The *Last Run Result* column shows the exit code (in hexadecimal, e.g. `0x3`):

| Code | Meaning | What to do |
| --- | --- | --- |
| 0 | Success | Nothing |
| 1 | Run failed, nothing published | Read `runs/<workflow>/<run id>/run_report.md` |
| 3 | Refused before running | Usually: the period was already processed, files are missing, or another run holds the lock ([troubleshooting](running.md#troubleshooting)) |
| 4 | Partial (`on_error: continue`) | Read the report: some outputs were not produced |
| 130 | Interrupted | Run again |

Every run that starts writes its report in its own folder, so a history of scheduled runs
is kept in `runs/`. Delete old run folders when they are no longer needed; the toolkit never
deletes them.
