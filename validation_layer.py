# -*- coding: utf-8 -*-

"""
Validation Layer for Telegram Bot Security Improvements
Provides specific validators for each question type with detailed error messages,
help suggestions, and progressive assistance for repeated errors.
"""

import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from security_manager import SecurityManager, InputType, ValidationResult

logger = logging.getLogger(__name__)


class QuestionType(Enum):
    """Types of questions in the questionnaire"""
    ADAM_YES_NO = "adam_yes_no"
    AMS_SCALE = "ams_scale"
    LIFESTYLE_AGE = "lifestyle_age"
    LIFESTYLE_BODY_FAT = "lifestyle_body_fat"
    LIFESTYLE_SLEEP_QUALITY = "lifestyle_sleep_quality"
    LIFESTYLE_STRESS_LEVEL = "lifestyle_stress_level"
    LIFESTYLE_EXERCISE_FREQUENCY = "lifestyle_exercise_frequency"
    LIFESTYLE_ALCOHOL_TOBACCO = "lifestyle_alcohol_tobacco"


@dataclass
class ValidationConfig:
    """Configuration for validation behavior"""
    max_retries_before_help: int = 3
    max_retries_before_progressive_help: int = 5
    enable_progressive_assistance: bool = True
    enable_format_suggestions: bool = True


@dataclass
class EnhancedValidationResult(ValidationResult):
    """Enhanced validation result with additional assistance features"""
    retry_count: int = 0
    progressive_help: Optional[str] = None
    examples: Optional[List[str]] = None
    is_progressive_help_triggered: bool = False


