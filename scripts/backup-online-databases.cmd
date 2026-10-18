@echo off
rem Copies the CRM's, Inventory's, Admin's and Platform's online databases (Neon) into dated SQLite
rem files on this computer: bishnoi-<app>\backend\.data\backups\<app>-YYYY-MM-DD.db,
rem keeping the last 30 of each. Each app's BACKUP_FROM (in its backend\.env)
rem says which database to copy.
rem
rem Run it by hand, or every night with Windows' Task Scheduler:
rem   schtasks /Create /TN "Bishnoi One backup" /SC DAILY /ST 21:00 /TR "\"%~f0\""

setlocal
set ROOT=%~dp0..
set FAILED=0
for %%A in (crm inventory admin platform) do (
  echo == %%A
  pushd "%ROOT%\bishnoi-%%A\backend"
  call uv run python -m app.tools.copy_database backup || set FAILED=1
  popd
)
if %FAILED%==1 (
  echo A backup didn't finish. See the messages above.
  exit /b 1
)
echo All backups done.
