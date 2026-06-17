Set-Location $PSScriptRoot\..
Write-Host "挖词看板: http://localhost:8080/viewer/" -ForegroundColor Cyan
python -m http.server 8080
