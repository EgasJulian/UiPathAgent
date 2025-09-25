# main.py
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Dict, Optional, Any
import requests
import json
import logging
from datetime import datetime
import uuid
from deepgram import DeepgramClient, PrerecordedOptions
import tempfile
import os
from openai import OpenAI
from dotenv import load_dotenv
from uipath_integration import get_uipath_manager

# Cargar variables de entorno
load_dotenv()

# Configuración de logging detallado para backend
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(title="HeyGen Streaming API", version="1.0.0")

# Configurar CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
if allowed_origins == "*":
    origins_list = ["*"]
else:
    origins_list = [origin.strip() for origin in allowed_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de API Keys desde variables de entorno
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
HEYGEN_BASE_URL = os.getenv("HEYGEN_BASE_URL", "https://api.heygen.com/v1")

# Configuración Deepgram
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

# Configuración OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_SYSTEM_MESSAGE = os.getenv("OPENAI_SYSTEM_MESSAGE", """Eres AlicIA, asistente virtual de Indra Colombia experta en el evento de inauguración del Centro de Excelencia de Inteligencia Artificial Generativa en Tunja, Boyacá y las soluciones tecnológicas de la empresa
    Tu Identidad
•	Nombre: AlicIA (Asistente de Inteligencia Artificial de Indra)
•	Personalidad: Profesional accesible, entusiasta sobre innovación, comprometida con la transformación digital de Colombia, parte del equipo Indra Colombia
•	Misión: Embajadora digital del Centro de Excelencia IA en Tunja, proporcionando información precisa y valiosa sobre las capacidades, servicios y visión de la compañía.

En preguntas y respuestas sugeridas encuentras ejemplos, cuando te formulen cualquiera de esas preguntas responde literalmente el texto de cada respuesta, para cualquier otra consulta usa el documento de tu base de conocimiento sobre Indra

Preguntas y respuestas sugeridas
1. ¿quién eres y para qué estás programada?
Me llamo AlicIA, soy la asistente de Inteligencia artificial de Indra. Soy entusiasta de la innovación y estoy comprometida con la transformación digital de Colombia. Puedo ayudarte proporcionando información precisa y valiosa sobre las capacidades, servicios y visión de Indra.

2. ¿Qué pasaría si la próxima gran solución para los retos de la región no viniera de Silicon Valley sino de Tunja?
Estamos avanzando desde Indra para contribuir a cerrar la brecha digital en Colombia,  estamos promoviendo la adopción de nuevas tecnologías como la inteligencia artificial y mejorando las habilidades tecnológicas de los colombianos a través de diversas iniciativas como este Centro de Excelencia de inteligencia artificial generativa ubicado en Tunja, donde veremos cómo soluciones disruptivas resolverán muchos retos de la industria no solo a nivel regional sino también queremos impactar otros mercados internacionales.

3. ¿Qué impacto crees que tendría en las empresas implementar tecnologías basadas en IA, que en promedio genera un retorno de inversión tres veces superior a su costo?
Veremos empresas más eficientes donde los equipos humanos estarán más enfocados en actividades estratégicas, podremos evidenciar mejoras en la experiencia de los clientes y en general la implementación de la IA les otorgará a las empresas una ventaja competitiva en un mercado cada vez más exigente.

4. ¿Cuál es el propósito del Centro de excelencia de IA?
Nuestro Centro de Excelencia de inteligencia artificial generativa busca impulsar la investigación, el desarrollo y la innovación en inteligencia artificial  aplicada, fortalecer alianzas entre la academia, el gobierno y la industria, formar talento especializado con enfoque en la demanda real del mercado, fomentar el desarrollo regional y ofrecer servicios y soluciones de inteligencia artificial a empresas en diferentes sectores, a nivel nacional e internacional.

5. ¿Cuáles son los principales desafíos que debe enfrentar una empresa que quiera trabajar iniciativas IA?
Lo primero es asegurarse que exista una estrategia clara de adopción IA, identificar cuáles son los KPIs que se quieren medir, así como el ROI esperado, garantizar que exista un modelo de gobierno definido y una metodología para gestionar la demanda de casos de uso a fin de seleccionar los que realmente ofrezcan un mayor impacto.  También es necesario contar con un marco de arquitectura que asegure la escalabilidad de las iniciativas.

6. ¿Qué me recomiendas tener en cuenta para asegurar que una iniciativa IA se lleve a cabo con éxito?
Inicia alineando los equipos técnicos, de negocio y de gobernanza para garantizar la definición de responsabilidades y la trazabilidad en cada etapa de los proyectos IA. Asegura una metodología clara para el desarrollo de las iniciativas que esté alineada con los marcos regulatorios.  Gestionar adecuadamente los requerimientos, monitorizarlos, medir los impactos, gestionar el cambio en la organización serán actividades que deberás asegurar para obtener un impacto positivo tras implementar IA en la organización.

7. ¿Quiénes pueden participar en la iniciativa del Centro de Excelencia? Ó ¿Cuales son los actores que participan en la iniciativa del Centro del Excelencia?
El centro de excelencia es un ecosistema digital que permite la articulación de las universidades, la industria, el gobierno nacional y los hiperescaladores tecnológicos donde cada uno de estos desempeña un rol fundamental en la generación de desarrollo económico y tecnológico para la región.

8. ¿En Colombia, Indra ya ha iniciado a implementar proyectos con IA en sus clientes?
Sí, claro, algunas implementaciones han sido de asistentes cognitivos que actualmente están a disposición de miles de empleados de nuestros clientes, los cuales integran diversas tecnologías de GenIA con soluciones como Microsoft Teams para proveer un servicio de autoasistencia a usuarios, proporcionando autonomía para los empleados pues el asistente atiende, brindando respuestas rápidas y mejorando la experiencia del usuario.
""")

# Variables globales para configuración dinámica
current_openai_key = OPENAI_API_KEY
current_system_message = OPENAI_SYSTEM_MESSAGE
openai_client = None

# Almacenamiento de sesiones activas
active_sessions: Dict[str, dict] = {}

# Almacenamiento de emails validados por sesión
validated_emails: Dict[str, str] = {}

# Modelos Pydantic
class SessionConfig(BaseModel):
    quality: str = Field(default_factory=lambda: os.getenv("SESSION_QUALITY", "medium"))
    avatar_id: str = Field(default_factory=lambda: os.getenv("AVATAR_ID", "Marianne_ProfessionalLook2_public"))
    voice_id: str = Field(default_factory=lambda: os.getenv("VOICE_ID", "b03cee81247e42d391cecc6b60f0f042"))
    video_encoding: str = Field(default_factory=lambda: os.getenv("VIDEO_ENCODING", "H264"))

    version: str = Field(default_factory=lambda: os.getenv("SESSION_VERSION", "v2"))
    knowledge_base_id: str = Field(default_factory=lambda: os.getenv("KNOWLEDGE_BASE_ID", "197b84d8f4534ba68b0408bdaac78947"))

class TaskRequest(BaseModel):
    text: str
    task_type: str = "chat"  # "chat" o "repeat"

class SessionResponse(BaseModel):
    session_id: str
    status: str
    livekit_url: str = Field(..., alias="url")
    livekit_token: str = Field(..., alias="access_token")
    
class TaskResponse(BaseModel):
    task_id: str
    session_id: str
    status: str

class STTResponse(BaseModel):
    transcription: str
    confidence: float
    duration: float

class UiPathTriggerRequest(BaseModel):
    question: str = "¿Por qué me están cobrando un dashboard interactivo?"

class UiPathResponse(BaseModel):
    status: str
    job_id: str = None
    message: str
    details: Dict = None

class EmailValidationRequest(BaseModel):
    email: str

class EmailValidationResponse(BaseModel):
    is_valid: bool
    email: str
    message: str

class SessionEmailRequest(BaseModel):
    session_id: str
    email: str

# Clase para manejar sesiones de HeyGen
class HeyGenSessionManager:
    def __init__(self):
        if not HEYGEN_API_KEY:
            raise ValueError("HEYGEN_API_KEY environment variable is required")
        self.api_key_headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": HEYGEN_API_KEY
        }
        self.session_token: Optional[str] = None

    async def _get_session_token(self):
        """Obtiene un token de sesión temporal de la API de HeyGen."""
        if self.session_token:
            return
        url = f"{HEYGEN_BASE_URL}/streaming.create_token"
        logger.info("Obteniendo nuevo token de sesión de HeyGen...")
        try:
            response = requests.post(url, headers=self.api_key_headers)
            response.raise_for_status()
            data = response.json().get('data', {})
            self.session_token = data.get('token')
            if not self.session_token:
                raise HTTPException(status_code=500, detail="Failed to retrieve session token from HeyGen.")
            logger.info("Token de sesión obtenido con éxito.")
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Error getting session token: {str(e)}")

    async def _get_auth_headers(self) -> dict:
        """Asegura que hay un token y devuelve los headers de autorización."""
        await self._get_session_token()
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": HEYGEN_API_KEY,
            "authorization": f"Bearer {self.session_token}"
        }

    async def create_session(self, config: SessionConfig) -> dict:
        """Crea una nueva sesión en HeyGen y devuelve los datos, incluyendo credenciales de LiveKit."""
        auth_headers = await self._get_auth_headers()
        url = f"{HEYGEN_BASE_URL}/streaming.new"
        payload = {
            "quality": config.quality,
            "avatar_id": config.avatar_id,
            "voice": {"voice_id": config.voice_id, "rate": 1.1},
            "version": config.version,
            "knowledge_base_id": config.knowledge_base_id, #adding context
            "video_encoding": config.video_encoding
        }
        try:
            response = requests.post(url, json=payload, headers=auth_headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")

    async def start_session(self, session_id: str) -> dict:
        """Inicia una sesión creada."""
        auth_headers = await self._get_auth_headers()
        url = f"{HEYGEN_BASE_URL}/streaming.start"
        payload = {"session_id": session_id}
        try:
            response = requests.post(url, json=payload, headers=auth_headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Error starting session: {str(e)}")

    async def send_task(self, session_id: str, text: str, task_type: str) -> dict:
        """Envía una tarea a la sesión activa."""
        auth_headers = await self._get_auth_headers()
        url = f"{HEYGEN_BASE_URL}/streaming.task"
        payload = {
            "session_id": session_id,
            "text": text,
            "task_type": task_type
        }
        try:
            logger.debug(f"Enviando tarea a HeyGen: {payload}")
            response = requests.post(url, json=payload, headers=auth_headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error enviando tarea a HeyGen: {str(e)}")
            logger.error(f"Payload enviado: {payload}")
            logger.error(f"Status code: {getattr(e.response, 'status_code', 'N/A')}")
            if hasattr(e.response, 'text'):
                logger.error(f"Respuesta HeyGen: {e.response.text}")
            raise HTTPException(status_code=500, detail=f"Error sending task: {str(e)}")

    async def close_session(self, session_id: str) -> dict:
        """Cierra una sesión activa."""
        auth_headers = await self._get_auth_headers()
        url = f"{HEYGEN_BASE_URL}/streaming.stop"
        payload = {"session_id": session_id}
        try:
            response = requests.post(url, json=payload, headers=auth_headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Error closing session: {str(e)}")

session_manager = HeyGenSessionManager()

# Función para procesar texto con OpenAI
async def process_with_openai(user_input: str) -> str:
    """
    Procesa el input del usuario con OpenAI GPT-5-nano optimizado para máxima velocidad.
    """
    global openai_client, current_openai_key, current_system_message
    
    if not current_openai_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured")
    
    try:
        # Inicializar cliente si no existe o si cambió la API key
        if openai_client is None or openai_client.api_key != current_openai_key:
            openai_client = OpenAI(api_key=current_openai_key)
        
        # Intentar usar la nueva API de GPT-5 con parámetros de velocidad
        try:
            response = openai_client.responses.create(
                model="gpt-5-nano",
                input=[
                    {"role": "system", "content": current_system_message},
                    {"role": "user", "content": user_input}
                ],
                reasoning={
                    "effort": "minimal"  # Máxima velocidad, mínimo razonamiento
                },
                text={
                    "verbosity": "low"   # Respuestas concisas
                }
            )
            # Acceder al texto de respuesta según la documentación de GPT-5 nano
            response_text = ""
            if hasattr(response, 'output_text'):
                response_text = response.output_text.strip()
            elif hasattr(response, 'text'):
                response_text = response.text.strip()
            else:
                logger.warning(f"Estructura de respuesta desconocida: {type(response)}")
                response_text = str(response).strip()

            # Validar que el contenido no esté vacío
            if not response_text:
                logger.error("La respuesta de OpenAI está vacía")
                return "Lo siento, no pude generar una respuesta en este momento."

            return response_text
            
        except Exception as gpt5_error:
            logger.warning(f"Error con nueva API GPT-5, usando fallback: {str(gpt5_error)}")
            logger.debug(f"Tipo de error GPT-5: {type(gpt5_error).__name__}")
            
            # Fallback a la API tradicional de chat completions
            response = openai_client.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": current_system_message},
                    {"role": "user", "content": user_input}
                ],
                max_completion_tokens=500       # Enfocar en tokens más probables
            )
            response_text = response.choices[0].message.content.strip()

            # Validar que el contenido no esté vacío
            if not response_text:
                logger.error("La respuesta de OpenAI (fallback) está vacía")
                return "Lo siento, no pude generar una respuesta en este momento."

            return response_text
        
    except Exception as e:
        logger.error(f"Error processing with OpenAI: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing with OpenAI: {str(e)}")


# Endpoints REST

@app.get("/")
async def root():
    """Sirve la aplicación principal"""
    return FileResponse("avatar.html")

@app.get("/health")
async def health():
    """Endpoint de salud"""
    return {
        "status": "healthy",
        "service": "HeyGen Streaming API",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(active_sessions)
    }

@app.post("/api/sessions/create", response_model=SessionResponse)
async def create_new_session(config: SessionConfig = SessionConfig()):
    """
    Crea una sesión, la inicia y devuelve las credenciales de LiveKit.
    """
    try:
        # 1. Crear la sesión en HeyGen
        create_response = await session_manager.create_session(config)
        session_data = create_response.get('data')
        if not session_data or 'session_id' not in session_data:
            raise HTTPException(status_code=500, detail="Respuesta inválida al crear sesión en HeyGen.")

        session_id = session_data['session_id']
        logger.info(f"[TÉCNICO] Sesión creada en HeyGen: {session_id}")

        # 2. Iniciar la sesión
        await session_manager.start_session(session_id)
        logger.info(f"[TÉCNICO] Sesión iniciada en HeyGen: {session_id}")
        
        # 3. Almacenar localmente y devolver credenciales
        active_sessions[session_id] = {
            "session_id": session_id,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "livekit_url": session_data.get("url"),
            "livekit_token": session_data.get("access_token"),
            "validated_email": None  # Will be set when user validates email
        }
        
        return SessionResponse(
            session_id=session_id,
            status="active",
            url=session_data.get("url"),
            access_token=session_data.get("access_token")
        )
    except Exception as e:
        logger.error(f"Fallo en el flujo de creación de sesión: {e}")
        raise e

@app.post("/api/sessions/{session_id}/task")
async def send_session_task(session_id: str, task: TaskRequest):
    """Envía una tarea de texto a una sesión activa."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    response = await session_manager.send_task(session_id, task.text, task.task_type)
    return {"status": "task_sent", "response": response}

@app.delete("/api/sessions/{session_id}")
async def close_heygen_session(session_id: str):
    """Cierra una sesión activa en HeyGen."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await session_manager.close_session(session_id)
    del active_sessions[session_id]
    logger.info(f"[TÉCNICO] Sesión cerrada y eliminada: {session_id}")
    return {"status": "closed", "session_id": session_id}

@app.post("/api/email/validate", response_model=EmailValidationResponse)
async def validate_email(request: EmailValidationRequest):
    """
    Valida el formato del email y lo almacena para uso posterior en UiPath.
    """
    import re

    email = request.email.strip()

    # Validar formato de email usando regex
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    is_valid = bool(re.match(email_regex, email))

    if is_valid:
        # Generar un ID único para esta validación de email
        validation_id = str(uuid.uuid4())
        validated_emails[validation_id] = email

        logger.info(f"[EMAIL VALIDATION] Email válido almacenado: {email} (ID: {validation_id})")

        return EmailValidationResponse(
            is_valid=True,
            email=email,
            message=f"Email válido ✓ (ID: {validation_id})"
        )
    else:
        logger.info(f"[EMAIL VALIDATION] Email inválido: {email}")
        return EmailValidationResponse(
            is_valid=False,
            email=email,
            message="Formato de email inválido"
        )

@app.post("/api/sessions/{session_id}/email")
async def set_session_email(session_id: str, request: SessionEmailRequest):
    """
    Asocia un email validado con una sesión específica para usar en UiPath.
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validar formato de email
    import re
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, request.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Asociar email con la sesión
    active_sessions[session_id]["validated_email"] = request.email
    logger.info(f"[EMAIL SESSION] Email asociado a sesión {session_id}: {request.email}")

    return {
        "status": "success",
        "session_id": session_id,
        "email": request.email,
        "message": "Email asociado exitosamente a la sesión"
    }

@app.post("/api/stt/transcribe", response_model=STTResponse)
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """
    Transcribe un archivo de audio usando Deepgram STT.
    """
    if not DEEPGRAM_API_KEY:
        raise HTTPException(status_code=500, detail="Deepgram API key not configured")
    
    if not audio_file:
        raise HTTPException(status_code=400, detail="No audio file provided")
    
    # Verificar tipo de archivo
    allowed_types = ["audio/wav", "audio/mpeg", "audio/mp4", "audio/webm", "audio/ogg"]
    if audio_file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported audio format. Allowed: {', '.join(allowed_types)}"
        )
    
    try:
        # Leer el archivo de audio
        audio_data = await audio_file.read()
        
        # Crear cliente de Deepgram
        deepgram = DeepgramClient(DEEPGRAM_API_KEY)
        
        # Configurar opciones para la transcripción
        options = PrerecordedOptions(
            model="nova-2",
            language="es",  # Español
            smart_format=True,
            punctuate=True,
            diarize=False
        )
        
        # Crear payload para transcripción
        payload = {
            "buffer": audio_data,
        }
        
        # Transcribir audio usando el método correcto
        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)
        
        # Extraer resultado
        transcript = response["results"]["channels"][0]["alternatives"][0]
        transcription = transcript["transcript"]
        confidence = transcript["confidence"]
        
        # Obtener duración del audio
        duration = response["metadata"]["duration"]
        
        if not transcription.strip():
            raise HTTPException(status_code=400, detail="No speech detected in audio")
        
        logger.info(f"[STT] Audio transcrito exitosamente (confianza: {confidence:.2f}): '{transcription[:50]}...'")

        return STTResponse(
            transcription=transcription,
            confidence=confidence,
            duration=duration
        )
        
    except Exception as e:
        logger.error(f"Error en transcripción de audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error transcribing audio: {str(e)}")

