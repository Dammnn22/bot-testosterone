# -*- coding: utf-8 -*-

"""
Bot de Telegram para una estimación de niveles de testosterona.
Utiliza cuestionarios médicos ADAM y AMS, además de factores de estilo de vida.
"""

import logging
import sys
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from config_manager import ConfigManager, ConfigurationError
from logging_system import LoggingSystem
from error_handler import ErrorHandler, ErrorContext, ErrorType
from conversation_handler import EnhancedConversationHandler, ConversationState

# Global instances (will be initialized in main)
logging_system = None
error_handler = None
conversation_handler = None
logger = logging.getLogger(__name__)

# --- Definición de Estados para la Conversación ---
# Usamos números para definir cada paso del flujo de la conversación.
(
    STATE_START,
    STATE_ADAM,
    STATE_AMS,
    STATE_LIFESTYLE,
    STATE_RESULTS,
) = range(5)

# --- Preguntas de los Cuestionarios ---

# Cuestionario ADAM (Androgen Deficiency in Aging Males)
ADAM_QUESTIONS = [
    "1/10: ¿Ha disminuido su libido (deseo sexual)?",
    "2/10: ¿Siente una falta de energía?",
    "3/10: ¿Ha perdido fuerza o resistencia?",
    "4/10: ¿Ha perdido estatura?",
    "5/10: ¿Ha notado una disminución en su 'disfrute de la vida'?",
    "6/10: ¿Está triste o de mal humor?",
    "7/10: ¿Son sus erecciones menos fuertes?",
    "8/10: ¿Ha notado un deterioro reciente en su capacidad para practicar deportes?",
    "9/10: ¿Se queda dormido después de cenar?",
    "10/10: ¿Ha disminuido recientemente su rendimiento en el trabajo?",
]

# Cuestionario AMS (Aging Male's Symptoms)
AMS_QUESTIONS = [
    "1/17: Disminución del deseo/apetito sexual.",
    "2/17: Sensación de agotamiento físico/falta de vitalidad.",
    "3/17: Disminución de la fuerza muscular.",
    "4/17: Dificultad para conciliar el sueño.",
    "5/17: Necesidad de dormir más que antes.",
    "6/17: Aumento de la irritabilidad.",
    "7/17: Aumento del nerviosismo.",
    "8/17: Ansiedad (sentirse al límite).",
    "9/17: Episodios de sudoración.",
    "10/17: Pérdida de vello corporal.",
    "11/17: Disminución de la barba.",
    "12/17: Disminución de la potencia/frecuencia de las erecciones matutinas.",
    "13/17: Disminución de la capacidad para el rendimiento sexual.",
    "14/17: Dolores articulares y musculares.",
    "15/17: Sensación de que 'ya ha pasado lo mejor'.",
    "16/17: Sensación de estar 'quemado', de haber llegado al límite.",
    "17/17: Tristeza o desánimo.",
]

# Preguntas sobre Estilo de Vida
LIFESTYLE_QUESTIONS = [
    "1/6: ¿Cuál es tu edad?",
    "2/6: ¿Cuál es tu porcentaje de grasa corporal aproximado? (Si no lo sabes, introduce un estimado. Ej: 15)",
    "3/6: En una escala de 1 a 5, ¿cómo calificarías la calidad de tu sueño? (1=Muy mala, 5=Excelente)",
    "4/6: En una escala de 1 a 5, ¿cómo calificarías tu nivel de estrés diario? (1=Muy bajo, 5=Muy alto)",
    "5/6: ¿Cuántas veces por semana realizas ejercicio de fuerza (pesas, calistenia, etc.)?",
    "6/6: ¿Consumes alcohol o tabaco de forma regular?",
]


