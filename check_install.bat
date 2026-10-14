@echo off
REM Pre-flight check. Run this FIRST on any new computer.
setlocal
set "HERE=%~dp0"
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
echo Using python: %PY%
"%PY%" "%HERE%tools\check_install.py" %*
pause
endlocal
