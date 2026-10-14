@echo off
REM ====================================================================
REM  Same-day data check.
REM
REM  Either:  double-click this file          -> checks ALL collected data
REM  Or:      drag a session folder onto it   -> checks just that session
REM
REM  Prints the validity effect (the primary outcome), the self-timing
REM  summary and the simple-RT summary, straight from the CSV files.
REM ====================================================================
setlocal
set "HERE=%~dp0"

REM --- which folder to look at ---------------------------------------
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=%HERE%data"

if not exist "%TARGET%" (
  echo.
  echo No data found at: %TARGET%
  echo Run a session first, or drag a session folder onto this file.
  echo.
  pause
  exit /b 1
)

REM --- find a python that has PsychoPy (same search as the launcher) --
set "PY="
REM set "PY=C:\Program Files\PsychoPy\python.exe"
if defined PY if exist "%PY%" goto run
for %%P in (
  "C:\Program Files\PsychoPy\python.exe"
  "C:\Program Files (x86)\PsychoPy\python.exe"
  "%LOCALAPPDATA%\Programs\PsychoPy\python.exe"
  "%ProgramFiles%\PsychoPy3\python.exe"
) do (
  if exist %%P (
    set "PY=%%~P"
    goto run
  )
)
set "PY=python"

:run
"%PY%" "%HERE%tools\quicklook.py" "%TARGET%"
echo.
pause
endlocal
