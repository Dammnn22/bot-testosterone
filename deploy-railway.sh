#!/bin/bash

# Script de despliegue automático para Railway
# Uso: ./deploy-railway.sh

echo "🚀 Desplegando Bot de Testosterona en Railway..."

# Verificar que estamos en el directorio correcto
if [ ! -f "main.py" ]; then
    echo "❌ Error: No se encontró main.py. Ejecuta este script desde el directorio del bot."
    exit 1
fi

# Verificar que existe el token
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "⚠️  Advertencia: TELEGRAM_BOT_TOKEN no está configurado."
    echo "   Configúralo en Railway después del despliegue."
fi

# Verificar que git está configurado
if ! git config user.name > /dev/null 2>&1; then
    echo "❌ Error: Git no está configurado. Ejecuta:"
    echo "   git config --global user.name 'Tu Nombre'"
    echo "   git config --global user.email 'tu@email.com'"
    exit 1
fi

# Crear .gitignore si no existe
if [ ! -f ".gitignore" ]; then
    echo "📝 Creando .gitignore..."
    cat > .gitignore << EOF
# Variables de entorno
.env
.env.*
!.env.example

# Logs
*.log
logs/

# Datos del bot
data/
backups/

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
EOF
fi

# Verificar estado de git
if [ ! -d ".git" ]; then
    echo "📦 Inicializando repositorio Git..."
    git init
    git add .
    git commit -m "Bot de testosterona - configuración inicial"
else
    echo "📦 Actualizando repositorio Git..."
    git add .
    git commit -m "Actualización del bot - $(date '+%Y-%m-%d %H:%M:%S')" || echo "No hay cambios para commitear"
fi

echo "✅ Repositorio Git actualizado"

# Instrucciones para Railway
echo ""
echo "🎯 SIGUIENTES PASOS PARA RAILWAY:"
echo ""
echo "1. Ve a https://railway.app"
echo "2. Regístrate con GitHub"
echo "3. Click 'New Project' → 'Deploy from GitHub repo'"
echo "4. Selecciona tu repositorio"
echo "5. En Variables, agrega:"
echo "   - TELEGRAM_BOT_TOKEN = tu_token_del_bot"
echo "   - LOG_LEVEL = INFO"
echo "   - DEBUG_MODE = false"
echo ""
echo "6. ¡Tu bot estará funcionando en minutos! 🚀"
echo ""

# Verificar que el bot está listo
echo "🔍 Verificando configuración..."

# Verificar archivos necesarios
required_files=("main.py" "requirements.txt" "Dockerfile" "railway.json")
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file encontrado"
    else
        echo "❌ $file no encontrado"
    fi
done

# Verificar dependencias principales
if grep -q "python-telegram-bot" requirements.txt; then
    echo "✅ python-telegram-bot encontrado en requirements.txt"
else
    echo "❌ python-telegram-bot no encontrado en requirements.txt"
fi

echo ""
echo "🎉 ¡Configuración completada!"
echo "   Ahora sigue los pasos de Railway arriba para desplegar tu bot."
