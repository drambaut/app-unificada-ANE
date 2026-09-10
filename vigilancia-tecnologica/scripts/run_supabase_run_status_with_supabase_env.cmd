@echo off
set "ROOT=%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\run_supabase_run_status_with_supabase_env.ps1" %*
