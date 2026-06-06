$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path -LiteralPath $bundledPython) {
    $python = $bundledPython
} else {
    $python = "python"
}

& $python -m pip install -e .

$url = "http://127.0.0.1:5000"
Start-Process $url
& $python -m auto_order_splitting.web_app --host 127.0.0.1 --port 5000
