@echo off
wsl -d Ubuntu -- python3 -B /home/fanzhou/octosense-ws/repair-runs/context-recommend-20261004-180749/verify.py
exit /b %ERRORLEVEL%
