<#
.SYNOPSIS
  Genera el esqueleto y/o ejecuta las pruebas usando la instalacion real de Blender.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\run.ps1                 # genera + prueba
  powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Task Generate
  powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Task Test
  powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Height 1.85 -Set thigh=0.25
  powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Task Generate -Pose shoulder.abduction=35,elbow.flexion=20
  powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Task Generate -Neutral
  Variable opcional ANATOMICAL_BLENDER = ruta completa a blender.exe

  Codigo de salida: 0 todo bien; distinto de 0 si algo falla.
  (Archivo solo ASCII a proposito: PowerShell 5.1 lee mal UTF-8 sin BOM.)
#>
param(
    [ValidateSet('All', 'Generate', 'Anatomy', 'Test')][string]$Task = 'All',
    [double]$Height = 0,
    [string[]]$Set = @(),
    [string[]]$Pose = @(),
    [switch]$Neutral,
    [switch]$NoPreview
)

$ErrorActionPreference = 'Stop'
# Con "powershell -File" una lista con comas llega como UNA cadena: se separa a mano.
$Set  = @($Set  | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$Pose = @($Pose | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root 'logs'
$OutDir = Join-Path $Root 'output'
New-Item -ItemType Directory -Force -Path $LogDir, $OutDir | Out-Null

function Find-Blender {
    if ($env:ANATOMICAL_BLENDER -and (Test-Path $env:ANATOMICAL_BLENDER)) { return $env:ANATOMICAL_BLENDER }
    $cmd = Get-Command blender -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
    foreach ($r in $roots) {
        $found = Get-ChildItem (Join-Path $r 'Blender Foundation') -Directory -ErrorAction SilentlyContinue |
            Sort-Object { [version]($_.Name -replace '[^\d\.]', '') } -Descending |
            ForEach-Object { Join-Path $_.FullName 'blender.exe' } |
            Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($found) { return $found }
    }
    throw 'No se encontro Blender. Define $env:ANATOMICAL_BLENDER con la ruta de blender.exe'
}

function Invoke-Blender([string]$Name, [string[]]$BlenderArgs) {
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $log = Join-Path $LogDir "${Name}_$stamp.log"
    $err = "$log.err"
    # Start-Process no entrecomilla: hay que hacerlo a mano (la ruta puede tener espacios).
    $quoted = $BlenderArgs | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }
    $p = Start-Process -FilePath $script:Blender -ArgumentList $quoted -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $log -RedirectStandardError $err
    if ((Test-Path $err) -and (Get-Item $err).Length -gt 0) {
        Add-Content -Path $log -Value "`n--- stderr ---"
        Get-Content $err | Add-Content -Path $log
    }
    Remove-Item $err -ErrorAction SilentlyContinue
    Write-Host "[$Name] codigo de salida: $($p.ExitCode)   log: $log"
    Get-Content $log | Select-String -Pattern '^\[(OK|FAIL|INFO|WARNING|ERROR|SUMMARY)\]|^(OK|FAIL|ERROR|Ran )|Traceback|Error' |
        ForEach-Object { Write-Host "   $($_.Line)" }
    return $p.ExitCode
}

$Blender = Find-Blender
Write-Host "Blender: $Blender"
$exit = 0

if ($Task -in 'All', 'Generate') {
    $blend = Join-Path $OutDir 'skeleton_core.blend'
    $a = @('-b', '--factory-startup', '--python', (Join-Path $Root 'scripts\generate_skeleton.py'), '--', '--output', $blend)
    if ($Height -gt 0) { $a += @('--height', "$Height") }
    foreach ($s in $Set) { $a += @('--set', $s) }
    foreach ($p in $Pose) { $a += @('--pose', $p) }
    if ($Neutral) { $a += '--neutral' }
    if ($NoPreview) { $a += '--no-preview' }
    $code = Invoke-Blender 'generate' $a
    if ($code -ne 0) { $exit = $code } else {
        Write-Host "Resultado .blend : $blend"
        Write-Host "Reporte JSON     : $(Join-Path $OutDir 'skeleton_core_report.json')"
        if (-not $NoPreview) { Write-Host "Vistas previas   : $OutDir\preview_front.png , preview_side.png (pose) ; preview_neutral_front.png , preview_neutral_side.png (neutro)" }
    }
}

if ($Task -in 'All', 'Anatomy') {
    # Nivel 1 (anatomia sobre la base): archivo propio; no toca skeleton_core.blend
    $ablend = Join-Path $OutDir 'anatomy_level1.blend'
    $a = @('-b', '--factory-startup', '--python', (Join-Path $Root 'scripts\generate_anatomy.py'), '--', '--output', $ablend)
    if ($NoPreview) { $a += '--no-preview' }
    $code = Invoke-Blender 'anatomy' $a
    if ($code -ne 0) { if ($exit -eq 0) { $exit = $code } } else {
        Write-Host "Nivel 1 .blend   : $ablend"
        Write-Host "Reporte nivel 1  : $(Join-Path $OutDir 'anatomy_level1_report.json')"
        if (-not $NoPreview) { Write-Host "Vistas nivel 1   : $OutDir\anatomy_*.png (frente, lado, pelvis, torax, nivel 1 aislado, columna, mano, pie)" }
    }
}

if ($Task -in 'All', 'Test') {
    $a = @('-b', '--factory-startup', '--python', (Join-Path $Root 'tests\run_tests.py'))
    $code = Invoke-Blender 'tests' $a
    if ($code -ne 0 -and $exit -eq 0) { $exit = $code }
}

if ($exit -eq 0) { Write-Host 'RESULTADO FINAL: OK' -ForegroundColor Green } else { Write-Host "RESULTADO FINAL: FALLO (codigo $exit)" -ForegroundColor Red }
exit $exit
