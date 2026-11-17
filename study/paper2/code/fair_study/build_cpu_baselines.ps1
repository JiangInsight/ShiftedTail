param([switch]$AllQueries)
$ErrorActionPreference = 'Stop'
$entry = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../../reproduce.py'))
if ($env:PAPER2_WORK) {
    & python $entry --work $env:PAPER2_WORK build
} else {
    & python $entry build
}
if ($LASTEXITCODE) { throw 'CPU baseline build failed' }
