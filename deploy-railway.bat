@echo off
REM Script de despliegue automático para Railway (Windows)
REM Uso: deploy-railway.bat

echo 🚀 Desplegando Bot de Testosterona en Railway...

REM Verificar que estamos en el directorio correcto
if not exist "main.py" (
    echo ❌ Error: No se encontró main.py. Ejecuta este script desde el directorio del bot.
    pause
    exit /b 1
)

REM Verificar que git está instalado
git --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Git no está instalado. Descárgalo de https://git-scm.com/
    pause
    exit /b 1
)

REM Crear .gitignore si no existe
if not exist ".gitignore" (
    echo 📝 Creando .gitignore...
    (
        echo # Variables de entorno
        echo .env
        echo .env.*
        echo !.env.example
        echo.
        echo # Logs
        echo *.log
        echo logs/
        echo.
        echo # Datos del bot
        echo data/
        echo backups/
        echo.
        echo # Python
        echo __pycache__/
        echo *.pyc
        echo *.pyo
        echo *.pyd
        echo .Python
        echo env/
        echo venv/
        echo .venv/
        echo.
        echo # IDE
        echo .vscode/
        echo .idea/
        echo *.swp
        echo *.swo
        echo.
        echo # OS
        echo .DS_Store
        echo Thumbs.db
    ) > .gitignore
)

REM Verificar estado de git
if not exist ".git" (
    echo 📦 Inicializando repositorio Git...
    git init
    git add .
    git commit -m "Bot de testosterona - configuración inicial"
) else (
    echo 📦 Actualizando repositorio Git...
    git add .
    git commit -m "Actualización del bot - %date% %time%" 2>nul || echo No hay cambios para commitear
)

echo ✅ Repositorio Git actualizado

REM Instrucciones para Railway
echo.
echo 🎯 SIGUIENTES PASOS PARA RAILWAY:
echo.
echo 1. Ve a https://railway.app
echo 2. Regístrate con GitHub
echo 3. Click 'New Project' → 'Deploy from GitHub repo'
echo 4. Selecciona tu repositorio
echo 5. En Variables, agrega:
echo    - TELEGRAM_BOT_TOKEN = tu_token_del_bot
echo    - LOG_LEVEL = INFO
echo    - DEBUG_MODE = false
echo.
echo 6. ¡Tu bot estará funcionando en minutos! 🚀
echo.

REM Verificar archivos necesarios
echo 🔍 Verificando configuración...

if exist "main.py" (
    echo ✅ main.py encontrado
) else (
    echo ❌ main.py no encontrado
)

if exist "requirements.txt" (
    echo ✅ requirements.txt encontrado
) else (
    echo ❌ requirements.txt no encontrado
)

if exist "Dockerfile" (
    echo ✅ Dockerfile encontrado
) else (
    echo ❌ Dockerfile no encontrado
)

if exist "railway.json" (
    echo ✅ railway.json encontrado
) else (
    echo ❌ railway.json no encontrado
)

echo.
echo 🎉 ¡Configuración completada!
echo    Ahora sigue los pasos de Railway arriba para desplegar tu bot.
echo.
pause
