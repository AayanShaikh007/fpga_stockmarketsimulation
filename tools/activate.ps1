# Dot-source from PowerShell: . .\tools\activate.ps1
param([string]$SuitePath = 'C:\tools\oss-cad-suite')

$projectRoot = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path "$SuitePath\bin\iverilog.exe")) {
    throw "OSS CAD Suite not found at $SuitePath. Supply -SuitePath with its location."
}
if (-not (Test-Path "$projectRoot\.venv\Scripts\python.exe")) {
    throw 'Create the project environment first: python -m venv .venv'
}
$env:PATH = "$projectRoot\.venv\Scripts;$SuitePath\bin;$SuitePath\lib;$env:PATH"
Write-Host 'NanoQuant Python and FPGA tools are ready in this terminal.'
