# Configuración de Logo para el Bot de Testosterona
# Modifica esta variable para cambiar el logo en todo el bot

# Opciones de logo disponibles:
LOGOS = {
    "simple": "🧬 **BOT DE TESTOSTERONA** 🧬\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    "medico": "⚕️ **BOT DE TESTOSTERONA** ⚕️\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    "testosterona": "🧪 **BOT DE TESTOSTERONA** 🧪\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    "fuerza": "💪 **BOT DE TESTOSTERONA** 💪\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    "ascii_simple": """    ╔══════════════════════════════╗
    ║    🧬 BOT DE TESTOSTERONA 🧬   ║
    ║    Tu Asistente Médico Digital ║
    ╚══════════════════════════════╝""",
    "ascii_detallado": """    ┌─────────────────────────────────┐
    │  🧬 BOT DE TESTOSTERONA 🧬      │
    │  ─────────────────────────────  │
    │  Tu Asistente Médico Digital    │
    │  Evaluación de Testosterona     │
    └─────────────────────────────────┘""",
    "decorativo": """╔══════════════════════════════════════╗
║  🧬 **BOT DE TESTOSTERONA** 🧬        ║
║  ═══════════════════════════════════  ║
║  Tu Asistente Médico Digital         ║
╚══════════════════════════════════════╝""",
    "minimalista": "🧬 **TESTOSTERONA BOT** 🧬\n━━━━━━━━━━━━━━━━━━━━━━━━",
    "fondo": """┌─────────────────────────────────────┐
│  🧬 **BOT DE TESTOSTERONA** 🧬      │
│  ─────────────────────────────────  │
│  Evaluación Médica Digital         │
└─────────────────────────────────────┘""",
    "cientifico": """🔬 **BOT DE TESTOSTERONA** 🔬
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚗️ Análisis de Testosterona ⚗️"""
}

# Logo actual (cambia esta variable para cambiar el logo)
CURRENT_LOGO = "simple"

def get_logo():
    """Retorna el logo actual configurado"""
    return LOGOS.get(CURRENT_LOGO, LOGOS["simple"])

def get_logo_with_title(title=""):
    """Retorna el logo con un título opcional"""
    logo = get_logo()
    if title:
        return f"{logo}\n{title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    return logo

# Ejemplo de uso:
if __name__ == "__main__":
    print("Logo actual:")
    print(get_logo())
    print("\nLogo con título:")
    print(get_logo_with_title("RESULTADOS DE TU EVALUACIÓN"))