# --- Funciones del Bot ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Inicia la conversación. Se activa con /start.
    Saluda y pregunta al usuario si quiere comenzar el cuestionario.
    """
    user_id = update.effective_user.id if update.effective_user else None
    
    try:
        # Log user action
        if logging_system:
            logging_system.log_user_action(user_id, "start_conversation")
        
        # Importante: El bot solo funciona en chats privados para proteger la privacidad.
        if update.message.chat.type != 'private':
            message = "Para proteger tu privacidad, solo respondo en chats privados. Por favor, envíame /start en un chat conmigo."
            if error_handler:
                await error_handler.safe_send_message(update, context, message)
            else:
                await update.message.reply_text(message)
            return ConversationHandler.END

        # Check for existing progress and offer recovery
        if conversation_handler and conversation_handler.has_active_session(user_id):
            recovery_message = conversation_handler.get_recovery_message(user_id)
            if recovery_message:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Continuar", callback_data="continue_yes"),
                        InlineKeyboardButton("🔄 Empezar de nuevo", callback_data="start_fresh"),
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                if error_handler:
                    await error_handler.safe_send_message(update, context, recovery_message, reply_markup=reply_markup)
                else:
                    await update.message.reply_text(recovery_message, reply_markup=reply_markup)
                
                return STATE_START

        keyboard = [
            [
                InlineKeyboardButton("✅ Sí, comenzar", callback_data="start_yes"),
                InlineKeyboardButton("❌ No, ahora no", callback_data="start_no"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            "🧬 **BOT DE TESTOSTERONA** 🧬\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Hola 👋 Soy tu asistente médico digital.\n\n"
            "Te haré una serie de preguntas basadas en cuestionarios médicos (ADAM + AMS) y sobre tu estilo de vida para darte una estimación de tu nivel de testosterona.\n\n"
            "⚠️ **Importante:** Esto NO reemplaza un análisis de sangre ni una consulta médica. Es solo una herramienta orientativa.\n\n"
            "¿Quieres comenzar?"
        )
        
        if error_handler:
            success = await error_handler.safe_send_message(update, context, message, reply_markup=reply_markup)
            if not success:
                # Fallback without markup
                await error_handler.safe_send_message(update, context, message)
        else:
            await update.message.reply_text(message, reply_markup=reply_markup)
        
        return STATE_START
        
    except Exception as e:
        if error_handler and logging_system:
            error_context = ErrorContext(
                user_id=user_id,
                chat_id=update.effective_chat.id if update.effective_chat else None,
                function_name="start"
            )
            recovery_action, user_message = await error_handler.handle_error(e, error_context)
            
            if user_message:
                await error_handler.safe_send_message(update, context, user_message)
        else:
            logger.error(f"Error in start function: {e}")
            
        return ConversationHandler.END


async def start_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Maneja la respuesta del botón 'Sí' o 'No' del inicio.
    """
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id if update.effective_user else None

    if query.data == "continue_yes":
        # User wants to continue from where they left off
        if conversation_handler:
            progress = conversation_handler.load_progress(user_id)
            if progress:
                # Restore context from saved progress
                conversation_handler.restore_context_from_progress(context, progress)
                
                # Show current progress
                progress_message = conversation_handler.show_progress(user_id)
                if progress_message:
                    await query.edit_message_text(text=progress_message)
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="Continuando desde donde lo dejaste..."
                    )
                
                # Return to the appropriate state
                if progress.current_state == ConversationState.ADAM:
                    current_question_index = len(progress.adam_answers)
                    if current_question_index < len(ADAM_QUESTIONS):
                        keyboard = [[InlineKeyboardButton("Sí", callback_data="adam_yes"), InlineKeyboardButton("No", callback_data="adam_no")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=ADAM_QUESTIONS[current_question_index],
                            reply_markup=reply_markup
                        )
                        return STATE_ADAM
                elif progress.current_state == ConversationState.AMS:
                    current_question_index = progress.ams_question_index
                    if current_question_index < len(AMS_QUESTIONS):
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=AMS_QUESTIONS[current_question_index]
                        )
                        return STATE_AMS
                elif progress.current_state == ConversationState.LIFESTYLE:
                    current_question_index = progress.lifestyle_question_index
                    if current_question_index < len(LIFESTYLE_QUESTIONS):
                        if current_question_index == 5:  # Last question with buttons
                            keyboard = [[InlineKeyboardButton("Sí", callback_data="ls_yes"), InlineKeyboardButton("No", callback_data="ls_no")]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=LIFESTYLE_QUESTIONS[current_question_index],
                                reply_markup=reply_markup
                            )
                        else:
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=LIFESTYLE_QUESTIONS[current_question_index]
                            )
                        return STATE_LIFESTYLE
        
        # Fallback to starting fresh if recovery fails
        query.data = "start_yes"
    
    if query.data == "start_fresh":
        # Clear existing progress and start fresh
        if conversation_handler:
            conversation_handler.clear_user_data(user_id)
        query.data = "start_yes"

    if query.data == "start_yes":
        # Inicializa las variables para guardar las respuestas del usuario.
        context.user_data["adam_answers"] = []
        context.user_data["ams_score"] = 0
        context.user_data["ams_question_index"] = 0
        context.user_data["lifestyle_answers"] = {}
        context.user_data["lifestyle_question_index"] = 0
        
        # Save initial progress
        if conversation_handler:
            conversation_handler.save_progress(user_id, ConversationState.ADAM, context.user_data)
        
        # Pregunta la primera del cuestionario ADAM
        keyboard = [[InlineKeyboardButton("Sí", callback_data="adam_yes"), InlineKeyboardButton("No", callback_data="adam_no")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text=ADAM_QUESTIONS[0], reply_markup=reply_markup)
        return STATE_ADAM
    else:
        await query.edit_message_text(text="Entendido. Si cambias de opinión, simplemente escribe /start. ¡Hasta luego!")
        return ConversationHandler.END


async def adam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Maneja las respuestas del cuestionario ADAM (Sí/No).
    """
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id if update.effective_user else None

    # Guarda la respuesta (True para Sí, False para No)
    context.user_data["adam_answers"].append(query.data == "adam_yes")
    
    # Save progress after each answer
    if conversation_handler:
        conversation_handler.save_progress(user_id, ConversationState.ADAM, context.user_data)
    
    current_question_index = len(context.user_data["adam_answers"])

    if current_question_index < len(ADAM_QUESTIONS):
        # Si quedan preguntas en ADAM, hace la siguiente.
        # Enhanced progress display with percentage and review option
        total_questions = len(ADAM_QUESTIONS) + len(AMS_QUESTIONS) + len(LIFESTYLE_QUESTIONS)
        overall_progress = (current_question_index / total_questions) * 100
        
        keyboard = [
            [InlineKeyboardButton("Sí", callback_data="adam_yes"), InlineKeyboardButton("No", callback_data="adam_no")],
            [InlineKeyboardButton("📝 Revisar respuesta anterior", callback_data="review_adam")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Enhanced progress display
        progress_bar = "█" * int(overall_progress / 10) + "░" * (10 - int(overall_progress / 10))
        progress_text = (
            f"📊 **Progreso General:** {int(overall_progress)}% [{progress_bar}]\n"
            f"📋 **Sección:** ADAM - Pregunta {current_question_index + 1} de {len(ADAM_QUESTIONS)}\n\n"
            f"{ADAM_QUESTIONS[current_question_index]}"
        )
        await query.edit_message_text(text=progress_text, reply_markup=reply_markup)
        return STATE_ADAM
    else:
        # Si ADAM terminó, empieza con AMS.
        # Initialize AMS tracking
        context.user_data["ams_question_index"] = 0
        
        # Save progress for AMS start
        if conversation_handler:
            conversation_handler.save_progress(user_id, ConversationState.AMS, context.user_data)
        
        # Show section completion with summary
        adam_yes_count = sum(context.user_data["adam_answers"])
        completion_message = (
            f"✅ **Cuestionario ADAM completado**\n"
            f"Respuestas 'Sí': {adam_yes_count}/10\n\n"
            f"Ahora, por favor, responde a las siguientes preguntas puntuando de 1 a 5, donde:\n"
            f"1 = Ninguno\n2 = Leve\n3 = Moderado\n4 = Severo\n5 = Muy severo"
        )
        await query.edit_message_text(text=completion_message)
        
        # Show progress in AMS question with enhanced display
        total_questions = len(ADAM_QUESTIONS) + len(AMS_QUESTIONS) + len(LIFESTYLE_QUESTIONS)
        overall_progress = (len(ADAM_QUESTIONS) / total_questions) * 100
        progress_bar = "█" * int(overall_progress / 10) + "░" * (10 - int(overall_progress / 10))
        
        progress_text = (
            f"📊 **Progreso General:** {int(overall_progress)}% [{progress_bar}]\n"
            f"📋 **Sección:** AMS - Pregunta 1 de {len(AMS_QUESTIONS)}\n\n"
            f"{AMS_QUESTIONS[0]}"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=progress_text)
        return STATE_AMS


async def ams_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Maneja las respuestas del cuestionario AMS (puntuación 1-5).
    """
    user_id = update.effective_user.id if update.effective_user else None
    user_input = update.message.text
    current_question_index = context.user_data.get("ams_question_index", 0)

    try:
        # Log user action
        if logging_system:
            logging_system.log_user_action(
                user_id, 
                "ams_response", 
                {"question_index": current_question_index, "response": user_input}
            )

        # Valida que la respuesta sea un número entre 1 y 5.
        try:
            score = int(user_input)
            if not 1 <= score <= 5:
                raise ValueError("Score out of range")
        except (ValueError, TypeError) as validation_error:
            # Enhanced error handling with user-friendly messages and review option
            keyboard = [[InlineKeyboardButton("📝 Revisar respuesta anterior", callback_data="review_ams")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            error_message = "Por favor, introduce un número válido entre 1 y 5."
            help_message = "Debe ser un número entero del 1 al 5, donde:\n1 = Ninguno\n2 = Leve\n3 = Moderado\n4 = Severo\n5 = Muy severo"
            
            if error_handler:
                await error_handler.safe_send_message(update, context, error_message)
                await error_handler.safe_send_message(update, context, help_message)
                
                # Enhanced progress display even for errors
                total_questions = len(ADAM_QUESTIONS) + len(AMS_QUESTIONS) + len(LIFESTYLE_QUESTIONS)
                answered_questions = len(context.user_data.get("adam_answers", [])) + current_question_index
                overall_progress = (answered_questions / total_questions) * 100
                progress_bar = "█" * int(overall_progress / 10) + "░" * (10 - int(overall_progress / 10))
                
                progress_text = (
                    f"📊 **Progreso General:** {int(overall_progress)}% [{progress_bar}]\n"
                    f"📋 **Sección:** AMS - Pregunta {current_question_index + 1} de {len(AMS_QUESTIONS)}\n\n"
                    f"{AMS_QUESTIONS[current_question_index]}"
                )
                await error_handler.safe_send_message(update, context, progress_text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(error_message)
                await update.message.reply_text(AMS_QUESTIONS[current_question_index])
            
            # Log validation error
            if logging_system:
                logging_system.log_warning(
                    f"Invalid AMS response from user {user_id}: {user_input}",
                    user_id=user_id,
                    context={"question_index": current_question_index, "input": user_input}
                )
            
            return STATE_AMS

        # Suma la puntuación y avanza a la siguiente pregunta.
        context.user_data["ams_score"] += score
        current_question_index += 1
        context.user_data["ams_question_index"] = current_question_index

        # Save progress after each answer
        if conversation_handler:
            conversation_handler.save_progress(user_id, ConversationState.AMS, context.user_data)

        if current_question_index < len(AMS_QUESTIONS):
            # Si quedan preguntas en AMS, hace la siguiente.
            # Enhanced progress display with review option
            total_questions = len(ADAM_QUESTIONS) + len(AMS_QUESTIONS) + len(LIFESTYLE_QUESTIONS)
            answered_questions = len(context.user_data.get("adam_answers", [])) + current_question_index
            overall_progress = (answered_questions / total_questions) * 100
            progress_bar = "█" * int(overall_progress / 10) + "░" * (10 - int(overall_progress / 10))
            
            keyboard = [[InlineKeyboardButton("📝 Revisar respuesta anterior", callback_data="review_ams")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            progress_text = (
                f"📊 **Progreso General:** {int(overall_progress)}% [{progress_bar}]\n"
                f"📋 **Sección:** AMS - Pregunta {current_question_index + 1} de {len(AMS_QUESTIONS)}\n"
                f"💯 **Puntuación actual:** {context.user_data['ams_score']} puntos\n\n"
                f"{AMS_QUESTIONS[current_question_index]}"
            )
            
            if error_handler:
                await error_handler.safe_send_message(update, context, progress_text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(text=progress_text, reply_markup=reply_markup)
            return STATE_AMS
        else:
            # Si AMS terminó, empieza con Estilo de Vida.
            # Initialize lifestyle tracking
            context.user_data["lifestyle_question_index"] = 0
            
            # Save progress for lifestyle start
            if conversation_handler:
                conversation_handler.save_progress(user_id, ConversationState.LIFESTYLE, context.user_data)
            
            # Show section completion with summary
            completion_message = (
                f"✅ **Cuestionario AMS completado**\n"
                f"Puntuación total: {context.user_data['ams_score']} puntos\n\n"
                f"Última sección: preguntas sobre tu estilo de vida."
            )
            
            # Enhanced progress display for lifestyle start
            total_questions = len(ADAM_QUESTIONS) + len(AMS_QUESTIONS) + len(LIFESTYLE_QUESTIONS)
            answered_questions = len(context.user_data.get("adam_answers", [])) + len(AMS_QUESTIONS)
            overall_progress = (answered_questions / total_questions) * 100
            progress_bar = "█" * int(overall_progress / 10) + "░" * (10 - int(overall_progress / 10))
            
            progress_text = (
                f"📊 **Progreso General:** {int(overall_progress)}% [{progress_bar}]\n"
                f"📋 **Sección:** Estilo de Vida - Pregunta 1 de {len(LIFESTYLE_QUESTIONS)}\n\n"
                f"{LIFESTYLE_QUESTIONS[0]}"
            )
            
            if error_handler:
                await error_handler.safe_send_message(update, context, completion_message)
                await error_handler.safe_send_message(update, context, progress_text)
            else:
                await update.message.reply_text(completion_message)
                await update.message.reply_text(text=progress_text)
            
            # Log completion
            if logging_system:
                logging_system.log_user_action(
                    user_id, 
                    "ams_completed", 
                    {"total_score": context.user_data["ams_score"]}
                )
            
            return STATE_LIFESTYLE
            
    except Exception as e:
        if error_handler and logging_system:
            error_context = ErrorContext(
                user_id=user_id,
                chat_id=update.effective_chat.id if update.effective_chat else None,
                function_name="ams_handler",
                additional_data={"question_index": current_question_index, "user_input": user_input}
            )
            recovery_action, user_message = await error_handler.handle_error(e, error_context)
            
            if user_message:
                await error_handler.safe_send_message(update, context, user_message)
                # Re-ask the current question
                await error_handler.safe_send_message(update, context, AMS_QUESTIONS[current_question_index])
        else:
            logger.error(f"Error in ams_handler: {e}")
            await update.message.reply_text("Ha ocurrido un error. Por favor, intenta de nuevo.")
            
        return STATE_AMS


async def lifestyle_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Maneja las preguntas sobre estilo de vida, que tienen diferentes tipos de respuesta.
    """
    user_input = update.message.text
    user_id = update.effective_user.id if update.effective_user else None
    current_question_index = context.user_data.get("lifestyle_question_index", 0)
    question_key = f"q{current_question_index}"

    # --- Validación de cada pregunta ---
    try:
        if current_question_index == 0: # Edad
            age = int(user_input)
            if age <= 0 or age > 120: raise ValueError
            context.user_data["lifestyle_answers"][question_key] = age
        elif current_question_index == 1: # Grasa corporal
            fat = int(user_input)
            if not 0 <= fat <= 100: raise ValueError
            context.user_data["lifestyle_answers"][question_key] = fat
        elif current_question_index in [2, 3]: # Sueño y Estrés (1-5)
            score = int(user_input)
            if not 1 <= score <= 5: raise ValueError
            context.user_data["lifestyle_answers"][question_key] = score
        elif current_question_index == 4: # Ejercicio
            times = int(user_input)
            if times < 0: raise ValueError
            context.user_data["lifestyle_answers"][question_key] = times
        elif current_question_index == 5: # Alcohol/Tabaco
            if user_input.lower() not in ['sí', 'si', 'no']: raise ValueError
            context.user_data["lifestyle_answers"][question_key] = user_input.lower().startswith('s')
    except (ValueError, TypeError):
        # Enhanced error handling with specific validation messages and review option
        keyboard = [[InlineKeyboardButton("📝 Revisar respuesta anterior", callback_data="review_lifestyle")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Specific error messages based on question type
        if current_question_index == 0:
            error_msg = "Por favor, introduce una edad válida (18-120 años)."
        elif current_question_index == 1:
            error_msg = "Por favor, introduce un porcentaje de grasa corporal válido (0-100%)."
        elif current_question_index in [2, 3]:
            error_msg = "Por favor, introduce un número del 1 al 5."
        elif current_question_index == 4:
            error_msg = "Por favor, introduce un número válido de veces por semana (0 o más)."
        else:
            error_msg = "Por favor, responde 'sí' o 'no'."
        
        # Enhanced progress display for errors
        total_questions = len(ADAM_QUESTIONS) + len(AMS_QUESTIONS) + len(LIFESTYLE_QUESTIONS)
        answered_questions = len(context.user_data.get("adam_answers", [])) + len(AMS_QUESTIONS) + current_question_index
        overall_progress = (answered_questions / total_questions) * 100
        progress_bar = "█" * int(overall_progress / 10) + "░" * (10 - int(overall_progress / 10))
        
        progress_text = (
            f"📊 **Progreso General:** {int(overall_progress)}% [{progress_bar}]\n"
            f"📋 **Sección:** Estilo de Vida - Pregunta {current_question_index + 1} de {len(LIFESTYLE_QUESTIONS)}\n\n"
            f"{LIFESTYLE_QUESTIONS[current_question_index]}"
        )
        
        await update.message.reply_text(error_msg)
        await update.message.reply_text(text=progress_text, reply_markup=reply_markup)
        return STATE_LIFESTYLE

    # Avanza a la siguiente pregunta de estilo de vida.
    current_question_index += 1
    context.user_data["lifestyle_question_index"] = current_question_index

    # Save progress after each answer
    if conversation_handler:
        conversation_handler.save_progress(user_id, ConversationState.LIFESTYLE, context.user_data)

    if current_question_index < len(LIFESTYLE_QUESTIONS):
        # Si quedan preguntas, hace la siguiente.
        # Enhanced progress display
        total_questions = len(ADAM_QUESTIONS) + len(AMS_QUESTIONS) + len(LIFESTYLE_QUESTIONS)
        answered_questions = len(context.user_data.get("adam_answers", [])) + len(AMS_QUESTIONS) + current_question_index
        overall_progress = (answered_questions / total_questions) * 100
        progress_bar = "█" * int(overall_progress / 10) + "░" * (10 - int(overall_progress / 10))
        
        progress_text = (
            f"📊 **Progreso General:** {int(overall_progress)}% [{progress_bar}]\n"
            f"📋 **Sección:** Estilo de Vida - Pregunta {current_question_index + 1} de {len(LIFESTYLE_QUESTIONS)}\n\n"
            f"{LIFESTYLE_QUESTIONS[current_question_index]}"
        )
        
        # Para la última pregunta, muestra botones Sí/No con opción de revisar.
        if current_question_index == 5:
            keyboard = [
                [InlineKeyboardButton("Sí", callback_data="ls_yes"), InlineKeyboardButton("No", callback_data="ls_no")],
                [InlineKeyboardButton("📝 Revisar respuesta anterior", callback_data="review_lifestyle")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text=progress_text, reply_markup=reply_markup)
        else:
            keyboard = [[InlineKeyboardButton("📝 Revisar respuesta anterior", callback_data="review_lifestyle")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text=progress_text, reply_markup=reply_markup)
        return STATE_LIFESTYLE
    else:
        # Si todas las preguntas terminaron, calcula y muestra los resultados.
        return await send_final_results(update, context)

async def lifestyle_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la respuesta de Sí/No para la última pregunta de estilo de vida."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id if update.effective_user else None
    
    current_question_index = context.user_data.get("lifestyle_question_index", 5)
    question_key = f"q{current_question_index}"

    context.user_data["lifestyle_answers"][question_key] = query.data == 'ls_yes'
    
    # Save final progress
    if conversation_handler:
        conversation_handler.save_progress(user_id, ConversationState.RESULTS, context.user_data)
    
    await query.edit_message_text("✅ Cuestionario completado al 100%. Calculando tus resultados...")
    return await send_final_results(update, context)


async def review_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Maneja las solicitudes de revisión de respuestas anteriores.
    """
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id if update.effective_user else None
    
    try:
        if query.data == "review_adam":
            return await handle_adam_review(update, context)
        elif query.data == "review_ams":
            return await handle_ams_review(update, context)
        elif query.data == "review_lifestyle":
            return await handle_lifestyle_review(update, context)
        else:
            await query.edit_message_text("Opción de revisión no válida.")
            return ConversationHandler.END
            
    except Exception as e:
        if error_handler and logging_system:
            error_context = ErrorContext(
                user_id=user_id,
                chat_id=update.effective_chat.id if update.effective_chat else None,
                function_name="review_handler"
            )
            recovery_action, user_message = await error_handler.handle_error(e, error_context)
            
            if user_message:
                await error_handler.safe_send_message(update, context, user_message)
        else:
            logger.error(f"Error in review_handler: {e}")
            await query.edit_message_text("Ha ocurrido un error durante la revisión.")
            
        return ConversationHandler.END


async def handle_adam_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la revisión de respuestas ADAM."""
    query = update.callback_query
    adam_answers = context.user_data.get("adam_answers", [])
    
    if not adam_answers:
        await query.edit_message_text("No hay respuestas ADAM para revisar.")
        return STATE_ADAM
    
    # Show summary of ADAM answers
    review_text = "📝 **Revisión de respuestas ADAM:**\n\n"
    for i, answer in enumerate(adam_answers):
        response = "Sí" if answer else "No"
        review_text += f"{i+1}. {ADAM_QUESTIONS[i][:50]}... → **{response}**\n"
    
    review_text += f"\n✅ Respuestas 'Sí': {sum(adam_answers)}/10"
    review_text += "\n\n¿Qué te gustaría hacer?"
    
    keyboard = [
        [InlineKeyboardButton("✅ Continuar", callback_data="continue_adam")],
        [InlineKeyboardButton("🔄 Modificar última respuesta", callback_data="modify_adam_last")],
        [InlineKeyboardButton("🔄 Reiniciar ADAM", callback_data="restart_adam")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=review_text, reply_markup=reply_markup)
    return STATE_ADAM


async def handle_ams_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la revisión de respuestas AMS."""
    query = update.callback_query
    ams_score = context.user_data.get("ams_score", 0)
    ams_index = context.user_data.get("ams_question_index", 0)
    
    if ams_index == 0:
        await query.edit_message_text("No hay respuestas AMS para revisar.")
        return STATE_AMS
    
    # Show AMS progress summary
    review_text = (
        f"📝 **Revisión del progreso AMS:**\n\n"
        f"Preguntas respondidas: {ams_index}/{len(AMS_QUESTIONS)}\n"
        f"Puntuación actual: {ams_score} puntos\n"
        f"Promedio por pregunta: {ams_score/ams_index:.1f}\n\n"
        f"¿Qué te gustaría hacer?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Continuar", callback_data="continue_ams")],
        [InlineKeyboardButton("🔄 Modificar última respuesta", callback_data="modify_ams_last")],
        [InlineKeyboardButton("🔄 Reiniciar AMS", callback_data="restart_ams")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=review_text, reply_markup=reply_markup)
    return STATE_AMS


async def handle_lifestyle_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la revisión de respuestas de estilo de vida."""
    query = update.callback_query
    lifestyle_answers = context.user_data.get("lifestyle_answers", {})
    lifestyle_index = context.user_data.get("lifestyle_question_index", 0)
    
    if not lifestyle_answers:
        await query.edit_message_text("No hay respuestas de estilo de vida para revisar.")
        return STATE_LIFESTYLE
    
    # Show lifestyle answers summary
    review_text = "📝 **Revisión de respuestas de Estilo de Vida:**\n\n"
    
    for i in range(lifestyle_index):
        question_key = f"q{i}"
        if question_key in lifestyle_answers:
            answer = lifestyle_answers[question_key]
            if i == 0:  # Edad
                review_text += f"Edad: {answer} años\n"
            elif i == 1:  # Grasa corporal
                review_text += f"Grasa corporal: {answer}%\n"
            elif i == 2:  # Sueño
                review_text += f"Calidad del sueño: {answer}/5\n"
            elif i == 3:  # Estrés
                review_text += f"Nivel de estrés: {answer}/5\n"
            elif i == 4:  # Ejercicio
                review_text += f"Ejercicio por semana: {answer} veces\n"
            elif i == 5:  # Alcohol/Tabaco
                response = "Sí" if answer else "No"
                review_text += f"Alcohol/Tabaco regular: {response}\n"
    
    review_text += "\n¿Qué te gustaría hacer?"
    
    keyboard = [
        [InlineKeyboardButton("✅ Continuar", callback_data="continue_lifestyle")],
        [InlineKeyboardButton("🔄 Modificar última respuesta", callback_data="modify_lifestyle_last")],
        [InlineKeyboardButton("🔄 Reiniciar Estilo de Vida", callback_data="restart_lifestyle")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=review_text, reply_markup=reply_markup)
    return STATE_LIFESTYLE


async def send_final_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Calcula todos los resultados y envía el mensaje final al usuario.
    """
    user_id = update.effective_user.id if update.effective_user else None
    
    try:
        # Log completion
        if logging_system:
            logging_system.log_user_action(user_id, "questionnaire_completed")
        
        # --- 1. Cálculo del resultado ADAM ---
        adam_answers = context.user_data["adam_answers"]
        # Regla: "sí" en la pregunta 1, 7, o en 3 preguntas cualesquiera.
        is_q1_yes = adam_answers[0]
        is_q7_yes = adam_answers[6]
        total_yes = sum(1 for answer in adam_answers if answer)
        
        if is_q1_yes or is_q7_yes or total_yes >= 3:
            adam_result = "🔴 Posible déficit."
        else:
            adam_result = "🟢 No se detecta un posible déficit."

        # --- 2. Cálculo del resultado AMS ---
        ams_score = context.user_data["ams_score"]
        if ams_score <= 26:
            ams_interpretation = "No significativo"
        elif 27 <= ams_score <= 36:
            ams_interpretation = "Leve"
        elif 37 <= ams_score <= 49:
            ams_interpretation = "Moderado"
        else:
            ams_interpretation = "Severo"
        ams_result = f"{ams_score} puntos → {ams_interpretation}."

        # --- 3. Análisis de factores de estilo de vida ---
        lifestyle_answers = context.user_data["lifestyle_answers"]
        lifestyle_factors = []
        if lifestyle_answers.get("q2", 15) > 20:
            lifestyle_factors.append("Grasa corporal elevada")
        if lifestyle_answers.get("q3", 3) <= 2:
            lifestyle_factors.append("Mala calidad del sueño")
        if lifestyle_answers.get("q4", 3) >= 4:
            lifestyle_factors.append("Alto nivel de estrés")
        if lifestyle_answers.get("q5", 2) < 2:
            lifestyle_factors.append("Poco ejercicio de fuerza")
        if lifestyle_answers.get("q6", False):
            lifestyle_factors.append("Consumo regular de alcohol/tabaco")

        if lifestyle_factors:
            lifestyle_summary = "Factores a mejorar: " + ", ".join(lifestyle_factors) + "."
        else:
            lifestyle_summary = "Tus hábitos de estilo de vida parecen adecuados."

        # --- 4. Construcción del mensaje final ---
        final_message = (
            "🧬 **BOT DE TESTOSTERONA** 🧬\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📝 **RESULTADOS DE TU EVALUACIÓN**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ **Resultado ADAM:** {adam_result}\n"
            f"📊 **Escala AMS:** {ams_result}\n"
            f"🏃‍♂️ **Estilo de Vida:** {lifestyle_summary}\n\n"
            "👉 **Recomendación:**\n"
            "Recuerda que esto es solo una estimación. Si tus resultados indican un posible déficit o síntomas moderados/severos, considera consultar a un médico especialista (urólogo o endocrinólogo) para un diagnóstico preciso a través de un análisis de sangre.\n\n"
            "Para volver a empezar, escribe /start."
        )
        
        # Enhanced result sharing options (Requirement 6.4)
        keyboard = [
            [InlineKeyboardButton("💾 Guardar resultados", callback_data="save_results")],
            [InlineKeyboardButton("📤 Compartir resultados", callback_data="share_results")],
            [InlineKeyboardButton("📊 Ver detalles", callback_data="detailed_results")],
            [InlineKeyboardButton("🔄 Nuevo cuestionario", callback_data="new_questionnaire")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send message with retry mechanism and result options
        if error_handler:
            # Use retry decorator for network operations
            @error_handler.with_retry(max_retries=3)
            async def send_results_with_retry():
                chat_id = update.effective_chat.id
                await context.bot.send_message(chat_id=chat_id, text=final_message, reply_markup=reply_markup)
            
            await send_results_with_retry()
        else:
            chat_id = update.effective_chat.id
            await context.bot.send_message(chat_id=chat_id, text=final_message, reply_markup=reply_markup)
        
        # Store results temporarily for saving/sharing
        context.user_data["final_results"] = {
            "adam_result": adam_result,
            "ams_result": ams_result,
            "lifestyle_summary": lifestyle_summary,
            "adam_yes_count": total_yes,
            "ams_score": ams_score,
            "ams_interpretation": ams_interpretation,
            "lifestyle_factors": lifestyle_factors,
            "completion_date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        # Log results for analytics (anonymized)
        if logging_system:
            results_data = {
                "adam_positive": is_q1_yes or is_q7_yes or total_yes >= 3,
                "adam_yes_count": total_yes,
                "ams_score": ams_score,
                "ams_interpretation": ams_interpretation,
                "lifestyle_factors_count": len(lifestyle_factors)
            }
            logging_system.log_user_action(user_id, "results_calculated", results_data)
        
        # Set the conversation state to RESULTS so the buttons work
        return STATE_RESULTS
            
    except Exception as e:
        if error_handler and logging_system:
            error_context = ErrorContext(
                user_id=user_id,
                chat_id=update.effective_chat.id if update.effective_chat else None,
                function_name="send_final_results"
            )
            recovery_action, user_message = await error_handler.handle_error(e, error_context)
            
            if user_message:
                await error_handler.safe_send_message(update, context, user_message)
        else:
            logger.error(f"Error in send_final_results: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Ha ocurrido un error al generar los resultados. Por favor, intenta de nuevo con /start."
            )


async def results_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Maneja las acciones de guardar, compartir y ver detalles de los resultados.
    """
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id if update.effective_user else None
    
    try:
        results = context.user_data.get("final_results")
        if not results:
            await query.edit_message_text("Los resultados ya no están disponibles. Usa /start para realizar un nuevo cuestionario.")
            return ConversationHandler.END
        
        if query.data == "save_results":
            # Generate a formatted results summary for saving
            saved_results = (
                f"🧪 **Resultados del Cuestionario de Testosterona**\n"
                f"📅 Fecha: {results['completion_date']}\n\n"
                f"**ADAM:** {results['adam_result']}\n"
                f"**AMS:** {results['ams_result']}\n"
                f"**Estilo de Vida:** {results['lifestyle_summary']}\n\n"
                f"**Detalles:**\n"
                f"• Respuestas ADAM 'Sí': {results['adam_yes_count']}/10\n"
                f"• Puntuación AMS: {results['ams_score']} ({results['ams_interpretation']})\n"
                f"• Factores de riesgo identificados: {len(results['lifestyle_factors'])}\n\n"
                f"⚠️ Estos resultados son solo orientativos. Consulta a un médico para un diagnóstico preciso."
            )
            
            # Create enhanced keyboard with all options
            keyboard = [
                [InlineKeyboardButton("💾 Guardar resultados", callback_data="save_results")],
                [InlineKeyboardButton("📤 Compartir resultados", callback_data="share_results")],
                [InlineKeyboardButton("📊 Ver detalles", callback_data="detailed_results")],
                [InlineKeyboardButton("🔄 Nuevo cuestionario", callback_data="new_questionnaire")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"💾 **Resultados guardados:**\n\n{saved_results}\n\n"
                f"Puedes copiar este texto para guardarlo en tus notas personales.",
                reply_markup=reply_markup
            )
            
            # Log save action
            if logging_system:
                logging_system.log_user_action(user_id, "results_saved")
                
        elif query.data == "share_results":
            # Generate a shareable summary (without personal details)
            share_text = (
                f"🧪 **Resumen de Evaluación de Testosterona**\n\n"
                f"**ADAM:** {results['adam_result']}\n"
                f"**AMS:** {results['ams_interpretation']} ({results['ams_score']} puntos)\n"
                f"**Factores de estilo de vida:** {len(results['lifestyle_factors'])} identificados\n\n"
                f"⚠️ Resultados orientativos. Consulta médica recomendada.\n\n"
                f"🤖 Evaluación realizada con el Bot de Testosterona"
            )
            
            # Create enhanced keyboard with all options
            keyboard = [
                [InlineKeyboardButton("💾 Guardar resultados", callback_data="save_results")],
                [InlineKeyboardButton("📤 Compartir resultados", callback_data="share_results")],
                [InlineKeyboardButton("📊 Ver detalles", callback_data="detailed_results")],
                [InlineKeyboardButton("🔄 Nuevo cuestionario", callback_data="new_questionnaire")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"📤 **Texto para compartir:**\n\n{share_text}\n\n"
                f"Puedes copiar este texto para compartir tus resultados de forma anónima.",
                reply_markup=reply_markup
            )
            
            # Log share action
            if logging_system:
                logging_system.log_user_action(user_id, "results_shared")
                
        elif query.data == "detailed_results":
            # Show detailed breakdown with enhanced information
            detailed_text = (
                f"📊 **Análisis Detallado Completo**\n\n"
                f"**📋 Cuestionario ADAM (Androgen Deficiency in Aging Males):**\n"
                f"• Respuestas 'Sí': {results['adam_yes_count']}/10\n"
                f"• Resultado: {results['adam_result']}\n"
                f"• Criterio: Posible déficit si pregunta 1 o 7 es 'Sí', o 3+ respuestas 'Sí'\n\n"
                f"**📈 Escala AMS (Aging Male's Symptoms):**\n"
                f"• Puntuación total: {results['ams_score']}/85 puntos\n"
                f"• Interpretación: {results['ams_interpretation']}\n"
                f"• Rangos de interpretación:\n"
                f"  - ≤26: No significativo\n"
                f"  - 27-36: Leve\n"
                f"  - 37-49: Moderado\n"
                f"  - ≥50: Severo\n\n"
                f"**🏃‍♂️ Factores de Estilo de Vida Analizados:**\n"
            )
            
            if results['lifestyle_factors']:
                for i, factor in enumerate(results['lifestyle_factors'], 1):
                    detailed_text += f"• {i}. {factor}\n"
            else:
                detailed_text += "• ✅ No se identificaron factores de riesgo significativos\n"
            
            # Add more detailed recommendations
            detailed_text += (
                f"\n**💡 Recomendaciones Específicas:**\n"
                f"• 🏥 Consulta médica si hay síntomas moderados/severos\n"
                f"• 🧪 Análisis de sangre (testosterona total y libre)\n"
                f"• 💪 Ejercicio de fuerza regular (3-4 veces/semana)\n"
                f"• 😴 Mejorar calidad del sueño (7-9 horas)\n"
                f"• 🍎 Alimentación equilibrada y reducción de estrés\n"
                f"• 🚫 Evitar alcohol y tabaco en exceso\n\n"
                f"**⚠️ Importante:** Estos resultados son orientativos. Solo un análisis de sangre y consulta médica pueden confirmar un diagnóstico real."
            )
            
            # Create enhanced keyboard with all options
            keyboard = [
                [InlineKeyboardButton("💾 Guardar resultados", callback_data="save_results")],
                [InlineKeyboardButton("📤 Compartir resultados", callback_data="share_results")],
                [InlineKeyboardButton("📊 Ver detalles", callback_data="detailed_results")],
                [InlineKeyboardButton("🔄 Nuevo cuestionario", callback_data="new_questionnaire")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(detailed_text, reply_markup=reply_markup)
            
            # Log detailed view action
            if logging_system:
                logging_system.log_user_action(user_id, "detailed_results_viewed")
        
        elif query.data == "new_questionnaire":
            # Clear all data and start fresh
            if conversation_handler:
                conversation_handler.clear_user_data(user_id)
            context.user_data.clear()
            
            # Log new questionnaire action
            if logging_system:
                logging_system.log_user_action(user_id, "new_questionnaire_started")
            
            # Show welcome message and start new questionnaire
            keyboard = [
                [InlineKeyboardButton("✅ Sí, comenzar", callback_data="start_yes"),
                 InlineKeyboardButton("❌ No, ahora no", callback_data="start_no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = (
                "🔄 **Nuevo Cuestionario de Testosterona**\n\n"
                "Te haré una serie de preguntas basadas en cuestionarios médicos (ADAM + AMS) y sobre tu estilo de vida para darte una estimación de tu nivel de testosterona.\n\n"
                "⚠️ **Importante:** Esto NO reemplaza un análisis de sangre ni una consulta médica. Es solo una herramienta orientativa.\n\n"
                "¿Quieres comenzar un nuevo cuestionario?"
            )
            
            await query.edit_message_text(message, reply_markup=reply_markup)
            return STATE_START
        
        # Don't clear data after other actions - keep results available
        return STATE_RESULTS
        
    except Exception as e:
        if error_handler and logging_system:
            error_context = ErrorContext(
                user_id=user_id,
                chat_id=update.effective_chat.id if update.effective_chat else None,
                function_name="results_action_handler"
            )
            recovery_action, user_message = await error_handler.handle_error(e, error_context)
            
            if user_message:
                await error_handler.safe_send_message(update, context, user_message)
        else:
            logger.error(f"Error in results_action_handler: {e}")
            await query.edit_message_text("Ha ocurrido un error. Los resultados se han perdido.")
            
        return ConversationHandler.END


async def modification_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Maneja las modificaciones y continuaciones desde las revisiones.
    """
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id if update.effective_user else None
    
    try:
        if query.data.startswith("continue_"):
            # Continue from current position
            section = query.data.split("_")[1]
            await query.edit_message_text("Continuando con el cuestionario...")
            
            if section == "adam":
                current_index = len(context.user_data.get("adam_answers", []))
                if current_index < len(ADAM_QUESTIONS):
                    keyboard = [
                        [InlineKeyboardButton("Sí", callback_data="adam_yes"), InlineKeyboardButton("No", callback_data="adam_no")],
                        [InlineKeyboardButton("📝 Revisar respuesta anterior", callback_data="review_adam")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    total_questions = len(ADAM_QUESTIONS) + len(AMS_QUESTIONS) + len(LIFESTYLE_QUESTIONS)
                    overall_progress = (current_index / total_questions) * 100
                    progress_bar = "█" * int(overall_progress / 10) + "░" * (10 - int(overall_progress / 10))
                    
                    progress_text = (
                        f"📊 **Progreso General:** {int(overall_progress)}% [{progress_bar}]\n"
                        f"📋 **Sección:** ADAM - Pregunta {current_index + 1} de {len(ADAM_QUESTIONS)}\n\n"
                        f"{ADAM_QUESTIONS[current_index]}"
                    )
                    
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=progress_text,
                        reply_markup=reply_markup
                    )
                    return STATE_ADAM
                    
            elif section == "ams":
                current_index = context.user_data.get("ams_question_index", 0)
                if current_index < len(AMS_QUESTIONS):
                    total_questions = len(ADAM_QUESTIONS) + len(AMS_QUESTIONS) + len(LIFESTYLE_QUESTIONS)
                    answered_questions = len(context.user_data.get("adam_answers", [])) + current_index
                    overall_progress = (answered_questions / total_questions) * 100
                    progress_bar = "█" * int(overall_progress / 10) + "░" * (10 - int(overall_progress / 10))
                    
                    keyboard = [[InlineKeyboardButton("📝 Revisar respuesta anterior", callback_data="review_ams")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    progress_text = (
                        f"📊 **Progreso General:** {int(overall_progress)}% [{progress_bar}]\n"
                        f"📋 **Sección:** AMS - Pregunta {current_index + 1} de {len(AMS_QUESTIONS)}\n"
                        f"💯 **Puntuación actual:** {context.user_data.get('ams_score', 0)} puntos\n\n"
                        f"{AMS_QUESTIONS[current_index]}"
                    )
                    
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=progress_text,
                        reply_markup=reply_markup
                    )
                    return STATE_AMS
                    
            elif section == "lifestyle":
                current_index = context.user_data.get("lifestyle_question_index", 0)
                if current_index < len(LIFESTYLE_QUESTIONS):
                    total_questions = len(ADAM_QUESTIONS) + len(AMS_QUESTIONS) + len(LIFESTYLE_QUESTIONS)
                    answered_questions = len(context.user_data.get("adam_answers", [])) + len(AMS_QUESTIONS) + current_index
                    overall_progress = (answered_questions / total_questions) * 100
                    progress_bar = "█" * int(overall_progress / 10) + "░" * (10 - int(overall_progress / 10))
                    
                    progress_text = (
                        f"📊 **Progreso General:** {int(overall_progress)}% [{progress_bar}]\n"
                        f"📋 **Sección:** Estilo de Vida - Pregunta {current_index + 1} de {len(LIFESTYLE_QUESTIONS)}\n\n"
                        f"{LIFESTYLE_QUESTIONS[current_index]}"
                    )
                    
                    if current_index == 5:  # Last question with buttons
                        keyboard = [
                            [InlineKeyboardButton("Sí", callback_data="ls_yes"), InlineKeyboardButton("No", callback_data="ls_no")],
                            [InlineKeyboardButton("📝 Revisar respuesta anterior", callback_data="review_lifestyle")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=progress_text,
                            reply_markup=reply_markup
                        )
                    else:
                        keyboard = [[InlineKeyboardButton("📝 Revisar respuesta anterior", callback_data="review_lifestyle")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=progress_text,
                            reply_markup=reply_markup
                        )
                    return STATE_LIFESTYLE
                    
        elif query.data.startswith("modify_") and query.data.endswith("_last"):
            # Modify last answer
            section = query.data.split("_")[1]
            
            if section == "adam":
                adam_answers = context.user_data.get("adam_answers", [])
                if adam_answers:
                    # Remove last answer
                    adam_answers.pop()
                    context.user_data["adam_answers"] = adam_answers
                    
                    # Save progress
                    if conversation_handler:
                        conversation_handler.save_progress(user_id, ConversationState.ADAM, context.user_data)
                    
                    # Re-ask the question
                    current_index = len(adam_answers)
                    keyboard = [
                        [InlineKeyboardButton("Sí", callback_data="adam_yes"), InlineKeyboardButton("No", callback_data="adam_no")],
                        [InlineKeyboardButton("📝 Revisar respuesta anterior", callback_data="review_adam")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await query.edit_message_text(
                        f"🔄 Modificando respuesta anterior.\n\n{ADAM_QUESTIONS[current_index]}",
                        reply_markup=reply_markup
                    )
                    return STATE_ADAM
                    
            elif section == "ams":
                ams_index = context.user_data.get("ams_question_index", 0)
                if ams_index > 0:
                    # We need to ask user what their previous answer was to subtract it
                    await query.edit_message_text(
                        f"🔄 Para modificar tu respuesta anterior, por favor responde nuevamente a:\n\n"
                        f"{AMS_QUESTIONS[ams_index - 1]}\n\n"
                        f"Tu respuesta anterior será reemplazada."
                    )
                    
                    # Adjust index and score
                    context.user_data["ams_question_index"] = ams_index - 1
                    # Note: We can't easily subtract the previous score without knowing it
                    # So we'll let the user re-answer and handle it in the handler
                    
                    if conversation_handler:
                        conversation_handler.save_progress(user_id, ConversationState.AMS, context.user_data)
                    
                    return STATE_AMS
                    
            elif section == "lifestyle":
                lifestyle_index = context.user_data.get("lifestyle_question_index", 0)
                if lifestyle_index > 0:
                    # Remove last answer
                    question_key = f"q{lifestyle_index - 1}"
                    lifestyle_answers = context.user_data.get("lifestyle_answers", {})
                    if question_key in lifestyle_answers:
                        del lifestyle_answers[question_key]
                    
                    context.user_data["lifestyle_question_index"] = lifestyle_index - 1
                    
                    if conversation_handler:
                        conversation_handler.save_progress(user_id, ConversationState.LIFESTYLE, context.user_data)
                    
                    # Re-ask the question
                    current_index = lifestyle_index - 1
                    await query.edit_message_text(
                        f"🔄 Modificando respuesta anterior.\n\n{LIFESTYLE_QUESTIONS[current_index]}"
                    )
                    return STATE_LIFESTYLE
                    
        elif query.data.startswith("restart_"):
            # Restart entire section
            section = query.data.split("_")[1]
            
            if section == "adam":
                context.user_data["adam_answers"] = []
                if conversation_handler:
                    conversation_handler.save_progress(user_id, ConversationState.ADAM, context.user_data)
                
                keyboard = [
                    [InlineKeyboardButton("Sí", callback_data="adam_yes"), InlineKeyboardButton("No", callback_data="adam_no")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"🔄 Reiniciando cuestionario ADAM.\n\n{ADAM_QUESTIONS[0]}",
                    reply_markup=reply_markup
                )
                return STATE_ADAM
                
            elif section == "ams":
                context.user_data["ams_score"] = 0
                context.user_data["ams_question_index"] = 0
                if conversation_handler:
                    conversation_handler.save_progress(user_id, ConversationState.AMS, context.user_data)
                
                await query.edit_message_text(
                    f"🔄 Reiniciando cuestionario AMS.\n\n{AMS_QUESTIONS[0]}"
                )
                return STATE_AMS
                
            elif section == "lifestyle":
                context.user_data["lifestyle_answers"] = {}
                context.user_data["lifestyle_question_index"] = 0
                if conversation_handler:
                    conversation_handler.save_progress(user_id, ConversationState.LIFESTYLE, context.user_data)
                
                await query.edit_message_text(
                    f"🔄 Reiniciando preguntas de estilo de vida.\n\n{LIFESTYLE_QUESTIONS[0]}"
                )
                return STATE_LIFESTYLE
        
        return ConversationHandler.END
        
    except Exception as e:
        if error_handler and logging_system:
            error_context = ErrorContext(
                user_id=user_id,
                chat_id=update.effective_chat.id if update.effective_chat else None,
                function_name="modification_handler"
            )
            recovery_action, user_message = await error_handler.handle_error(e, error_context)
            
            if user_message:
                await error_handler.safe_send_message(update, context, user_message)
        else:
            logger.error(f"Error in modification_handler: {e}")
            await query.edit_message_text("Ha ocurrido un error durante la modificación.")
            
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Cancela la conversación en cualquier momento con /cancel.
    """
    user_id = update.effective_user.id if update.effective_user else None
    
    # Clear persistent data
    if conversation_handler:
        conversation_handler.clear_user_data(user_id)
    
    await update.message.reply_text("Cuestionario cancelado. Si quieres volver a empezar, escribe /start.")
    context.user_data.clear()
    return ConversationHandler.END


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Muestra el progreso actual del usuario con /status.
    """
    user_id = update.effective_user.id if update.effective_user else None
    
    if not conversation_handler:
        await update.message.reply_text("Sistema de progreso no disponible.")
        return
    
    progress_message = conversation_handler.show_progress(user_id)
    
    if progress_message:
        await update.message.reply_text(progress_message)
        await update.message.reply_text("Usa /start para continuar el cuestionario.")
    else:
        await update.message.reply_text(
            "No tienes ningún cuestionario en progreso.\n"
            "Usa /start para comenzar un nuevo cuestionario."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Muestra la lista de comandos disponibles con /help.
    """
    help_text = (
        "🤖 **Comandos disponibles:**\n\n"
        "/start - Iniciar o continuar el cuestionario\n"
        "/status - Ver tu progreso actual\n"
        "/info - Información sobre los cuestionarios\n"
        "/reset - Reiniciar el cuestionario actual\n"
        "/cancel - Cancelar el cuestionario\n"
        "/help - Mostrar esta ayuda\n\n"
        "💡 **Consejos:**\n"
        "• El bot guarda tu progreso automáticamente\n"
        "• Puedes continuar donde lo dejaste hasta 24 horas después\n"
        "• Solo funciona en chats privados para proteger tu privacidad"
    )
    
    await update.message.reply_text(help_text)


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Muestra información sobre los cuestionarios con /info.
    """
    info_text = (
        "📋 **Información sobre los cuestionarios:**\n\n"
        "**Cuestionario ADAM (10 preguntas)**\n"
        "• Androgen Deficiency in Aging Males\n"
        "• Preguntas de Sí/No sobre síntomas\n"
        "• Detecta posible déficit de testosterona\n\n"
        "**Cuestionario AMS (17 preguntas)**\n"
        "• Aging Male's Symptoms\n"
        "• Escala de 1-5 por severidad de síntomas\n"
        "• Evaluación más detallada\n\n"
        "**Preguntas de Estilo de Vida (6 preguntas)**\n"
        "• Edad, grasa corporal, sueño, estrés\n"
        "• Ejercicio y hábitos\n"
        "• Factores que afectan la testosterona\n\n"
        "⚠️ **Importante:** Este es solo un cuestionario orientativo.\n"
        "NO reemplaza un análisis de sangre ni consulta médica."
    )
    
    await update.message.reply_text(info_text)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Reinicia el cuestionario actual con /reset.
    """
    user_id = update.effective_user.id if update.effective_user else None
    
    # Clear all user data
    if conversation_handler:
        conversation_handler.clear_user_data(user_id)
    context.user_data.clear()
    
    await update.message.reply_text(
        "🔄 Cuestionario reiniciado.\n\n"
        "Usa /start para comenzar un nuevo cuestionario."
    )


async def timeout_reminder_task():
    """
    Tarea periódica para enviar recordatorios de timeout.
    """
    if not conversation_handler:
        return
    
    # This would need to be implemented with a job queue in a real application
    # For now, it's a placeholder for the timeout reminder functionality
    pass


def main() -> None:
    """Función principal que configura y ejecuta el bot."""
    global logging_system, error_handler, conversation_handler
    
    # Initialize configuration manager
    config_manager = ConfigManager()
    
    try:
        # Load and validate configuration
        bot_config = config_manager.load_config()
        token = config_manager.get_token()
        
        # Initialize logging system
        logging_config = config_manager.get_logging_config()
        logging_system = LoggingSystem(logging_config)
        
        # Initialize error handler
        from error_handler import RetryConfig
        retry_config = RetryConfig(
            max_retries=bot_config.max_retries,
            base_delay=1.0,
            max_delay=60.0
        )
        error_handler = ErrorHandler(logging_system, retry_config)
        
        # Initialize enhanced conversation handler
        conversation_handler = EnhancedConversationHandler(
            logging_system=logging_system,
            data_dir="data"
        )
        
        # Log successful initialization
        logging_system.log_info("Bot systems initialized successfully")
        
        # Log configuration summary (without sensitive data)
        config_summary = config_manager.get_config_summary()
        logging_system.log_info(f"Bot configuration loaded: {config_summary}")
        
    except ConfigurationError as e:
        if logging_system:
            logging_system.log_error(e, context={"stage": "configuration"})
        else:
            logger.error(f"Configuration error: {e}")
        
        print(f"❌ Configuration Error: {e}")
        print("\n💡 Quick Setup:")
        print("1. Copy .env.example to .env")
        print("2. Add your bot token from @BotFather to the .env file")
        print("3. Set TELEGRAM_BOT_TOKEN=your_actual_token_here")
        sys.exit(1)
    except Exception as e:
        if logging_system:
            logging_system.log_error(e, context={"stage": "initialization"})
        else:
            logger.error(f"Unexpected error during initialization: {e}")
        
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
    
    # Create application with secure token
    application = Application.builder().token(token).build()

    # --- Configuración del ConversationHandler ---
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            STATE_START: [CallbackQueryHandler(start_quiz_callback)],
            STATE_ADAM: [
                CallbackQueryHandler(adam_handler, pattern="^adam_"),
                CallbackQueryHandler(review_handler, pattern="^review_adam$"),
                CallbackQueryHandler(modification_handler, pattern="^(continue_adam|modify_adam_last|restart_adam)$")
            ],
            STATE_AMS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ams_handler),
                CallbackQueryHandler(review_handler, pattern="^review_ams$"),
                CallbackQueryHandler(modification_handler, pattern="^(continue_ams|modify_ams_last|restart_ams)$")
            ],
            STATE_LIFESTYLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lifestyle_handler),
                CallbackQueryHandler(lifestyle_button_handler, pattern="^ls_"),
                CallbackQueryHandler(review_handler, pattern="^review_lifestyle$"),
                CallbackQueryHandler(modification_handler, pattern="^(continue_lifestyle|modify_lifestyle_last|restart_lifestyle)$")
            ],
            STATE_RESULTS: [
                CallbackQueryHandler(results_action_handler, pattern="^(save_results|share_results|detailed_results|new_questionnaire)$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Add standalone command handlers
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("reset", reset_command))

    # Add error handler for unhandled errors
    async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle unhandled errors globally."""
        if error_handler and logging_system:
            user_id = None
            chat_id = None
            
            if isinstance(update, Update):
                user_id = update.effective_user.id if update.effective_user else None
                chat_id = update.effective_chat.id if update.effective_chat else None
            
            error_context = ErrorContext(
                user_id=user_id,
                chat_id=chat_id,
                function_name="global_error_handler",
                additional_data={"update_type": type(update).__name__}
            )
            
            recovery_action, user_message = await error_handler.handle_error(context.error, error_context)
            
            # Try to send user message if we have update context
            if user_message and isinstance(update, Update):
                await error_handler.safe_send_message(update, context, user_message)
        else:
            logger.error(f"Unhandled error: {context.error}")
    
    application.add_error_handler(global_error_handler)

    # Inicia el bot.
    try:
        print("🚀 El bot se ha iniciado y está esperando mensajes...")
        if logging_system:
            logging_system.log_info("Bot started successfully")
        
        application.run_polling()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot detenido por el usuario")
        if logging_system:
            logging_system.log_info("Bot stopped by user")
    except Exception as e:
        print(f"❌ Error ejecutando el bot: {e}")
        if logging_system:
            logging_system.log_error(e, context={"stage": "runtime"})
        raise
    finally:
        if conversation_handler:
            conversation_handler.cleanup()
        if logging_system:
            logging_system.log_info("Bot shutdown completed")


if __name__ == "__main__":
    main()
