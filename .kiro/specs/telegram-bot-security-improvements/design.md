# Design Document

## Overview

Este diseño mejora el bot de Telegram existente implementando capas de seguridad, manejo robusto de errores, configuración flexible y mejor experiencia de usuario. El diseño mantiene la funcionalidad actual mientras añade características empresariales de seguridad y monitoreo.

## Architecture

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Config        │    │   Security      │    │   Logging       │
│   Manager       │    │   Layer         │    │   System        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
┌─────────────────────────────────┼─────────────────────────────────┐
│                    Bot Core Application                           │
├─────────────────┬─────────────────┬─────────────────┬─────────────┤
│  Conversation   │   Validation    │   Persistence   │   Metrics   │
│  Handler        │   Layer         │   Manager       │   Collector │
└─────────────────┴─────────────────┴─────────────────┴─────────────┘
```

### Security Layer Architecture

```
User Input → Sanitization → Validation → Rate Limiting → Processing
     ↓              ↓            ↓            ↓            ↓
   Logging    Error Handling  Metrics   Session Mgmt   Response
```

## Components and Interfaces

### 1. Configuration Manager

**Purpose:** Centralizar toda la configuración del bot

```python
class ConfigManager:
    def load_config(self) -> BotConfig
    def get_token(self) -> str
    def get_database_config(self) -> DatabaseConfig
    def get_logging_config(self) -> LoggingConfig
    def validate_config(self) -> bool
```

**Configuration Sources Priority:**
1. Environment variables (highest)
2. .env file
3. config.yaml file
4. Default values (lowest)

### 2. Security Layer

**Purpose:** Sanitizar y validar todas las entradas del usuario

```python
class SecurityManager:
    def sanitize_input(self, text: str) -> str
    def validate_input(self, text: str, input_type: InputType) -> ValidationResult
    def check_rate_limit(self, user_id: int) -> bool
    def log_security_event(self, event: SecurityEvent) -> None
```

**Input Validation Rules:**
- Edad: 18-120 años
- Grasa corporal: 0-50%
- Escalas 1-5: Solo números enteros
- Texto libre: Máximo 100 caracteres, sin HTML/scripts

### 3. Enhanced Conversation Handler

**Purpose:** Mejorar el flujo de conversación con persistencia y recuperación

```python
class EnhancedConversationHandler:
    def save_progress(self, user_id: int, state: ConversationState) -> None
    def load_progress(self, user_id: int) -> Optional[ConversationState]
    def handle_timeout(self, user_id: int) -> None
    def show_progress(self, user_id: int) -> str
```

**State Management:**
- Estados guardados en memoria con TTL de 24 horas
- Progreso mostrado como "Pregunta X de Y"
- Recuperación automática al reiniciar conversación

### 4. Validation Layer

**Purpose:** Validación específica por tipo de pregunta

```python
class ValidationLayer:
    def validate_age(self, age_str: str) -> ValidationResult
    def validate_body_fat(self, fat_str: str) -> ValidationResult
    def validate_scale_response(self, response: str) -> ValidationResult
    def validate_yes_no(self, response: str) -> ValidationResult
    def get_help_message(self, question_type: QuestionType) -> str
```

**Validation Features:**
- Mensajes de error específicos por tipo
- Sugerencias de formato correcto
- Límites de reintentos con ayuda escalada

### 5. Logging System

**Purpose:** Sistema de logging estructurado y rotativo

```python
class LoggingSystem:
    def setup_loggers(self) -> None
    def log_user_action(self, user_id: int, action: str) -> None
    def log_error(self, error: Exception, context: dict) -> None
    def log_security_event(self, event: SecurityEvent) -> None
    def rotate_logs(self) -> None
```

**Log Levels:**
- INFO: Acciones normales del usuario
- WARNING: Entradas inválidas, reintentos
- ERROR: Errores de sistema, fallos de conexión
- CRITICAL: Eventos de seguridad, fallos críticos

### 6. Persistence Manager

**Purpose:** Gestionar datos temporales del usuario

```python
class PersistenceManager:
    def save_user_data(self, user_id: int, data: UserData) -> None
    def load_user_data(self, user_id: int) -> Optional[UserData]
    def cleanup_expired_data(self) -> None
    def get_user_progress(self, user_id: int) -> ProgressInfo
