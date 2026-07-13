@echo off
rem restart loop - if the script dies, wait 10s and bring it back
cd /d C:\AlJazeera
:loop
py main.py >> bridge.log 2>&1
echo [%date% %time%] bridge exited, restarting in 10s... >> bridge.log
timeout /t 10 /nobreak > nul
goto loop
