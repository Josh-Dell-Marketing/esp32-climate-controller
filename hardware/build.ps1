# Rebuilds the whole KiCad project from hardware/gen/design.py and checks it.
#   powershell -ExecutionPolicy Bypass -File hardware\build.ps1            (design + checks)
#   powershell -ExecutionPolicy Bypass -File hardware\build.ps1 -Fab      (also Gerbers, drill, BOM, PDFs, STEP)
param([switch]$Fab)
$ErrorActionPreference = "Continue"   # kicad-cli prints warnings on stderr; exit codes are checked instead
$hw = $PSScriptRoot
$kc = "C:\Program Files\KiCad\10.0\bin"
$py = "$kc\python.exe"
$cli = "$kc\kicad-cli.exe"
$name = "climate-controller"
$sch = "$hw\$name.kicad_sch"
$pcb = "$hw\$name.kicad_pcb"
$out = "$hw\build"
New-Item -ItemType Directory -Force "$out\img" | Out-Null

Push-Location "$hw\gen"
try {
    & $py make_pro.py;  if ($LASTEXITCODE) { throw "make_pro failed" }
    & $py make_sch.py;  if ($LASTEXITCODE) { throw "make_sch failed" }
    & $cli sch upgrade $sch | Out-Null
    & $cli sch erc --severity-all --format json -o "$out\erc.json" $sch | Out-Null
    $erc = Get-Content "$out\erc.json" -Raw | ConvertFrom-Json
    $ercErr = @($erc.sheets.violations | Where-Object { $_.severity -eq "error" }).Count
    $ercWarn = @($erc.sheets.violations | Where-Object { $_.severity -eq "warning" }).Count
    Write-Host "ERC: $ercErr errors, $ercWarn warnings"

    & $py make_pcb.py;  if ($LASTEXITCODE) { throw "make_pcb failed (unrouted nets?)" }
    & $cli pcb drc --schematic-parity --refill-zones --save-board --severity-all --format json -o "$out\drc.json" $pcb | Out-Null
    $drc = Get-Content "$out\drc.json" -Raw | ConvertFrom-Json
    $drcErr = @($drc.violations | Where-Object { $_.severity -eq "error" }).Count
    $drcWarn = @($drc.violations | Where-Object { $_.severity -eq "warning" }).Count
    Write-Host "DRC: $drcErr errors, $drcWarn warnings, $(@($drc.unconnected_items).Count) unconnected, $(@($drc.schematic_parity).Count) parity issues"
    $drc.violations | Where-Object { $_.severity -eq "error" } | ForEach-Object {
        Write-Host "  $($_.type): $($_.description)"; $_.items | ForEach-Object { Write-Host "      $($_.description)" } }

    & $cli pcb render --side top --quality high --width 1600 --height 1530 -o "$out\img\top.png" $pcb | Out-Null
    & $cli pcb render --side bottom --quality high --width 1600 --height 1530 -o "$out\img\bottom.png" $pcb | Out-Null
    & $cli pcb render --side top --rotate "-45,0,20" --quality high --width 1600 --height 1200 -o "$out\img\iso.png" $pcb | Out-Null
    & $cli sch export svg -o "$out\img" $sch | Out-Null
    & $cli pcb export svg --layers "F.Cu,F.SilkS,Edge.Cuts" --mode-single --fit-page-to-board -o "$out\img\copper_top.svg" $pcb | Out-Null
    & $cli pcb export svg --layers "B.Cu,B.SilkS,Edge.Cuts" --mode-single --mirror --fit-page-to-board -o "$out\img\copper_bottom.svg" $pcb | Out-Null

    if ($Fab) {
        $fabDir = "$out\fab"
        New-Item -ItemType Directory -Force "$fabDir\gerbers" | Out-Null
        & $cli pcb export gerbers --layers "F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" -o "$fabDir\gerbers" $pcb | Out-Null
        & $cli pcb export drill --format excellon --excellon-separate-th -o "$fabDir/gerbers/" $pcb | Out-Null
        Compress-Archive -Path "$fabDir\gerbers\*" -DestinationPath "$fabDir\$name-gerbers.zip" -Force
        & $cli sch export bom --fields "Reference,Value,Footprint,`${QUANTITY}" --labels "Refs,Value,Footprint,Qty" --group-by "Value,Footprint" -o "$fabDir\$name-bom.csv" $sch | Out-Null
        & $cli sch export pdf -o "$fabDir\$name-schematic.pdf" $sch | Out-Null
        & $cli pcb export pdf --layers "F.Cu,F.SilkS,Edge.Cuts" --mode-single -o "$fabDir\$name-pcb-top.pdf" $pcb | Out-Null
        & $cli pcb export step --subst-models --force -o "$fabDir\$name.step" $pcb 2>&1 | Out-Null
        if (-not (Test-Path "$fabDir\$name.step")) { Write-Host "STEP export failed" }
        Write-Host "Fabrication files in $fabDir"
    }
}
finally { Pop-Location }

# Exit code: 0 only when ERC and DRC have no errors and nothing is unconnected
if ($ercErr -or $drcErr -or @($drc.unconnected_items).Count -or @($drc.schematic_parity).Count) { exit 1 }
exit 0
