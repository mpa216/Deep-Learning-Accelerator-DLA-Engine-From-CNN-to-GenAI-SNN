param(
    [int]$SeedStart = 0,
    [int]$SeedEnd = 9,
    [int]$Scale = 8,
    [string]$OutDir = "tb/data/g300_samples",
    [string]$OutPrefix = "g300_output",
    [string]$PythonPath = ""
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$apicDir = Split-Path -Parent $scriptDir

if (-not $PythonPath) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        $PythonPath = $cmd.Source
    }
}

if (-not $PythonPath) {
    $fallback = "C:/msys64/mingw64/bin/python3.12.exe"
    if (Test-Path $fallback) {
        $PythonPath = $fallback
    } else {
        throw "Python not found. Pass -PythonPath to the script."
    }
}

if ($SeedEnd -lt $SeedStart) {
    throw "SeedEnd must be >= SeedStart"
}

$genScript = Join-Path $apicDir "scripts/gen_g3000_image.py"

for ($seed = $SeedStart; $seed -le $SeedEnd; $seed++) {
    $seedDir = Join-Path $OutDir ("seed_" + $seed)

    & $PythonPath $genScript --seed $seed --out-dir $seedDir --out-prefix $OutPrefix
    if ($LASTEXITCODE -ne 0) {
        throw "gen_g3000_image.py failed for seed $seed"
    }

    $memhRel = Join-Path $seedDir "$OutPrefix$seed.memh"
    $jpgRel = Join-Path $seedDir "$OutPrefix$seed`_28x28.jpg"

    & (Join-Path $apicDir "scripts/memh_to_jpeg.ps1") -InputPath $memhRel -OutputPath $jpgRel -Width 28 -Height 28 -Scale $Scale
    if ($LASTEXITCODE -ne 0) {
        throw "memh_to_jpeg.ps1 failed for seed $seed"
    }
}

Write-Host "Wrote G300 images to $OutDir/seed_*"
