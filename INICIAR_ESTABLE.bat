@echo off
setlocal
title EL ECO DEL VACIO - INTEGRADO PRO
cd /d "%~dp0"
if not exist "data" mkdir "data"
if not exist "backups" mkdir "backups"
echo ================================================================
echo          EL ECO DEL VACIO - INTEGRADO PRO
echo ================================================================
where py >nul 2>nul
if errorlevel 1 (echo ERROR: Python no disponible.&pause&exit /b 1)
if not exist ".venv\Scripts\python.exe" (
 py -m venv .venv
 if errorlevel 1 (echo ERROR creando entorno virtual.&pause&exit /b 1)
)
call ".venv\Scripts\activate.bat"
if errorlevel 1 (echo ERROR activando entorno virtual.&pause&exit /b 1)
python -m pip install --upgrade pip
if errorlevel 1 (echo ERROR actualizando pip.&pause&exit /b 1)
pip install -r requirements.txt
if errorlevel 1 (echo ERROR instalando dependencias. No se inicia el bot.&pause&exit /b 1)
python -c "import discord,yt_dlp,imageio_ffmpeg,nacl; print('Dependencias OK')"
if errorlevel 1 (echo ERROR verificando dependencias.&pause&exit /b 1)
if "%DISCORD_TOKEN%"=="" set /p DISCORD_TOKEN=Pega tu TOKEN privado y pulsa ENTER: 
if "%DISCORD_TOKEN%"=="" (echo ERROR: token vacio.&pause&exit /b 1)
:restart
python main.py
if errorlevel 1 (
 echo.
 echo El bot se cerro con error. Revisa el mensaje de arriba.
 echo Reinicio de seguridad en 8 segundos...
 timeout /t 8 /nobreak >nul
 goto restart
)
echo Bot cerrado normalmente.
pause
