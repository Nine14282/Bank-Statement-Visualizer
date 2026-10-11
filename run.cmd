@echo off
setlocal
rem Open Statement Visualizer: the setup page the first time, then the add-statements page (run.cmd --rebuild: just rebuild).
rem Same options as ./run.sh; the work is done by workspace\launcher.py.
call "%~dp0workspace\py.cmd" run %*
set code=%errorlevel%
rem Opened by double-click, the window would close before an error can be read.
if not %code%==0 pause
exit /b %code%
