#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
export PYINSTALLER_CONFIG_DIR="$PWD/.build-cache/pyinstaller"
if [[ ! -x .venv/bin/python ]]; then
  /usr/bin/python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m PyInstaller --noconfirm --clean --onefile --name MafiaTrainer \
  --add-data 'mafia_trainer/assets:mafia_trainer/assets' \
  --add-data 'mafia_trainer/web_assets:mafia_trainer/web_assets' \
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets \
  --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick main.py
printf '\nГотово: dist/MafiaTrainer\n'
