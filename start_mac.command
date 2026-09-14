#!/bin/bash
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Install Python 3.11 or newer, then run this file again."
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi
python3 -m pip install -r requirements.txt
python3 run_dashboard.py
