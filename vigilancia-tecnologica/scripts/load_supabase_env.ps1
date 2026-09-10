param(
    [string]$ProjectUrl = "https://iaxwkghevmdssfiqrgcz.supabase.co",
    [string]$Bucket = "source-documents",
    [string]$SecretsPath = ".tools/secrets/ane_supabase_api_keys.json"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $SecretsPath)) {
    throw "No existe el archivo de llaves: $SecretsPath"
}

$keys = Get-Content -Raw -LiteralPath $SecretsPath | ConvertFrom-Json
$anon = $keys | Where-Object { $_.name -eq "anon" } | Select-Object -First 1
$serviceRole = $keys | Where-Object { $_.name -eq "service_role" } | Select-Object -First 1

if (-not $anon -or -not $anon.api_key) {
    throw "No se encontro la llave anon en $SecretsPath"
}

if (-not $serviceRole -or -not $serviceRole.api_key) {
    throw "No se encontro la llave service_role en $SecretsPath"
}

$env:SUPABASE_URL = $ProjectUrl
$env:SUPABASE_KEY = $anon.api_key
$env:SUPABASE_SERVICE_ROLE_KEY = $serviceRole.api_key
$env:SUPABASE_STORAGE_BUCKET = $Bucket

Write-Host "Variables Supabase cargadas para esta terminal."
Write-Host "Proyecto: $ProjectUrl"
Write-Host "Bucket: $Bucket"