class ValidationLayer:
    """
    Enhanced validation layer that provides specific validators for each question type
    with detailed error messages, help suggestions, and progressive assistance.
    """
    
    def __init__(self, security_manager: SecurityManager, config: Optional[ValidationConfig] = None):
        """
        Initialize ValidationLayer.
        
        Args:
            security_manager: SecurityManager instance for basic validation
            config: Validation configuration (optional)
        """
        self.security_manager = security_manager
        self.config = config or ValidationConfig()
        
        # Track user retry counts per question type
        self.user_retry_counts: Dict[int, Dict[QuestionType, int]] = {}
        
        # Question type mappings to input types
        self.question_type_mapping = {
            QuestionType.ADAM_YES_NO: InputType.YES_NO,
            QuestionType.AMS_SCALE: InputType.SCALE_1_5,
            QuestionType.LIFESTYLE_AGE: InputType.AGE,
            QuestionType.LIFESTYLE_BODY_FAT: InputType.BODY_FAT,
            QuestionType.LIFESTYLE_SLEEP_QUALITY: InputType.SCALE_1_5,
            QuestionType.LIFESTYLE_STRESS_LEVEL: InputType.SCALE_1_5,
            QuestionType.LIFESTYLE_EXERCISE_FREQUENCY: InputType.EXERCISE_FREQUENCY,
            QuestionType.LIFESTYLE_ALCOHOL_TOBACCO: InputType.YES_NO,
        }
        
        logger.info("ValidationLayer initialized with progressive assistance enabled")
    
    def validate_question_response(self, user_input: str, question_type: QuestionType, 
                                 user_id: int) -> EnhancedValidationResult:
        """
        Validate user response for a specific question type with progressive assistance.
        
        Args:
            user_input: User's input text
            question_type: Type of question being answered
            user_id: User ID for tracking retries
            
        Returns:
            EnhancedValidationResult: Enhanced validation result with assistance
        """
        # Get current retry count for this user and question type
        retry_count = self._get_retry_count(user_id, question_type)
        
        # Get the corresponding input type for security manager validation
        input_type = self.question_type_mapping.get(question_type, InputType.FREE_TEXT)
        
        # Perform basic validation using security manager
        basic_result = self.security_manager.validate_input(user_input, input_type, user_id)
        
        # If validation failed, increment retry count and add progressive assistance
        if not basic_result.is_valid:
            self._increment_retry_count(user_id, question_type)
            new_retry_count = retry_count + 1
            
            # Create enhanced result with updated retry count
            enhanced_result = EnhancedValidationResult(
                is_valid=basic_result.is_valid,
                error_message=basic_result.error_message,
                help_message=basic_result.help_message,
                suggested_format=basic_result.suggested_format,
                retry_count=new_retry_count
            )
            
            # Add question-specific enhancements
            self._enhance_validation_result(enhanced_result, question_type, new_retry_count)
            
            # Add progressive assistance if enabled and threshold reached
            if (self.config.enable_progressive_assistance and 
                new_retry_count >= self.config.max_retries_before_progressive_help):
                enhanced_result.progressive_help = self._get_progressive_help(question_type)
                enhanced_result.is_progressive_help_triggered = True
        else:
            # Reset retry count on successful validation
            self._reset_retry_count(user_id, question_type)
            
            # Create enhanced result with reset retry count
            enhanced_result = EnhancedValidationResult(
                is_valid=basic_result.is_valid,
                error_message=basic_result.error_message,
                help_message=basic_result.help_message,
                suggested_format=basic_result.suggested_format,
                retry_count=0
            )
        
        return enhanced_result
    
    def validate_age(self, age_str: str, user_id: int) -> EnhancedValidationResult:
        """Validate age input with specific error messages and help."""
        return self.validate_question_response(age_str, QuestionType.LIFESTYLE_AGE, user_id)
    
    def validate_body_fat(self, fat_str: str, user_id: int) -> EnhancedValidationResult:
        """Validate body fat percentage with specific error messages and help."""
        return self.validate_question_response(fat_str, QuestionType.LIFESTYLE_BODY_FAT, user_id)
    
    def validate_scale_response(self, response: str, question_type: QuestionType, 
                              user_id: int) -> EnhancedValidationResult:
        """Validate 1-5 scale response with specific error messages and help."""
        if question_type not in [QuestionType.AMS_SCALE, QuestionType.LIFESTYLE_SLEEP_QUALITY, 
                               QuestionType.LIFESTYLE_STRESS_LEVEL]:
            raise ValueError(f"Invalid question type for scale validation: {question_type}")
        
        return self.validate_question_response(response, question_type, user_id)
    
    def validate_yes_no(self, response: str, question_type: QuestionType, 
                       user_id: int) -> EnhancedValidationResult:
        """Validate yes/no response with specific error messages and help."""
        if question_type not in [QuestionType.ADAM_YES_NO, QuestionType.LIFESTYLE_ALCOHOL_TOBACCO]:
            raise ValueError(f"Invalid question type for yes/no validation: {question_type}")
        
        return self.validate_question_response(response, question_type, user_id)
    
    def validate_exercise_frequency(self, frequency_str: str, user_id: int) -> EnhancedValidationResult:
        """Validate exercise frequency with specific error messages and help."""
        return self.validate_question_response(frequency_str, QuestionType.LIFESTYLE_EXERCISE_FREQUENCY, user_id)
    
    def get_help_message(self, question_type: QuestionType, retry_count: int = 0) -> str:
        """
        Get context-specific help message for a question type.
        
        Args:
            question_type: Type of question
            retry_count: Number of failed attempts
            
        Returns:
            str: Help message tailored to the question type and retry count
        """
        base_help = self._get_base_help_message(question_type)
        
        if retry_count >= self.config.max_retries_before_help:
            additional_help = self._get_additional_help(question_type)
            return f"{base_help}\n\n{additional_help}"
        
        return base_help
    
    def get_format_examples(self, question_type: QuestionType) -> List[str]:
        """
        Get format examples for a specific question type.
        
        Args:
            question_type: Type of question
            
        Returns:
            List[str]: List of valid format examples
        """
        examples = {
            QuestionType.ADAM_YES_NO: ["Sí", "No", "Si", "S", "N"],
            QuestionType.AMS_SCALE: ["1", "2", "3", "4", "5"],
            QuestionType.LIFESTYLE_AGE: ["25", "30", "45", "60"],
            QuestionType.LIFESTYLE_BODY_FAT: ["15", "20", "25", "12.5"],
            QuestionType.LIFESTYLE_SLEEP_QUALITY: ["1", "2", "3", "4", "5"],
            QuestionType.LIFESTYLE_STRESS_LEVEL: ["1", "2", "3", "4", "5"],
            QuestionType.LIFESTYLE_EXERCISE_FREQUENCY: ["0", "2", "3", "5", "7"],
            QuestionType.LIFESTYLE_ALCOHOL_TOBACCO: ["Sí", "No", "Si", "S", "N"],
        }
        
        return examples.get(question_type, ["Ejemplo no disponible"])
    
    def reset_user_retries(self, user_id: int, question_type: Optional[QuestionType] = None) -> None:
        """
        Reset retry counts for a user.
        
        Args:
            user_id: User ID
            question_type: Specific question type to reset (optional, resets all if None)
        """
        if user_id in self.user_retry_counts:
            if question_type:
                self.user_retry_counts[user_id].pop(question_type, None)
            else:
                self.user_retry_counts[user_id].clear()
    
    def get_user_retry_stats(self, user_id: int) -> Dict[QuestionType, int]:
        """
        Get retry statistics for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict[QuestionType, int]: Retry counts per question type
        """
        return self.user_retry_counts.get(user_id, {}).copy()
    
    def _get_retry_count(self, user_id: int, question_type: QuestionType) -> int:
        """Get current retry count for user and question type."""
        return self.user_retry_counts.get(user_id, {}).get(question_type, 0)
    
    def _increment_retry_count(self, user_id: int, question_type: QuestionType) -> None:
        """Increment retry count for user and question type."""
        if user_id not in self.user_retry_counts:
            self.user_retry_counts[user_id] = {}
        
        current_count = self.user_retry_counts[user_id].get(question_type, 0)
        self.user_retry_counts[user_id][question_type] = current_count + 1
    
    def _reset_retry_count(self, user_id: int, question_type: QuestionType) -> None:
        """Reset retry count for user and question type."""
        if user_id in self.user_retry_counts:
            self.user_retry_counts[user_id].pop(question_type, None)
    
    def _enhance_validation_result(self, result: EnhancedValidationResult, 
                                 question_type: QuestionType, retry_count: int) -> None:
        """Enhance validation result with question-specific information."""
        # Add examples if format suggestions are enabled
        if self.config.enable_format_suggestions:
            result.examples = self.get_format_examples(question_type)
        
        # Enhance error message based on retry count
        if retry_count >= self.config.max_retries_before_help:
            result.help_message = self.get_help_message(question_type, retry_count)
        elif not result.help_message:
            # If no help message from security manager, provide basic help
            result.help_message = self._get_base_help_message(question_type)
        
        # Add specific guidance based on question type
        specific_guidance = self._get_specific_guidance(question_type, retry_count)
        if specific_guidance:
            if result.help_message:
                result.help_message += f"\n\n{specific_guidance}"
            else:
                result.help_message = specific_guidance
    
    def _get_base_help_message(self, question_type: QuestionType) -> str:
        """Get base help message for question type."""
        help_messages = {
            QuestionType.ADAM_YES_NO: (
                "Responde 'Sí' o 'No' a la pregunta.\n"
                "Respuestas válidas: Sí, Si, No, S, N"
            ),
            QuestionType.AMS_SCALE: (
                "Califica del 1 al 5 según la intensidad de los síntomas:\n"
                "1 = Ninguno\n2 = Leve\n3 = Moderado\n4 = Severo\n5 = Muy severo"
            ),
            QuestionType.LIFESTYLE_AGE: (
                "Introduce tu edad como un número entero.\n"
                "Debe estar entre 18 y 120 años."
            ),
            QuestionType.LIFESTYLE_BODY_FAT: (
                "Introduce tu porcentaje de grasa corporal estimado.\n"
                "Debe ser un número entre 0 y 50 (sin el símbolo %)."
            ),
            QuestionType.LIFESTYLE_SLEEP_QUALITY: (
                "Califica la calidad de tu sueño del 1 al 5:\n"
                "1 = Muy mala\n2 = Mala\n3 = Regular\n4 = Buena\n5 = Excelente"
            ),
            QuestionType.LIFESTYLE_STRESS_LEVEL: (
                "Califica tu nivel de estrés del 1 al 5:\n"
                "1 = Muy bajo\n2 = Bajo\n3 = Moderado\n4 = Alto\n5 = Muy alto"
            ),
            QuestionType.LIFESTYLE_EXERCISE_FREQUENCY: (
                "Introduce el número de veces por semana que haces ejercicio de fuerza.\n"
                "Debe ser un número entre 0 y 7."
            ),
            QuestionType.LIFESTYLE_ALCOHOL_TOBACCO: (
                "Responde 'Sí' o 'No' sobre si consumes alcohol o tabaco regularmente.\n"
                "Respuestas válidas: Sí, Si, No, S, N"
            ),
        }
        
        return help_messages.get(question_type, "Introduce una respuesta válida.")
    
    def _get_additional_help(self, question_type: QuestionType) -> str:
        """Get additional help for users who have failed multiple times."""
        additional_help = {
            QuestionType.ADAM_YES_NO: (
                "💡 Consejo: Si no estás seguro, piensa en tu experiencia reciente. "
                "Las preguntas ADAM se refieren a cambios que hayas notado."
            ),
            QuestionType.AMS_SCALE: (
                "💡 Consejo: Si no experimentas el síntoma, responde '1'. "
                "Si lo experimentas intensamente, responde '5'. "
                "Para síntomas moderados, usa '2', '3' o '4'."
            ),
            QuestionType.LIFESTYLE_AGE: (
                "💡 Consejo: Introduce solo números, sin letras ni símbolos. "
                "Por ejemplo: 30"
            ),
            QuestionType.LIFESTYLE_BODY_FAT: (
                "💡 Consejo: Si no conoces tu porcentaje exacto, puedes estimarlo:\n"
                "- Muy delgado: 8-12%\n- Delgado: 12-18%\n- Normal: 18-25%\n- Con sobrepeso: 25-35%"
            ),
            QuestionType.LIFESTYLE_SLEEP_QUALITY: (
                "💡 Consejo: Piensa en qué tan descansado te sientes al despertar "
                "y qué tan fácil es para ti conciliar el sueño."
            ),
            QuestionType.LIFESTYLE_STRESS_LEVEL: (
                "💡 Consejo: Considera tu nivel de estrés promedio en los últimos meses, "
                "no solo el día de hoy."
            ),
            QuestionType.LIFESTYLE_EXERCISE_FREQUENCY: (
                "💡 Consejo: Cuenta solo ejercicios de fuerza como pesas, calistenia, "
                "o entrenamientos de resistencia. No incluyas cardio."
            ),
            QuestionType.LIFESTYLE_ALCOHOL_TOBACCO: (
                "💡 Consejo: 'Regular' significa varias veces por semana. "
                "Si es ocasional (una vez al mes o menos), responde 'No'."
            ),
        }
        
        return additional_help.get(question_type, "")
    
    def _get_progressive_help(self, question_type: QuestionType) -> str:
        """Get progressive help for users who have failed many times."""
        progressive_help = {
            QuestionType.ADAM_YES_NO: (
                "🆘 Ayuda progresiva:\n"
                "Parece que tienes dificultades con esta pregunta. "
                "Simplemente escribe la letra 'S' para Sí o 'N' para No."
            ),
            QuestionType.AMS_SCALE: (
                "🆘 Ayuda progresiva:\n"
                "Escribe solo un número del 1 al 5. "
                "Si no tienes este síntoma, escribe '1'. "
                "Si lo tienes muy intenso, escribe '5'."
            ),
            QuestionType.LIFESTYLE_AGE: (
                "🆘 Ayuda progresiva:\n"
                "Escribe solo tu edad como número. "
                "Por ejemplo, si tienes treinta años, escribe: 30"
            ),
            QuestionType.LIFESTYLE_BODY_FAT: (
                "🆘 Ayuda progresiva:\n"
                "Si no estás seguro, puedes usar estos valores aproximados:\n"
                "- Muy delgado: 10\n- Delgado: 15\n- Normal: 20\n- Con sobrepeso: 30"
            ),
            QuestionType.LIFESTYLE_SLEEP_QUALITY: (
                "🆘 Ayuda progresiva:\n"
                "Escribe un número del 1 al 5:\n"
                "1 = Duermo muy mal\n3 = Duermo regular\n5 = Duermo excelente"
            ),
            QuestionType.LIFESTYLE_STRESS_LEVEL: (
                "🆘 Ayuda progresiva:\n"
                "Escribe un número del 1 al 5:\n"
                "1 = Muy poco estrés\n3 = Estrés normal\n5 = Mucho estrés"
            ),
            QuestionType.LIFESTYLE_EXERCISE_FREQUENCY: (
                "🆘 Ayuda progresiva:\n"
                "Escribe un número del 0 al 7 (días por semana).\n"
                "Si no haces ejercicio de fuerza, escribe: 0"
            ),
            QuestionType.LIFESTYLE_ALCOHOL_TOBACCO: (
                "🆘 Ayuda progresiva:\n"
                "Escribe 'S' si consumes alcohol o tabaco varias veces por semana.\n"
                "Escribe 'N' si no consumes o es muy ocasional."
            ),
        }
        
        return progressive_help.get(question_type, "")
    
    def _get_specific_guidance(self, question_type: QuestionType, retry_count: int) -> str:
        """Get specific guidance based on question type and retry count."""
        if retry_count == 2:
            return "💭 Recuerda: Solo necesitas una respuesta simple y directa."
        elif retry_count == 3:
            return "⚠️ Atención: Asegúrate de seguir exactamente el formato solicitado."
        elif retry_count >= 4:
            return "🔄 Último intento: Si sigues teniendo problemas, puedes usar /cancel para reiniciar."
        
        return ""