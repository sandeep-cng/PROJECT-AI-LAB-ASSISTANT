@echo off
setlocal enabledelayedexpansion
set "PATH=C:\Users\sandeep agrawal\.mingit\cmd;C:\Users\sandeep agrawal\AppData\Local\Microsoft\WinGet\Packages\GitHub.cli_Microsoft.Winget.Source_8wekyb3d8bbwe\bin;%PATH%"

echo ========================================================
echo   Pushing Project AI Lab to GitHub:
echo   https://github.com/sandeep-cng/PROJECT-AI-LAB-ASSISTANT
echo ========================================================
echo.

rem 1. Check if logged in with GitHub CLI
"C:\Users\sandeep agrawal\AppData\Local\Microsoft\WinGet\Packages\GitHub.cli_Microsoft.Winget.Source_8wekyb3d8bbwe\bin\gh.exe" auth status >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [1/2] Connecting to GitHub via GitHub CLI...
    echo An authorization code will appear and a browser will open.
    echo.
    "C:\Users\sandeep agrawal\AppData\Local\Microsoft\WinGet\Packages\GitHub.cli_Microsoft.Winget.Source_8wekyb3d8bbwe\bin\gh.exe" auth login --web -h github.com -p https
)

echo.
echo [2/2] Pushing code to https://github.com/sandeep-cng/PROJECT-AI-LAB-ASSISTANT ...
"C:\Users\sandeep agrawal\.mingit\cmd\git.exe" push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo   SUCCESS! All code has been pushed to GitHub:
    echo   https://github.com/sandeep-cng/PROJECT-AI-LAB-ASSISTANT
    echo ========================================================
) else (
    echo.
    echo If GitHub web login did not complete, you can use a Personal Access Token (PAT).
    set /p GITHUB_PAT="Paste your GitHub Personal Access Token (or press Enter to cancel): "
    if defined GITHUB_PAT (
        "C:\Users\sandeep agrawal\.mingit\cmd\git.exe" push https://!GITHUB_PAT!@github.com/sandeep-cng/PROJECT-AI-LAB-ASSISTANT.git main
    )
)

echo.
pause
