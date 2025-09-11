# main.py
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
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

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(title="HeyGen Streaming API", version="1.0.0")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica los dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración DPG 11b6db766d44511819db6728f429908475aa01f3
HEYGEN_API_KEY = "MTVmMmU5ZWFmMjE5NDkwYTg0YjNjN2I0MjFhZTZiODQtMTc1NjczODk5Mw=="  #PAT rt_4895A464AEE32CA8DCB0D227E303B6441E83632296DCBD4D9ABBA79C7C8C7E2E-1
HEYGEN_BASE_URL = "https://api.heygen.com/v1"

# Configuración Deepgram - Pegar aquí tu API KEY
DEEPGRAM_API_KEY = "11b6db766d44511819db6728f429908475aa01f3"  # Deepgram API Key aquí

# Almacenamiento de sesiones activas
active_sessions: Dict[str, dict] = {}

# Modelos Pydantic
class SessionConfig(BaseModel):
    quality: str = "medium"
    avatar_id: str = "Marianne_ProfessionalLook2_public" #"Abigail_expressive_2024112501"
    voice_id: str = "253dc1d148f2410a860bc28996b30621"
    video_encoding: str = "H264"
    version: str = "v2"
    knowledge_base_id : str = "197b84d8f4534ba68b0408bdaac78947"

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

# Clase para manejar sesiones de HeyGen
class HeyGenSessionManager:
    def __init__(self):
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
            "voice": {"voice_id": config.voice_id, "rate": 1},
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
            response = requests.post(url, json=payload, headers=auth_headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
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

# Endpoints REST

@app.get("/")
async def root():
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
        logger.info(f"Sesión creada en HeyGen: {session_id}")

        # 2. Iniciar la sesión
        await session_manager.start_session(session_id)
        logger.info(f"Sesión iniciada en HeyGen: {session_id}")
        
        # 3. Almacenar localmente y devolver credenciales
        active_sessions[session_id] = {
            "session_id": session_id,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "livekit_url": session_data.get("url"),
            "livekit_token": session_data.get("access_token")
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
    logger.info(f"Sesión cerrada y eliminada: {session_id}")
    return {"status": "closed", "session_id": session_id}

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
        
        logger.info(f"Audio transcrito exitosamente: '{transcription[:50]}...'")
        
        return STTResponse(
            transcription=transcription,
            confidence=confidence,
            duration=duration
        )
        
    except Exception as e:
        logger.error(f"Error en transcripción de audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error transcribing audio: {str(e)}")

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
    logger.info(f"WebSocket conectado para sesión: {session_id}")
    
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
                    # Enviar tarea de texto al avatar
                    task_text = message.get("text", "")
                    task_type = message.get("task_type", "chat")  # Default a "chat" si no se especifica
                    if task_text:
                        await session_manager.send_task(session_id, task_text, task_type)
                        await websocket.send_text(json.dumps({
                            "type": "task_sent",
                            "message": "Tarea enviada correctamente"
                        }))
                
                elif message.get("type") == "close":
                    # Cerrar sesión
                    await session_manager.close_session(session_id)
                    if session_id in active_sessions:
                        del active_sessions[session_id]
                    logger.info(f"Sesión cerrada desde WebSocket: {session_id}")
                    break
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket desconectado para sesión: {session_id}")
                break
            except Exception as e:
                logger.error(f"Error en WebSocket para sesión {session_id}: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Error: {str(e)}"
                }))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket desconectado para sesión: {session_id}")
    except Exception as e:
        logger.error(f"Error general en WebSocket para sesión {session_id}: {e}")
    finally:
        logger.info(f"Cerrando WebSocket para sesión: {session_id}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)