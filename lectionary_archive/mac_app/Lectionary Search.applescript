-- Source for the "Lectionary Search.app" launcher.
-- Compile it into a real double-clickable app with:
--   osacompile -o "Lectionary Search.app" "Lectionary Search.applescript"
--
-- If your project isn't at the path below, edit appDir first.

set appDir to "/Users/mattstout/Documents/GitHub/worship-planning/lectionary_archive"
set webappPath to appDir & "/webapp.py"

do shell script "pgrep -f " & quoted form of webappPath & " >/dev/null 2>&1 || (cd " & quoted form of appDir & " && nohup python3 " & quoted form of webappPath & " > webapp.log 2>&1 &); sleep 1; open http://localhost:8000"
