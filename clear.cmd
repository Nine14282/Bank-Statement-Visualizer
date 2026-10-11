@echo off
setlocal
rem Reset all your data, as on a fresh clone (asks first; -y doesn't). The installed app stays.
rem Same options as ./clear.sh; the work is done by workspace\launcher.py.
call "%~dp0workspace\py.cmd" clear %*
set code=%errorlevel%
rem Opened by double-click, the window would close before an error can be read.
if not %code%==0 pause
exit /b %code%
