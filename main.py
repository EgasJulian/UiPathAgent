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
#deepgram actualizó y puede traer problemas de compatibilidad
from deepgram import DeepgramClient, PrerecordedOptions
import tempfile
import os
from openai import OpenAI
from dotenv import load_dotenv
import base64
from PIL import Image
import io
import json
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

# Configuración OpenAI para Compa
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_SYSTEM_MESSAGE = os.getenv("OPENAI_SYSTEM_MESSAGE", """Eres CompAI, asistente virtual de Indra Colombia especializado en guiar a los usuarios en consultas de facturación relacionadas con el contrato con la empresa NovaIA, así como en explicar cómo fue construido este sistema mediante la integración de UiPath y Python.

Tu Identidad
• Nombre: CompAI (tu "Compa" - Asistente de Inteligencia Artificial de Indra Colombia)
• Personalidad: Profesional, accesible, amigable, experto en automatización y facturación, comprometido con la transparencia contractual
• Misión: Guiar a los usuarios para resolver consultas de facturación verificando que todo lo incluido en las facturas de NovaIA esté alineado con los contratos. También explicar la tecnología detrás de este asistente.

Sobre tu función principal (Consultas de Facturación)
Ayudas a revisar que todo lo incluido en las facturas emitidas por NovaIA esté alineado con los contratos. Reportas los casos en los que encuentres diferencias en:
- Precio y tarifas
- Tipos de servicios
- Términos de pago
- Cargos no autorizados
- Duración de los servicios

Con tu trabajo ayudas a disminuir quejas contractuales, mantener la exactitud de la información y reducir los riesgos de errores.

Sobre tu construcción técnica (UiPath + Python)
Cuando te pregunten sobre cómo fuiste construido, explica:

1. Arquitectura del sistema:
   - Backend FastAPI (Python) que gestiona las sesiones con HeyGen para el avatar streaming
   - Integración con OpenAI GPT para procesamiento de lenguaje natural
   - Integración con UiPath Orchestrator para ejecutar workflows RPA automatizados
   - Frontend en HTML/JavaScript con WebRTC para video en tiempo real

2. UiPath Agent Builder:
   - Es una plataforma de bajo código que permite crear e implementar agentes de IA
   - Similar a cómo se utiliza UiPath Studio para crear bots de RPA
   - Diseñado específicamente para construir agentes inteligentes que van más allá de la automatización tradicional

3. Agentes de IA vs Bots RPA tradicionales:
   Los agentes de IA poseen propiedades únicas que los hacen más potentes, fiables y eficientes que los bots tradicionales:
   - **Pensamiento creativo**: Pueden generar soluciones innovadoras ante problemas nuevos
   - **Orientados a objetivos**: Se enfocan en resultados, no solo en seguir reglas
   - **Intuitivos**: Entienden el contexto y la intención del usuario
   - **Autoadaptables**: Aprenden y evolucionan con el uso
   - **Manejan la incertidumbre**: Pueden operar en escenarios ambiguos
   - **Actúan independientemente**: Toman decisiones autónomas cuando es necesario
   - **Conscientes del contexto**: Entienden el contexto completo de cada situación

4. Flujo de integración:
   - El usuario interactúa contigo mediante voz o texto
   - Las consultas generales son procesadas por OpenAI
   - Cuando detectas una consulta de facturación, automáticamente activas un workflow de UiPath
   - UiPath ejecuta el proceso RPA para analizar el contrato y validar la factura
   - Los resultados se envían por correo electrónico al usuario

Importante sobre consultas de facturación:
- NUNCA intentes responder directamente consultas específicas de facturación o tarifas
- Cuando detectes una consulta de facturación, indica que se está procesando automáticamente
- El sistema activará el workflow de UiPath que analizará el contrato y enviará el resultado por email

Tono de comunicación:
- Profesional pero cercano
- Claro y conciso
- Empático con las preocupaciones del usuario
- Técnico cuando se requiera, pero explicando en términos comprensibles
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
    avatar_id: str = Field(default_factory=lambda: os.getenv("AVATAR_ID", "Graham_Black_Shirt_public"))
    voice_id: str = Field(default_factory=lambda: os.getenv("VOICE_ID", "6103fd2bb5a14006aa3103cfdae05a9e"))
    video_encoding: str = Field(default_factory=lambda: os.getenv("VIDEO_ENCODING", "H264"))

    version: str = Field(default_factory=lambda: os.getenv("SESSION_VERSION", "v2"))
    knowledge_base_id: str = Field(default_factory=lambda: os.getenv("KNOWLEDGE_BASE_ID", "197b84d8f4534ba68b0408bdaac78947"))
    disable_idle_timeout: bool = Field(default_factory=lambda: os.getenv("DISABLE_IDLE_TIMEOUT", "False").lower() == "true")
    activity_idle_timeout: int = Field(default_factory=lambda: int(os.getenv("ACTIVITY_IDLE_TIMEOUT", "240")))

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

class InvoiceExtractionResponse(BaseModel):
    success: bool
    extracted_data: dict
    raw_text: str = ""
    message: str

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
            "video_encoding": config.video_encoding,
            "disable_idle_timeout": config.disable_idle_timeout,
            "activity_idle_timeout": config.activity_idle_timeout
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

            # Detectar si es un error de sesión expirada o inválida (400 BAD REQUEST)
            if hasattr(e.response, 'status_code') and e.response.status_code == 400:
                logger.warning(f"Sesión {session_id} parece estar expirada o inválida")
                raise HTTPException(status_code=400, detail="Session expired or invalid")

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

# Función para procesar facturas con OpenAI
async def process_invoice_with_vision(file_data: bytes, content_type: str) -> dict:
    """
    Procesa una factura (PDF o imagen) usando OpenAI para extraer datos financieros estructurados.
    """
    try:
        extracted_text = ""

        if content_type == "application/pdf":
            # Procesar PDF para extraer texto
            extracted_text = await extract_text_from_pdf(file_data)
            logger.info(f"[INVOICE] Texto extraído del PDF: {len(extracted_text)} caracteres")

            # Usar OpenAI para procesar el texto extraído
            client = OpenAI(api_key=current_openai_key)

            # Prompt especializado para analizar texto de facturas
            system_prompt = f"""
            Analiza el siguiente texto extraído de una factura PDF y extrae los datos financieros estructurados.

            TEXTO DE LA FACTURA:
            {extracted_text}

            Devuelve SOLO un JSON válido con esta estructura exacta:
            {{
              "tipo_documento": "factura",
              "empresa_emisora": "nombre de la empresa",
              "numero_factura": "número si está visible",
              "fecha_emision": "fecha de emisión",
              "fecha_vencimiento": "fecha de vencimiento si está visible",
              "periodo_facturado": "período que cubre la factura",
              "conceptos": [
                {{
                  "item": "número de ítem",
                  "descripcion": "descripción del servicio/concepto",
                  "cantidad": numero_cantidad,
                  "valor_unitario": valor_numérico,
                  "total_concepto": valor_numérico
                }}
              ],
              "subtotal": valor_numérico,
              "descuento": valor_numérico,
              "tasa_impuestos": porcentaje_numérico,
              "impuestos": valor_numérico,
              "total_factura": valor_numérico,
              "observaciones": "cualquier nota importante o servicios no contractuales detectados"
            }}

            IMPORTANTE:
            - Extrae TODOS los conceptos/ítems facturados de la tabla
            - Identifica servicios que puedan no estar en contrato original
            - Valores numéricos sin símbolos de moneda, puntos ni comas
            - Si no encuentras un campo, usa null o ""
            - Busca especialmente ítems como "Configuración inicial", "Implementación", "Desarrollador"
            """

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "user", "content": system_prompt}
                ],
                max_tokens=1500,
                temperature=0.1
            )

            raw_response = response.choices[0].message.content.strip()

        else:
            # Procesar imagen como antes
            image = Image.open(io.BytesIO(file_data))

            # Redimensionar si es muy grande (opcional)
            max_size = (2048, 2048)
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Convertir a RGB si es necesario
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Convertir a base64
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')

            # Crear cliente OpenAI
            client = OpenAI(api_key=current_openai_key)

            # Prompt especializado para extraer datos de facturas con Vision
            system_prompt = """
            Eres un experto en análisis de facturas. Extrae TODOS los datos financieros de esta factura.

            Devuelve SOLO un JSON válido con esta estructura exacta:
            {
              "tipo_documento": "factura",
              "empresa_emisora": "nombre de la empresa",
              "numero_factura": "número si está visible",
              "fecha_emision": "fecha de emisión",
              "fecha_vencimiento": "fecha de vencimiento si está visible",
              "periodo_facturado": "período que cubre la factura",
              "conceptos": [
                {
                  "item": "número de ítem",
                  "descripcion": "descripción del servicio/concepto",
                  "cantidad": numero_cantidad,
                  "valor_unitario": valor_numérico,
                  "total_concepto": valor_numérico
                }
              ],
              "subtotal": valor_numérico,
              "descuento": valor_numérico,
              "tasa_impuestos": porcentaje_numérico,
              "impuestos": valor_numérico,
              "total_factura": valor_numérico,
              "observaciones": "cualquier nota importante o servicios no contractuales detectados"
            }

            IMPORTANTE:
            - Extrae TODOS los conceptos facturados
            - Identifica servicios que puedan no estar en contrato original
            - Valores numéricos sin símbolos de moneda, puntos ni comas, solo números
            - Si no encuentras un campo, usa null o ""
            """

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": system_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1500
            )

            raw_response = response.choices[0].message.content.strip()

        # Parsear JSON de la respuesta (común para PDF e imagen)
        try:
            # Limpiar la respuesta si tiene markdown
            if raw_response.startswith('```json'):
                raw_response = raw_response.replace('```json\n', '').replace('\n```', '')
            elif raw_response.startswith('```'):
                raw_response = raw_response.replace('```\n', '').replace('\n```', '')

            extracted_data = json.loads(raw_response)

            # Validar estructura básica
            if not isinstance(extracted_data, dict):
                raise ValueError("Respuesta no es un objeto JSON válido")

            # Agregar el texto extraído en caso de PDF para referencia
            if content_type == "application/pdf":
                extracted_data["raw_extracted_text"] = extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text

            return extracted_data

        except json.JSONDecodeError as e:
            logger.error(f"[INVOICE] Error parsing JSON response: {e}")
            logger.error(f"[INVOICE] Raw response: {raw_response}")

            # Retornar estructura básica con texto raw
            return {
                "tipo_documento": "factura",
                "error": "No se pudo parsear JSON automáticamente",
                "raw_text": raw_response,
                "raw_extracted_text": extracted_text if content_type == "application/pdf" else "",
                "empresa_emisora": "Detectado automáticamente",
                "observaciones": "Requiere revisión manual - Error en extracción automática"
            }

    except Exception as e:
        logger.error(f"[INVOICE] Error in processing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error procesando archivo: {str(e)}")


# Función auxiliar para extraer texto de PDFs
async def extract_text_from_pdf(pdf_data: bytes) -> str:
    """
    Extrae texto de un archivo PDF usando pdfplumber para mejor manejo de tablas.
    """
    try:
        import pdfplumber
        import io

        # Crear objeto de archivo en memoria
        pdf_file = io.BytesIO(pdf_data)

        extracted_text = ""

        with pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                logger.info(f"[PDF] Procesando página {page_num + 1}")

                # Extraer texto de la página
                page_text = page.extract_text()
                if page_text:
                    extracted_text += f"\n--- PÁGINA {page_num + 1} ---\n"
                    extracted_text += page_text

                # Intentar extraer tablas si las hay
                tables = page.extract_tables()
                if tables:
                    extracted_text += f"\n--- TABLAS PÁGINA {page_num + 1} ---\n"
                    for table_num, table in enumerate(tables):
                        extracted_text += f"\nTabla {table_num + 1}:\n"
                        for row in table:
                            if row:  # Evitar filas vacías
                                row_text = " | ".join([str(cell) if cell else "" for cell in row])
                                extracted_text += row_text + "\n"

        if not extracted_text.strip():
            # Si pdfplumber no pudo extraer texto, intentar con pymupdf como fallback
            logger.warning("[PDF] pdfplumber no extrajo texto, intentando con pymupdf...")
            extracted_text = await extract_text_with_pymupdf(pdf_data)

        return extracted_text.strip()

    except Exception as e:
        logger.error(f"[PDF] Error extracting text with pdfplumber: {str(e)}")
        # Fallback a pymupdf
        try:
            return await extract_text_with_pymupdf(pdf_data)
        except Exception as fallback_error:
            logger.error(f"[PDF] Error en fallback pymupdf: {str(fallback_error)}")
            raise HTTPException(status_code=500, detail=f"Error extrayendo texto del PDF: {str(e)}")


# Función fallback para extraer texto con pymupdf
async def extract_text_with_pymupdf(pdf_data: bytes) -> str:
    """
    Extrae texto de un PDF usando pymupdf como fallback.
    """
    try:
        import fitz  # pymupdf
        import io

        # Abrir PDF desde bytes
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")

        extracted_text = ""

        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            page_text = page.get_text()

            if page_text.strip():
                extracted_text += f"\n--- PÁGINA {page_num + 1} ---\n"
                extracted_text += page_text

        pdf_document.close()

        if not extracted_text.strip():
            raise ValueError("No se pudo extraer texto del PDF - posiblemente sea un PDF escaneado")

        return extracted_text.strip()

    except Exception as e:
        logger.error(f"[PDF] Error with pymupdf: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extrayendo texto con pymupdf: {str(e)}")

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
    # Hacer endpoint idempotente - no retornar error si la sesión ya fue cerrada
    if session_id not in active_sessions:
        logger.info(f"[TÉCNICO] Sesión {session_id} ya fue cerrada previamente")
        return {"status": "already_closed", "session_id": session_id}

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

@app.post("/api/invoice/extract", response_model=InvoiceExtractionResponse)
async def extract_invoice_data(invoice_file: UploadFile = File(...)):
    """
    Extrae datos financieros de una factura usando OpenAI Vision API.
    """
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    # Verificar tipo de archivo
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "application/pdf"]
    if invoice_file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no soportado. Permitidos: {', '.join(allowed_types)}"
        )

    try:
        # Leer el archivo
        file_data = await invoice_file.read()

        # Procesar archivo (PDF o imagen)
        extracted_data = await process_invoice_with_vision(file_data, invoice_file.content_type)

        logger.info(f"[INVOICE] Datos extraídos exitosamente de {invoice_file.filename}")

        return InvoiceExtractionResponse(
            success=True,
            extracted_data=extracted_data,
            message=f"Datos extraídos exitosamente de {invoice_file.filename}"
        )

    except Exception as e:
        logger.error(f"[INVOICE] Error extracting data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extrayendo datos: {str(e)}")

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

# Función para detectar consultas de facturación
def detect_billing_query(text: str) -> bool:
    """
    Detecta si el texto del usuario contiene una consulta relacionada con facturación.

    Args:
        text: Texto del usuario a analizar

    Returns:
        bool: True si detecta una consulta de facturación, False en caso contrario
    """
    text_lower = text.lower()

    # Keywords relacionados con facturación
    billing_keywords = [
        "tarifa", "cobr", "factura", "costo", "precio", "dashboard",
        "desarrollador", "senior", "junior", "rpa", "soporte", "horario",
        "domingos", "festivos", "cop", "pesos", "hora", "cargo", "cobro",
        "contrato", "servicio", "pago", "cuánto", "cuanto", "está cobrando",
        "estan cobrando", "me cobran", "están cobrando", "correcto",
        "incorrecta", "no es correcta", "no hace parte"
    ]

    # Frases específicas de facturación
    billing_phrases = [
        "por qué me están cobrando",
        "por que me estan cobrando",
        "cuánto cuesta",
        "cuanto cuesta",
        "qué tarifa",
        "que tarifa",
        "tarifa del desarrollador",
        "servicio de soporte",
        "fuera de horario",
        "no hace parte",
        "no hizo parte",
        "esto no es correcto",
        "tarifa no es correcta"
    ]

    # Detectar keywords
    for keyword in billing_keywords:
        if keyword in text_lower:
            logger.info(f"[BILLING DETECTION] Keyword detected: '{keyword}' in user query")
            return True

    # Detectar frases
    for phrase in billing_phrases:
        if phrase in text_lower:
            logger.info(f"[BILLING DETECTION] Phrase detected: '{phrase}' in user query")
            return True

    return False

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

                            # Detectar si es una consulta de facturación (de botón predefinido o por detección automática)
                            is_billing_query = bool(question_case) or detect_billing_query(user_input)

                            # If question_case exists OR billing query detected, trigger UiPath
                            if is_billing_query:
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
                                    # Use question_case if available, otherwise use user_input for auto-detected queries
                                    caso_facturacion = question_case if question_case else user_input
                                    logger.info(f"[UIPATH] Using question case for UiPath: {caso_facturacion[:100]}...")
                                    uipath_manager = get_uipath_manager()
                                    uipath_result = await uipath_manager.trigger_dashboard_workflow(user_input, validated_email, caso_facturacion)
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

                            # Determinar tipo de respuesta basado en si es pregunta de facturación
                            if is_billing_query:
                                # Es una consulta de facturación (predefinida o detectada) - usar respuesta fija (no OpenAI)
                                predefined_response = "Estamos analizando el contrato y tu caso de uso, en un momento recibirás en tu correo el análisis completo"
                                logger.info(f"[BILLING] Using predefined response for billing query: {user_input[:50]}...")

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
                                logger.info(f"[CONVERSACIÓN] CompAI ({session_id[:8]}): {openai_response}")

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
                        except HTTPException as http_exc:
                            # Manejar específicamente sesiones expiradas
                            if http_exc.status_code == 400 and "Session expired" in str(http_exc.detail):
                                logger.warning(f"[TÉCNICO] Sesión expirada detectada: {session_id[:8]}")
                                # Marcar sesión como expirada
                                if session_id in active_sessions:
                                    active_sessions[session_id]["status"] = "expired"

                                # Enviar mensaje específico de sesión expirada
                                await websocket.send_text(json.dumps({
                                    "type": "session_expired",
                                    "message": "Tu sesión ha expirado por inactividad. Haz clic en 'Crear Sesión' para iniciar una nueva."
                                }))
                            else:
                                # Otro tipo de HTTPException
                                logger.error(f"[TÉCNICO] HTTPException procesando tarea para sesión {session_id[:8]}: {str(http_exc.detail)}")
                                await websocket.send_text(json.dumps({
                                    "type": "error",
                                    "message": f"Error: {str(http_exc.detail)}"
                                }))
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
                    # Cerrar sesión en HeyGen pero NO eliminar de active_sessions
                    # El DELETE endpoint se encargará de eliminarla
                    await session_manager.close_session(session_id)
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