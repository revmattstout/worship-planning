-- Source for the "Stop Lectionary Search.app" launcher.
-- Compile it into a real double-clickable app with:
--   osacompile -o "Stop Lectionary Search.app" "Stop Lectionary Search.applescript"
--
-- If your project isn't at the path below, edit appDir first.

set appDir to "/Users/mattstout/Documents/GitHub/worship-planning/lectionary_archive"
set webappPath to appDir & "/webapp.py"

try
	do shell script "pkill -f " & quoted form of webappPath
	display notification "The search server has been stopped." with title "Lectionary Search"
on error
	display notification "The search server wasn't running." with title "Lectionary Search"
end try
