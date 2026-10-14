@echo off
REM ====================================================================
REM  TUS dentate nucleus task battery - Windows launcher
REM
REM  Double-click to run with the start-up dialog, or pass arguments:
REM      run_windows.bat --schedule post_tus
REM      run_windows.bat --demo
REM      run_windows.bat --list
REM
REM  If PsychoPy lives somewhere unusual, set PSYCHOPY_PYTHON below.
REM ====================================================================
setlocal
set "HERE=%~dp0"

REM --- 1. explicit override (edit this line if needed) ---------------
set "PY="
REM set "PY=C:\Program Files\PsychoPy\python.exe"
if defined PY if exist "%PY%" goto run

REM --- 2. the usual PsychoPy standalone locations --------------------
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

REM --- 3. fall back to whatever python is on PATH --------------------
set "PY=python"

:run
echo Using python: %PY%
"%PY%" "%HERE%run_experiment.py" %*
if errorlevel 1 (
  echo.
  echo The experiment exited with an error. Read the message above.
  pause
)
endlocal
