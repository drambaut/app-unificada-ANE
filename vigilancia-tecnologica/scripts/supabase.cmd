@echo off
set "ROOT=%~dp0.."
set "USERPROFILE=%ROOT%\.tools"
set "HOME=%ROOT%\.tools"
"%ROOT%\.tools\supabase\supabase.exe" %*
