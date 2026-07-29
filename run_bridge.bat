@echo off
rem restart loop - if the script dies, wait 10s and bring it back
rem note: using ping as the sleep, not timeout - timeout needs a console stdin
rem and fails instantly when launched hidden, which turns this into a hot loop
cd /d C:\AlJazeera
:loop
py main.py >> bridge.log 2>&1
echo [%date% %time%] bridge exited, restarting in 10s... >> bridge.log
ping -n 11 127.0.0.1 > nul
goto loop
