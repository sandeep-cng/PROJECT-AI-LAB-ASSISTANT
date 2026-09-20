$ErrorActionPreference = "Continue"

$gitDir = "C:\Users\sandeep agrawal\.mingit\cmd"
$ghDir = "C:\Users\sandeep agrawal\AppData\Local\Microsoft\WinGet\Packages\GitHub.cli_Microsoft.Winget.Source_8wekyb3d8bbwe\bin"
$env:Path = "$gitDir;$ghDir;$env:Path"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Pushing Project AI Lab to GitHub:" -ForegroundColor Cyan
Write-Host "  https://github.com/sandeep-cng/PROJECT-AI-LAB-ASSISTANT" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$ghStatus = & "$ghDir\gh.exe" auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[1/2] Connecting to GitHub via GitHub CLI..." -ForegroundColor Green
    Write-Host "A one-time device code will appear below, and a browser window will open." -ForegroundColor Gray
    Write-Host ""
    & "$ghDir\gh.exe" auth login --web -h github.com -p https
}

Write-Host ""
Write-Host "[2/2] Pushing main branch to GitHub..." -ForegroundColor Green
& "$gitDir\git.exe" push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host "  SUCCESS! All code has been pushed to GitHub:" -ForegroundColor Green
    Write-Host "  https://github.com/sandeep-cng/PROJECT-AI-LAB-ASSISTANT" -ForegroundColor Cyan
    Write-Host "========================================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "If web login did not finish, you can provide a GitHub Personal Access Token (PAT):" -ForegroundColor Yellow
    $pat = Read-Host -Prompt "Enter GitHub PAT (or press Enter to cancel)"
    if ($pat) {
        & "$gitDir\git.exe" push "https://$($pat)@github.com/sandeep-cng/PROJECT-AI-LAB-ASSISTANT.git" main
    }
}
