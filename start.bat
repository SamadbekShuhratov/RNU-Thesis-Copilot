@echo off
REM RNU Thesis Copilot — first run creates a virtual environment and installs dependencies.
cd /d "%~dp0"
if not exist .venv (
  echo Creating virtual environment...
  py -3 -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\pip install -r requirements.txt
)
.venv\Scripts\python -m app %*
