# 🚀 Guía de Despliegue Gratuito - Bot de Testosterona

## Opciones Gratuitas para Alojar tu Bot 24/7

### 1. Railway (⭐ RECOMENDADO)

**Ventajas:**
- ✅ 500 horas gratuitas por mes (suficiente para 24/7)
- ✅ Despliegue automático desde GitHub
- ✅ No necesitas configurar servidor
- ✅ Incluye base de datos y logs
- ✅ Reinicio automático si falla

**Pasos para desplegar:**

1. **Crear cuenta en Railway:**
   - Ve a [railway.app](https://railway.app)
   - Regístrate con GitHub

2. **Subir tu código a GitHub:**
   ```bash
   # Si no tienes repositorio
   git init
   git add .
   git commit -m "Bot de testosterona listo para producción"
   git branch -M main
   git remote add origin https://github.com/tu-usuario/bot-testosterona.git
   git push -u origin main
   ```

3. **Desplegar en Railway:**
   - En Railway, click "New Project"
   - Selecciona "Deploy from GitHub repo"
   - Elige tu repositorio
   - Railway detectará automáticamente que es un bot de Python

4. **Configurar variables de entorno:**
   - En Railway, ve a tu proyecto
   - Click en "Variables"
   - Agrega: `TELEGRAM_BOT_TOKEN` = tu_token_del_bot
   - Agrega: `LOG_LEVEL` = INFO
   - Agrega: `DEBUG_MODE` = false

5. **¡Listo!** Tu bot estará funcionando 24/7

---

### 2. Render (Alternativa)

**Ventajas:**
- ✅ 750 horas gratuitas por mes
- ✅ Muy fácil de usar
- ⚠️ Se duerme después de 15 min de inactividad (se despierta automáticamente)

**Pasos:**

1. **Crear cuenta en Render:**
   - Ve a [render.com](https://render.com)
   - Regístrate con GitHub

2. **Crear nuevo servicio:**
   - Click "New +" → "Web Service"
   - Conecta tu repositorio de GitHub
   - Configura:
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `python main.py`
     - **Environment:** Python 3

3. **Configurar variables:**
   - En "Environment Variables"
   - Agrega `TELEGRAM_BOT_TOKEN`

---

### 3. Oracle Cloud (VPS Gratuito)

**Ventajas:**
- ✅ Siempre gratuito (nunca expira)
- ✅ 1GB RAM, 1 CPU
- ✅ Control total del servidor

**Requisitos:**
- Tarjeta de crédito (no se cobra, solo verificación)
- Documento de identidad

**Pasos:**

1. **Crear cuenta en Oracle Cloud:**
   - Ve a [oracle.com/cloud/free](https://oracle.com/cloud/free)
   - Regístrate (necesitas tarjeta de crédito)

2. **Crear instancia:**
   - Ve a "Compute" → "Instances"
   - Click "Create Instance"
   - Selecciona "Always Free" shape
   - Elige Ubuntu 20.04 o 22.04
   - Genera/descarga las llaves SSH

3. **Conectar al servidor:**
   ```bash
   ssh -i tu-llave.pem ubuntu@IP_DEL_SERVIDOR
   ```

4. **Instalar dependencias:**
   ```bash
   # Actualizar sistema
   sudo apt update && sudo apt upgrade -y
   
   # Instalar Python y pip
   sudo apt install python3 python3-pip git -y
   
   # Instalar Docker (opcional, más fácil)
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker ubuntu
   ```

5. **Desplegar el bot:**
   ```bash
   # Clonar tu repositorio
   git clone https://github.com/tu-usuario/bot-testosterona.git
   cd bot-testosterona
   
   # Instalar dependencias
   pip3 install -r requirements.txt
   
   # Configurar variables de entorno
   export TELEGRAM_BOT_TOKEN="tu_token_aqui"
   export LOG_LEVEL="INFO"
   export DEBUG_MODE="false"
   
   # Ejecutar en background
   nohup python3 main.py > bot.log 2>&1 &
   ```

6. **Configurar para que se ejecute automáticamente:**
   ```bash
   # Crear servicio systemd
   sudo nano /etc/systemd/system/telegram-bot.service
   ```

   Contenido del archivo:
   ```ini
   [Unit]
   Description=Telegram Bot
   After=network.target

   [Service]
   Type=simple
   User=ubuntu
   WorkingDirectory=/home/ubuntu/bot-testosterona
   Environment=TELEGRAM_BOT_TOKEN=tu_token_aqui
   Environment=LOG_LEVEL=INFO
   Environment=DEBUG_MODE=false
   ExecStart=/usr/bin/python3 main.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   # Activar el servicio
   sudo systemctl daemon-reload
   sudo systemctl enable telegram-bot
   sudo systemctl start telegram-bot
   sudo systemctl status telegram-bot
   ```

---

## 🔧 Configuración Adicional

### Variables de Entorno Necesarias

```env
TELEGRAM_BOT_TOKEN=tu_token_del_botfather
LOG_LEVEL=INFO
DEBUG_MODE=false
RATE_LIMIT_PER_MINUTE=10
MAX_RETRIES=3
TIMEOUT_MINUTES=30
```

### Monitoreo del Bot

**Verificar que funciona:**
```bash
# En Railway/Render: ver logs en el dashboard
# En VPS:
sudo systemctl status telegram-bot
tail -f /home/ubuntu/bot-testosterona/bot.log
```

**Comandos útiles:**
```bash
# Reiniciar bot
sudo systemctl restart telegram-bot

# Ver logs en tiempo real
sudo journalctl -u telegram-bot -f

# Verificar que el bot responde
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe"
```

---

## 🎯 Recomendación Final

**Para empezar rápido:** Usa **Railway**
- Es la opción más fácil
- No necesitas conocimientos de servidores
- Despliegue en 5 minutos
- 500 horas gratuitas son suficientes para 24/7

**Para control total:** Usa **Oracle Cloud**
- Siempre gratuito
- Aprendes sobre servidores
- Más control sobre la configuración

---

## 🆘 Solución de Problemas

### Bot no responde
1. Verifica que el token sea correcto
2. Revisa los logs de errores
3. Asegúrate de que el bot esté activo en @BotFather

### Errores de permisos (VPS)
```bash
sudo chown -R ubuntu:ubuntu /home/ubuntu/bot-testosterona
chmod +x main.py
```

### Bot se desconecta
- Railway/Render: Se reinicia automáticamente
- VPS: Verifica que el servicio esté habilitado

---

## 📞 Soporte

Si tienes problemas:
1. Revisa los logs de errores
2. Verifica la configuración de variables de entorno
3. Asegúrate de que el token del bot sea válido
4. En Railway/Render: revisa el dashboard de logs

¡Tu bot estará funcionando 24/7 en pocos minutos! 🚀
