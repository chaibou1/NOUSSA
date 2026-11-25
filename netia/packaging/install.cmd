@echo off
rem Installe NetIA sur Windows (sans Python).
rem   curl -fsSLo %TEMP%\netia-install.cmd https://github.com/chaibou1/NOUSSA/releases/latest/download/install.cmd && %TEMP%\netia-install.cmd
setlocal
set "DEST=%LOCALAPPDATA%\Programs\netia"
set "URL=https://github.com/chaibou1/NOUSSA/releases/latest/download/netia_windows_x64.exe"

if not exist "%DEST%" mkdir "%DEST%"
echo Telechargement de NetIA...
curl -fL --progress-bar -o "%DEST%\netia.exe" "%URL%"
if errorlevel 1 (
    echo Echec du telechargement. Verifie ta connexion Internet.
    exit /b 1
)

rem Ajoute le dossier au PATH de l'utilisateur (sans toucher au PATH systeme).
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=$env:DEST; $p=[Environment]::GetEnvironmentVariable('Path','User'); if (-not $p) {$p=''}; if (($p -split ';') -notcontains $d) { [Environment]::SetEnvironmentVariable('Path', (($p.TrimEnd(';') + ';' + $d).TrimStart(';')), 'User'); Write-Host 'Dossier ajoute au PATH.' }"

echo.
echo NetIA est installe dans %DEST%
echo Ferme cette fenetre, ouvre un NOUVEAU cmd et tape : netia
echo Desinstaller : supprime le dossier %DEST%
endlocal