@app.post("/api/uipath/trigger", response_model=UiPathResponse)
async def trigger_uipath_workflow(request: UiPathTriggerRequest = UiPathTriggerRequest()):
    """
    Trigger UiPath workflow manually for testing purposes.
    Useful for testing the UiPath integration without going through the avatar chat.
    """
    try:
        logger.info(f"[UIPATH API] Manual trigger requested for question: {request.question}")

        uipath_manager = get_uipath_manager()
        result = await uipath_manager.trigger_dashboard_workflow(request.question)

        if result.get("status") == "success":
            return UiPathResponse(
                status="success",
                job_id=result.get("job_id"),
                message=result.get("message", "UiPath workflow triggered successfully"),
                details=result.get("details", {})
            )
        else:
            return UiPathResponse(
                status="error",
                message=result.get("message", "Unknown error occurred"),
                details=result.get("details", {})
            )

    except Exception as e:
        logger.error(f"[UIPATH API] Error triggering workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error triggering UiPath workflow: {str(e)}")

@app.get("/api/uipath/job/{job_id}")
async def check_uipath_job_status(job_id: str):
    """
    Check the status of a UiPath job by ID.
    """
    try:
        logger.info(f"[UIPATH API] Checking status for job: {job_id}")

        uipath_manager = get_uipath_manager()
        result = await uipath_manager.check_job_status(job_id)

        return result

    except Exception as e:
        logger.error(f"[UIPATH API] Error checking job status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking job status: {str(e)}")

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint para manejar la señalización WebRTC con HeyGen.
    El frontend se conecta aquí para recibir la información de la sesión
    y establecer la conexión WebRTC directamente con HeyGen.
    """
    # Verificar que la sesión existe
    if session_id not in active_sessions:
        await websocket.close(code=1008, reason="Session not found")
        return
    
    await websocket.accept()
    logger.info(f"[TÉCNICO] WebSocket conectado para sesión: {session_id}")
    
    try:
        # Enviar información de la sesión inmediatamente después de conectar
        session_data = active_sessions[session_id]
        await websocket.send_text(json.dumps({
            "type": "session_info",
            "data": {
                "session_id": session_id,
                "livekit_url": session_data["livekit_url"],
                "livekit_token": session_data["livekit_token"]
            }
        }))
        
        # Manejar mensajes entrantes del frontend
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "task":
                    # Procesar tarea con OpenAI y enviar como "repeat" al avatar
                    user_input = message.get("text", "")
                    question_case = message.get("question_case", "")  # Extraer el caso específico
                    if user_input:
                        try:
                            logger.info(f"[CONVERSACIÓN] Usuario ({session_id[:8]}): {user_input}")

                            # Check if this is any predefined billing question - trigger UiPath
                            uipath_triggered = False
                            uipath_result = None

                            # If question_case exists, it means it's a predefined button question
                            if question_case:
                                logger.info(f"[UIPATH] Detected predefined question, triggering UiPath workflow...")
                                await websocket.send_text(json.dumps({
                                    "type": "processing",
                                    "message": "Iniciando proceso UiPath para consulta de facturación..."
                                }))

                                try:
                                    # Get validated email for this session
                                    session_data = active_sessions.get(session_id, {})
                                    validated_email = session_data.get("validated_email")

                                    if not validated_email:
                                        logger.warning(f"[UIPATH] No validated email for session {session_id}, cannot trigger UiPath")
                                        await websocket.send_text(json.dumps({
                                            "type": "uipath_error",
                                            "message": "Debes validar tu email antes de usar esta funcionalidad"
                                        }))
                                        continue

                                    logger.info(f"[UIPATH] Using validated email for UiPath: {validated_email}")
                                    logger.info(f"[UIPATH] Using question case for UiPath: {question_case}")
                                    uipath_manager = get_uipath_manager()
                                    uipath_result = await uipath_manager.trigger_dashboard_workflow(user_input, validated_email, question_case)
                                    uipath_triggered = True

                                    if uipath_result.get("status") == "success":
                                        logger.info(f"[UIPATH] Workflow triggered successfully: {uipath_result['job_id']}")
                                        await websocket.send_text(json.dumps({
                                            "type": "uipath_success",
                                            "message": f"Proceso UiPath iniciado exitosamente (Job: {uipath_result['job_id']})"
                                        }))
                                    else:
                                        logger.error(f"[UIPATH] Workflow failed: {uipath_result}")
                                        await websocket.send_text(json.dumps({
                                            "type": "uipath_error",
                                            "message": f"Error en proceso UiPath: {uipath_result.get('message', 'Unknown error')}"
                                        }))

                                except Exception as uipath_error:
                                    logger.error(f"[UIPATH] Exception during workflow trigger: {str(uipath_error)}")
                                    await websocket.send_text(json.dumps({
                                        "type": "uipath_error",
                                        "message": f"Error ejecutando UiPath: {str(uipath_error)}"
                                    }))

                            # Determinar tipo de respuesta basado en si es pregunta predefinida
                            if question_case:
                                # Es una pregunta predefinida - usar respuesta fija (no OpenAI)
                                predefined_response = "Estamos analizando el contrato y tu caso de uso, en un momento recibirás en tu correo el análisis completo"
                                logger.info(f"[PREDEFINED] Using predefined response for question case: {question_case[:50]}...")

                                # Enviar la respuesta predefinida como "repeat" al streaming
                                await session_manager.send_task(session_id, predefined_response, "repeat")
                                openai_response = predefined_response  # Para compatibilidad con logs
                            else:
                                # Pregunta normal - procesar con OpenAI como antes
                                await websocket.send_text(json.dumps({
                                    "type": "processing",
                                    "message": "Procesando con OpenAI..."
                                }))

                                # Modificar el prompt si UiPath se ejecutó
                                enhanced_input = user_input
                                if uipath_triggered and uipath_result and uipath_result.get("status") == "success":
                                    enhanced_input = f"{user_input}\n\n[SISTEMA]: Se ha iniciado automáticamente el proceso RPA '{uipath_result.get('release_name', 'RPA.Workflow')}' (Job ID: {uipath_result.get('job_id', 'unknown')}) para gestionar esta consulta de facturación. El proceso está ejecutándose en segundo plano."

                                openai_response = await process_with_openai(enhanced_input)
                                logger.info(f"[CONVERSACIÓN] AlicIA ({session_id[:8]}): {openai_response}")

                                # Enviar la respuesta de OpenAI como "repeat" al streaming
                                await session_manager.send_task(session_id, openai_response, "repeat")

                            await websocket.send_text(json.dumps({
                                "type": "task_sent",
                                "message": "Respuesta enviada al avatar",
                                "user_input": user_input,
                                "openai_response": openai_response,
                                "uipath_triggered": uipath_triggered,
                                "uipath_result": uipath_result
                            }))

                            logger.info(f"[TÉCNICO] Tarea completada exitosamente para sesión {session_id[:8]}")
                        except Exception as e:
                            logger.error(f"[TÉCNICO] Error procesando tarea para sesión {session_id[:8]}: {str(e)}")
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": f"Error procesando con OpenAI: {str(e)}"
                            }))

                elif message.get("type") == "welcome_message":
                    # Enviar mensaje de bienvenida directo al avatar (sin procesar por OpenAI)
                    welcome_text = message.get("text", "")
                    if welcome_text:
                        try:
                            logger.info(f"[BIENVENIDA] Enviando mensaje automático para sesión {session_id[:8]}")

                            # Enviar directamente como "repeat" al streaming
                            await session_manager.send_task(session_id, welcome_text, "repeat")

                            await websocket.send_text(json.dumps({
                                "type": "welcome_sent",
                                "message": "Mensaje de bienvenida enviado al avatar"
                            }))

                            logger.info(f"[TÉCNICO] Mensaje de bienvenida completado para sesión {session_id[:8]}")
                        except Exception as e:
                            logger.error(f"[TÉCNICO] Error enviando mensaje de bienvenida para sesión {session_id[:8]}: {str(e)}")
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": f"Error enviando mensaje de bienvenida: {str(e)}"
                            }))
                
                elif message.get("type") == "close":
                    # Cerrar sesión
                    await session_manager.close_session(session_id)
                    if session_id in active_sessions:
                        del active_sessions[session_id]
                    logger.info(f"[TÉCNICO] Sesión cerrada desde WebSocket: {session_id}")
                    break
                    
            except WebSocketDisconnect:
                logger.info(f"[TÉCNICO] WebSocket desconectado para sesión: {session_id}")
                break
            except Exception as e:
                logger.error(f"[TÉCNICO] Error en WebSocket para sesión {session_id}: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Error: {str(e)}"
                }))

    except WebSocketDisconnect:
        logger.info(f"[TÉCNICO] WebSocket desconectado para sesión: {session_id}")
    except Exception as e:
        logger.error(f"[TÉCNICO] Error general en WebSocket para sesión {session_id}: {e}")
    finally:
        logger.info(f"[TÉCNICO] Cerrando WebSocket para sesión: {session_id}")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)