```

**Storage Strategy:**
- Datos en memoria con respaldo en archivo JSON
- TTL de 24 horas para datos de conversación
- Limpieza automática cada hora

### 7. Metrics Collector

**Purpose:** Recopilar métricas anónimas de uso

```python
class MetricsCollector:
    def record_conversation_start(self) -> None
    def record_conversation_complete(self, duration: int) -> None
    def record_question_response_time(self, question_type: str, time: float) -> None
    def record_error(self, error_type: str) -> None
    def generate_report(self) -> MetricsReport
```

**Metrics Tracked:**
- Conversaciones iniciadas/completadas
- Tiempo promedio por cuestionario
- Errores más comunes
- Patrones de abandono

## Data Models

### Configuration Models

```python
@dataclass
class BotConfig:
    token: str
    debug_mode: bool
    max_retries: int
    timeout_minutes: int
    rate_limit_per_minute: int

@dataclass
class DatabaseConfig:
    file_path: str
    backup_interval: int
    max_file_size: int

@dataclass
class LoggingConfig:
    level: str
    file_path: str
    max_file_size: int
    backup_count: int
```

### User Data Models

```python
@dataclass
class UserProgress:
    user_id: int
    current_state: ConversationState
    adam_answers: List[bool]
    ams_score: int
    ams_question_index: int
    lifestyle_answers: Dict[str, Any]
    lifestyle_question_index: int
    start_time: datetime
    last_activity: datetime

@dataclass
class ValidationResult:
    is_valid: bool
    error_message: Optional[str]
    help_message: Optional[str]
    suggested_format: Optional[str]
```

### Security Models

```python
@dataclass
class SecurityEvent:
    user_id: int
    event_type: SecurityEventType
    description: str
    timestamp: datetime
    severity: SecuritySeverity

@dataclass
class RateLimitInfo:
    user_id: int
    requests_count: int
    window_start: datetime
    is_blocked: bool
```

## Error Handling

### Error Categories

1. **Network Errors**
   - Automatic retry with exponential backoff
   - Maximum 3 retries
   - Graceful degradation

2. **User Input Errors**
   - Specific validation messages
   - Help suggestions
   - Progressive assistance

3. **System Errors**
   - Logged with full context
   - User-friendly error messages
   - Automatic recovery when possible

4. **Security Errors**
   - Immediate logging
   - Rate limiting activation
   - Alert generation

### Error Recovery Strategies

```python
class ErrorHandler:
    def handle_network_error(self, error: NetworkError) -> RecoveryAction
    def handle_validation_error(self, error: ValidationError) -> UserMessage
    def handle_system_error(self, error: SystemError) -> RecoveryAction
    def handle_security_error(self, error: SecurityError) -> SecurityAction
```

## Testing Strategy

### Unit Tests
- Configuration loading and validation
- Input sanitization and validation
- Conversation state management
- Metrics collection accuracy

### Integration Tests
- End-to-end conversation flows
- Error handling scenarios
- Security validation
- Persistence operations

### Security Tests
- Input injection attempts
- Rate limiting effectiveness
- Data sanitization verification
- Authentication bypass attempts

### Performance Tests
- Response time under load
- Memory usage with multiple users
- Database performance
- Log file rotation

## Security Considerations

### Input Security
- All user input sanitized before processing
- SQL injection prevention (if database added)
- XSS prevention in logged data
- Command injection prevention

### Data Protection
- No sensitive data stored permanently
- Automatic data cleanup
- Encrypted logs for sensitive events
- GDPR compliance for EU users

### Rate Limiting
- Maximum 10 requests per minute per user
- Progressive delays for repeated violations
- Temporary blocking for severe violations
- Whitelist for admin users

### Monitoring
- Real-time security event detection
- Automated alerts for suspicious activity
- Regular security audit logs
- Compliance reporting

## Deployment Considerations

### Environment Configuration
- Separate configs for dev/staging/prod
- Environment-specific logging levels
- Secure token management
- Health check endpoints

### Monitoring and Alerting
- Application health monitoring
- Error rate alerting
- Performance metrics tracking
- Security event notifications

### Backup and Recovery
- Automated configuration backups
- Log file archival
- Disaster recovery procedures
- Data retention policies