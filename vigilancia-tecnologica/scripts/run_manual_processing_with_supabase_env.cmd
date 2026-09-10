@echo off
set "ROOT=%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\run_manual_processing_with_supabase_env.ps1" %*
