#!/bin/bash
# Double-click this file to start the lectionary search web app and open it
# in your browser. Close this Terminal window (or press Ctrl+C) to stop it.
cd "$(dirname "$0")"
( sleep 1 && open "http://localhost:8000" ) &
python3 webapp.py
