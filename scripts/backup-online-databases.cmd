@echo off
rem Copies the CRM's, Inventory's, Admin's and Platform's online databases into dated SQLite
rem files on this computer: backend\.data\backups\<module>-YYYY-MM-DD.db, keeping the last 30
rem of each. Which database each copies is <MODULE>_BACKUP_FROM in backend\.env (CRM_BACKUP_FROM,
rem INVENTORY_BACKUP_FROM, ADMIN_BACKUP_FROM, PLATFORM_BACKUP_FROM), else BACKUP_FROM, else
rem DATABASE_URL.
rem
rem Run it by hand, or every night with Windows' Task Scheduler:
rem   schtasks /Create /TN "Bishnoi One backup" /SC DAILY /ST 21:00 /TR "\"%~f0\""

setlocal
set ROOT=%~dp0..
set FAILED=0
pushd "%ROOT%\backend"
for %%A in (crm inventory admin platform) do (
  echo == %%A
  call uv run python -m modules.%%A.tools.copy_database backup || set FAILED=1
)
popd
if %FAILED%==1 (
  echo A backup didn't finish. See the messages above.
  exit /b 1
)
echo All backups done.
