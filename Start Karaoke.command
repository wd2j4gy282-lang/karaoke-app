#!/bin/bash
cd "$(dirname "$0")"

if [ -d "venv" ]; then
  source venv/bin/activate
  PYTHON=python
else
  PYTHON=python3
fi

# Open the browser shortly after the server starts
( sleep 1.5 && open "http://localhost:5050" ) &

"$PYTHON" app.py
