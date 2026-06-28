param(
    [string]$InputPath = "tb/data/d3004_input.memh",
    [string]$OutputPath = "tb/data/d3004_input_16x16.jpg",
    [int]$Width = 16,
    [int]$Height = 16,
    [int]$Scale = 16
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$apicDir = Split-Path -Parent $scriptDir
$inputFull = Join-Path $apicDir $InputPath
$outputFull = Join-Path $apicDir $OutputPath

if (-not (Test-Path $inputFull)) {
    throw "Input file not found: $inputFull"
}

$widthInt = [int]($Width | Select-Object -First 1)
$heightInt = [int]($Height | Select-Object -First 1)
$scaleInt = [int]($Scale | Select-Object -First 1)

if ($widthInt -is [array]) { $widthInt = [int]$widthInt[0] }
if ($heightInt -is [array]) { $heightInt = [int]$heightInt[0] }
if ($scaleInt -is [array]) { $scaleInt = [int]$scaleInt[0] }

$values = Get-Content $inputFull | Where-Object { $_.Trim().Length -gt 0 } | ForEach-Object {
    $raw = $_.Trim()
    $val = [Convert]::ToInt32($raw, 16)
    if ($val -ge 0x80) {
        $val -= 0x100
    }
    $val
}

if ($values.Count -ne ($widthInt * $heightInt)) {
    throw "Expected $($widthInt * $heightInt) values, got $($values.Count)"
}

Add-Type -AssemblyName System.Drawing

$bmp = New-Object -TypeName System.Drawing.Bitmap -ArgumentList $widthInt, $heightInt
for ($y = 0; $y -lt $heightInt; $y++) {
    for ($x = 0; $x -lt $widthInt; $x++) {
        $idx = ($y * $widthInt) + $x
        $v = $values[$idx] + 128
        if ($v -lt 0) { $v = 0 }
        if ($v -gt 255) { $v = 255 }
        $color = [System.Drawing.Color]::FromArgb($v, $v, $v)
        $bmp.SetPixel($x, $y, $color)
    }
}

if ($scaleInt -gt 1) {
    $scaledWidth = $widthInt * $scaleInt
    $scaledHeight = $heightInt * $scaleInt
    $scaled = New-Object -TypeName System.Drawing.Bitmap -ArgumentList $scaledWidth, $scaledHeight
    $g = [System.Drawing.Graphics]::FromImage($scaled)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::Half
    $g.DrawImage($bmp, 0, 0, $scaledWidth, $scaledHeight)
    $g.Dispose()
    $bmp.Dispose()
    $bmp = $scaled
}

$outDir = Split-Path -Parent $outputFull
if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

$bmp.Save($outputFull, [System.Drawing.Imaging.ImageFormat]::Jpeg)
$bmp.Dispose()

Write-Host "Wrote $outputFull"
