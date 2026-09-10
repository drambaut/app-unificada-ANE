param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RunnerArgs
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$secretsPath = Join-Path $root ".tools/secrets/ane_supabase_api_keys.json"

if (-not (Test-Path -LiteralPath $secretsPath)) {
    throw "No existe el archivo de llaves: $secretsPath"
}

$keys = Get-Content -Raw -LiteralPath $secretsPath | ConvertFrom-Json
$anon = $keys | Where-Object { $_.name -eq "anon" } | Select-Object -First 1
$serviceRole = $keys | Where-Object { $_.name -eq "service_role" } | Select-Object -First 1

if (-not $anon -or -not $anon.api_key) {
    throw "No se encontro la llave anon en $secretsPath"
}

if (-not $serviceRole -or -not $serviceRole.api_key) {
    throw "No se encontro la llave service_role en $secretsPath"
}

$env:SUPABASE_URL = "https://iaxwkghevmdssfiqrgcz.supabase.co"
$env:SUPABASE_KEY = $anon.api_key
$env:SUPABASE_SERVICE_ROLE_KEY = $serviceRole.api_key
$env:SUPABASE_STORAGE_BUCKET = "source-documents"

Write-Host "Variables Supabase cargadas para este proceso."

$python = Join-Path $root ".venv/Scripts/python.exe"
$runner = Join-Path $root "run_corpus_manifest_batch.py"
& $python $runner @RunnerArgs
exit $LASTEXITCODE
