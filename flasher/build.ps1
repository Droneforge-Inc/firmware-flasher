$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($env:PYTHON_BIN) {
    $PythonCmd = $env:PYTHON_BIN
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
} else {
    throw "Python not found. Set PYTHON_BIN or install Python."
}

if ($PythonCmd -eq "py") {
    & py -3 (Join-Path $RootDir "build.py") @args
} else {
    & $PythonCmd (Join-Path $RootDir "build.py") @args
}
