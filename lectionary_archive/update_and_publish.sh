#!/bin/bash
# Runs the full weekly refresh: crawl for new lectionary weeks, rebuild the
# static export, and push it so the GitHub Pages site picks it up.
# Invoked on a schedule by com.umcdiscipleship.lectionary-scraper.plist, or
# run by hand any time: ./update_and_publish.sh

set -uo pipefail
cd "$(dirname "$0")"

echo "=== $(date) : starting scheduled update ==="

python3 scraper.py --delay 1.5
python3 export_static.py

cd ..
BRANCH="$(git symbolic-ref --short HEAD)"

git add docs/data.json

if git diff --cached --quiet; then
    echo "No changes to publish."
else
    git commit -m "Automated archive update ($(date +%Y-%m-%d))"
    if git push origin "$BRANCH"; then
        echo "Pushed to $BRANCH."
    else
        echo "PUSH FAILED -- changes are committed locally but not published. Check auth/network."
    fi
fi

echo "=== $(date) : done ==="
