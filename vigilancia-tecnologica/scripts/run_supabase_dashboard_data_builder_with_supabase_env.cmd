@echo off
set "ROOT=%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\run_supabase_dashboard_data_builder_with_supabase_env.ps1" %*
