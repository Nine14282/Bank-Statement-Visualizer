@echo off
setlocal
rem Install Statement Visualizer, without opening it (safe to re-run). install.cmd --app: also the app window (not ready on Windows yet).
rem Same options as ./install.sh; the work is done by workspace\launcher.py.
call "%~dp0workspace\py.cmd" install %*
set code=%errorlevel%
rem Opened by double-click, the window would close before an error can be read.
if not %code%==0 pause
exit /b %code%
