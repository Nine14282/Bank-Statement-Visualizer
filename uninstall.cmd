@echo off
setlocal
rem Remove what install.cmd set up (uninstall.cmd --all: the whole folder, data included; -n: only list).
rem Same options as ./uninstall.sh; the work is done by workspace\launcher.py.
call "%~dp0workspace\py.cmd" uninstall %*
set code=%errorlevel%
rem Opened by double-click, the window would close before an error can be read.
if not %code%==0 pause
exit /b %code%
