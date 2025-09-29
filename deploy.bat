@echo off
REM Script de Deploy para Bot de Testosterona (Windows)
REM Uso: deploy.bat

echo 🚀 Iniciando deploy del Bot de Testosterona...

REM Verificar que existe el archivo .env
if not exist ".env" (
    echo ⚠️  Archivo .env no encontrado. Copiando desde production.env...
    copy production.env .env
    echo 📝 Por favor, edita el archivo .env y agrega tu token del bot:
    echo    TELEGRAM_BOT_TOKEN=tu_token_aqui
    echo.
    echo Después de editar el archivo, ejecuta este script nuevamente.
    pause
    exit /b 1
)

REM Verificar que el token está configurado
findstr /C:"your_production_bot_token_here" .env >nul
if %errorlevel% equ 0 (
    echo ❌ Error: Debes configurar tu token del bot en el archivo .env
    echo    Edita el archivo .env y reemplaza 'your_production_bot_token_here' con tu token real
    pause
    exit /b 1
)

echo ✅ Configuración verificada

REM Crear directorios necesarios
echo 📁 Creando directorios necesarios...
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "backups" mkdir backups

REM Instalar dependencias
echo 📦 Instalando dependencias...
pip install -r requirements.txt

REM Verificar que el bot se puede importar
echo 🔍 Verificando que el bot funciona...
python -c "import main; print('✅ Bot verificado correctamente')"

if %errorlevel% equ 0 (
    echo.
    echo 🎉 ¡Deploy completado exitosamente!
    echo.
    echo Para ejecutar el bot:
    echo   python main.py
    echo.
    echo O con Docker:
    echo   docker-compose up -d
    echo.
    echo Para ver logs:
    echo   docker-compose logs -f telegram-bot
) else (
    echo ❌ Error: El bot no se pudo verificar correctamente
    pause
    exit /b 1
)

pause
