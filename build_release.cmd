@echo off
setlocal
cd /d "%~dp0"

if not exist ".release-venv\Scripts\python.exe" python -m venv .release-venv
if errorlevel 1 exit /b %errorlevel%

.release-venv\Scripts\python.exe -m pip install --upgrade pip
.release-venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b %errorlevel%

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
.release-venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --name "mspy-dat-mgr" --paths . main.py
if errorlevel 1 exit /b %errorlevel%

copy /y README.txt "dist\mspy-dat-mgr\README.txt" >nul
powershell -NoProfile -Command "Compress-Archive -Path 'dist\mspy-dat-mgr' -DestinationPath 'dist\mspy-dat-mgr-v0.1.0-windows-x64.zip' -Force"
if errorlevel 1 exit /b %errorlevel%

echo.
echo Release package created:
echo %cd%\dist\mspy-dat-mgr-v0.1.0-windows-x64.zip
