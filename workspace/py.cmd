@echo off
setlocal
rem Statement Visualizer on Windows: finds Python 3 and runs workspace\launcher.py with this command's arguments.
rem The commands themselves are install.cmd, run.cmd, gmail.cmd, clear.cmd and uninstall.cmd in the project folder.
rem Prefers the "py" launcher that python.org's installer adds; else "python" on PATH. -X utf8: Thai text prints.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -X utf8 "%~dp0launcher.py" %*
) else (
  where python >nul 2>nul || (
    echo Python 3.10 or newer is needed: https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^).
    exit /b 1
  )
  python -X utf8 "%~dp0launcher.py" %*
)
exit /b %errorlevel%
