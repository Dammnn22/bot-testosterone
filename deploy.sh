#!/bin/bash

# Script de Deploy para Bot de Testosterona
# Uso: ./deploy.sh

echo "🚀 Iniciando deploy del Bot de Testosterona..."

# Verificar que existe el archivo .env
if [ ! -f ".env" ]; then
    echo "⚠️  Archivo .env no encontrado. Copiando desde production.env..."
    cp production.env .env
    echo "📝 Por favor, edita el archivo .env y agrega tu token del bot:"
    echo "   TELEGRAM_BOT_TOKEN=tu_token_aqui"
    echo ""
    echo "Después de editar el archivo, ejecuta este script nuevamente."
    exit 1
fi

# Verificar que el token está configurado
if grep -q "your_production_bot_token_here" .env; then
    echo "❌ Error: Debes configurar tu token del bot en el archivo .env"
    echo "   Edita el archivo .env y reemplaza 'your_production_bot_token_here' con tu token real"
    exit 1
fi

echo "✅ Configuración verificada"

# Crear directorios necesarios
echo "📁 Creando directorios necesarios..."
mkdir -p data logs backups

# Instalar dependencias
echo "📦 Instalando dependencias..."
pip install -r requirements.txt

# Verificar que el bot se puede importar
echo "🔍 Verificando que el bot funciona..."
python -c "import main; print('✅ Bot verificado correctamente')"

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 ¡Deploy completado exitosamente!"
    echo ""
    echo "Para ejecutar el bot:"
    echo "  python main.py"
    echo ""
    echo "O con Docker:"
    echo "  docker-compose up -d"
    echo ""
    echo "Para ver logs:"
    echo "  docker-compose logs -f telegram-bot"
else
    echo "❌ Error: El bot no se pudo verificar correctamente"
    exit 1
fi
