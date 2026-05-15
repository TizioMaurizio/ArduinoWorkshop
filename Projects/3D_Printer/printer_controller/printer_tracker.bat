@echo off
title Printer Tracker
cd /d "%~dp0"

:: Activate conda environment
call "%USERPROFILE%\miniconda3\condabin\conda.bat" activate base

python scripts\launcher.py %*
