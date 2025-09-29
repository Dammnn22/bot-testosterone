# Bot de Testosterona - Telegram

Bot de Telegram para estimación de niveles de testosterona basado en cuestionarios médicos ADAM y AMS.

## 🚀 Deploy Rápido

### 1. Configuración
```bash
# Copia el archivo de configuración
cp production.env .env

# Edita el archivo .env y agrega tu token del bot
# TELEGRAM_BOT_TOKEN=tu_token_aqui
```

### 2. Deploy con Docker
```bash
# Construir y ejecutar
docker-compose up -d

# Ver logs
docker-compose logs -f telegram-bot
```

### 3. Deploy Manual
```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar bot
python main.py
```

## 📋 Características

- ✅ Cuestionarios médicos ADAM y AMS
- ✅ Preguntas de estilo de vida
- ✅ Guardado automático de progreso
- ✅ Resultados detallados y orientativos
- ✅ Interfaz intuitiva con botones
- ✅ Solo funciona en chats privados

## ⚠️ Importante

Este bot es solo una herramienta orientativa. NO reemplaza un análisis de sangre ni una consulta médica profesional.

## 🔧 Archivos Principales

- `main.py` - Bot principal
- `config_manager.py` - Gestión de configuración
- `conversation_handler.py` - Manejo de conversaciones
- `error_handler.py` - Manejo de errores
- `logging_system.py` - Sistema de logs
- `security_manager.py` - Gestión de seguridad
- `persistence_manager.py` - Persistencia de datos

## 📁 Estructura de Producción

```
bot_testosterone/
├── main.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── production.env
├── config/
│   ├── production.env
│   └── telegram-bot.service
├── scripts/
│   ├── backup.sh
│   ├── install.sh
│   └── restore.sh
└── data/ (se crea automáticamente)
```
