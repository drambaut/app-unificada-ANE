param(
    [string]$Manifest = "outputs/corpus_processing_manifest.csv",
    [int]$StartBatch = 2,
    [int]$EndBatch = 25,
    [switch]$Smoke,
    [switch]$ResetFailed,
    [switch]$StopOnBatchFailure,
    [switch]$DryRun
)

# Procesa varios lotes del manifiesto de corpus de forma secuencial y automatica,
# reutilizando run_corpus_manifest_batch_with_supabase_env.ps1 para cada batch.
# Los fallos de documentos individuales dentro de un batch NO detienen el
# recorrido (son normales); usa -StopOnBatchFailure si prefieres detenerte ante
# el primer batch con al menos un documento fallido.

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$batchRunner = Join-Path $root "scripts\run_corpus_manifest_batch_with_supabase_env.ps1"

$summary = @()

for ($i = $StartBatch; $i -le $EndBatch; $i++) {
    $batchId = "batch-{0:D3}" -f $i
    $reportPath = Join-Path $root "outputs\corpus_${batchId}_report.csv"

    Write-Host ""
    Write-Host "=== Procesando $batchId ($($i - $StartBatch + 1) de $($EndBatch - $StartBatch + 1)) ===" -ForegroundColor Cyan

    $runnerArgs = @($Manifest, "--batch-id", $batchId, "--skip-existing", "--report-csv", $reportPath)
    if ($Smoke) { $runnerArgs += "--smoke" }
    if ($ResetFailed) { $runnerArgs += "--reset-failed" }
    if ($DryRun) { $runnerArgs += "--dry-run" }

    & $batchRunner @runnerArgs
    $exitCode = $LASTEXITCODE

    $processed = 0; $failed = 0; $skipped = 0; $quotaExhausted = $false
    if (-not $DryRun -and (Test-Path -LiteralPath $reportPath)) {
        $rows = @(Import-Csv -LiteralPath $reportPath)
        $failed = @($rows | Where-Object { $_.status -eq "failed" }).Count
        $skipped = @($rows | Where-Object { $_.status -eq "skipped" }).Count
        $processed = $rows.Count - $failed - $skipped
        $quotaExhausted = @($rows | Where-Object {
            $_.status -eq "failed" -and $_.error -match "RESOURCE_EXHAUSTED|spending cap"
        }).Count -gt 0
    }
    $summary += [PSCustomObject]@{
        Batch = $batchId; Procesados = $processed; Fallidos = $failed; Omitidos = $skipped
    }

    if ($quotaExhausted) {
        Write-Host ""
        Write-Host "Cuota de Gemini agotada (RESOURCE_EXHAUSTED / spending cap). Deteniendo todo el recorrido." -ForegroundColor Red
        Write-Host "Revisa/aumenta el limite en https://ai.studio/spend y luego reanuda con -ResetFailed desde $batchId." -ForegroundColor Red
        break
    }

    if ($StopOnBatchFailure -and $failed -gt 0) {
        Write-Host "Deteniendo: $batchId tuvo $failed documento(s) fallido(s)." -ForegroundColor Yellow
        break
    }
}

Write-Host ""
Write-Host "=== Resumen total ===" -ForegroundColor Cyan
$summary | Format-Table -AutoSize
Write-Host "Procesados: $(($summary | Measure-Object Procesados -Sum).Sum)"
Write-Host "Fallidos:   $(($summary | Measure-Object Fallidos -Sum).Sum)"
Write-Host "Omitidos:   $(($summary | Measure-Object Omitidos -Sum).Sum)"
Write-Host ""
Write-Host "Cuando termines, publica el analisis transversal para actualizar el dashboard:"
Write-Host "  python run_supabase_transversal.py --bounded-context"
