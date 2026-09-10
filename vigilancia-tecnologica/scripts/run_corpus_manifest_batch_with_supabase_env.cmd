@echo off
set "ROOT=%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\run_corpus_manifest_batch_with_supabase_env.ps1" %*
