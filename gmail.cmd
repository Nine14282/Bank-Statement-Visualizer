@echo off
setlocal
rem Download new statement PDFs from Gmail into Statement\, then rebuild the dashboard (gmail.cmd --listen: keep running).
rem Same options as ./gmail.sh; the work is done by workspace\launcher.py.
call "%~dp0workspace\py.cmd" gmail %*
set code=%errorlevel%
rem Opened by double-click, the window would close before an error can be read.
if not %code%==0 pause
exit /b %code%
