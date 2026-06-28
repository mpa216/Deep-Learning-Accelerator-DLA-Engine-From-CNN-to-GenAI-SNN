$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$apicDir = Split-Path -Parent $scriptDir
$resultsDir = Join-Path $scriptDir "results"
$tbDir = Join-Path $apicDir "tb"
$rtlDir = Join-Path $apicDir "rtl"

if (-not (Test-Path $resultsDir)) {
    New-Item -Path $resultsDir -ItemType Directory | Out-Null
}

$rtlFiles = Get-ChildItem -Path (Join-Path $rtlDir "*.v") | Sort-Object Name | ForEach-Object { $_.FullName }
if ($rtlFiles.Count -eq 0) {
    throw "No RTL files matching $rtlDir/*.v were found."
}

$tbFiles = Get-ChildItem -Path (Join-Path $tbDir "*_tb.sv") | Sort-Object Name
if ($tbFiles.Count -eq 0) {
    throw "No testbench files matching *_tb.sv were found in $tbDir"
}

foreach ($tb in $tbFiles) {
    $tbName = [System.IO.Path]::GetFileNameWithoutExtension($tb.Name)
    $outVvp = Join-Path $resultsDir "$tbName.vvp"
    $logFile = Join-Path $resultsDir "$tbName.log"

    Write-Host "[SIM] Compiling $tbName..."
    & iverilog -g2012 -I $rtlDir -s $tbName -o $outVvp @rtlFiles $tb.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "iverilog compilation failed for $tbName with exit code $LASTEXITCODE"
    }

    Write-Host "[SIM] Running $tbName..."
    Push-Location $apicDir
    try {
        & vvp $outVvp *>&1 | Tee-Object -FilePath $logFile
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) {
        throw "vvp simulation failed for $tbName with exit code $LASTEXITCODE"
    }

    Write-Host "[SIM] Completed $tbName. Log: $logFile"
}

Write-Host "[SIM] All *_tb.sv simulations passed. Results are in $resultsDir"
