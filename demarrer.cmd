@echo off
rem Double-clic : prepare ce qui manque, puis ouvre l'interface du bot evolutif (voir demarrer.ps1).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0demarrer.ps1" %*
if errorlevel 1 pause
