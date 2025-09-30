# 🏛️ NovaIA Contract Validator - Sistema de Validación Contractual

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.68+-green.svg)
![UiPath](https://img.shields.io/badge/UiPath-Integration-orange.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-Vision%20API-green.svg)

**NovaIA Contract Validator** es un sistema inteligente de validación contractual que utiliza AlicIA (avatar IA de Indra) para gestionar consultas de facturación y validar automáticamente facturas de NovaIA contra contratos establecidos. El sistema integra HeyGen para el avatar, OpenAI Vision para OCR de facturas, y UiPath para análisis contractual automatizado.

## 🎯 Propósito del Proyecto

Este sistema fue creado específicamente para **identificar diferencias entre contratos pactados con NovaIA y las facturas emitidas**. Permite a los usuarios:

- **Consultar discrepancias** mediante preguntas predefinidas
- **Validar facturas** automáticamente usando OCR inteligente
- **Recibir análisis contractual** detallado vía email
- **Interactuar naturalmente** con AlicIA, el avatar de Indra

## ✨ Características principales

### 🤖 Avatar AlicIA Inteligente
- **Avatar profesional de Indra** con conocimiento especializado en contratos
- **Respuestas predefinidas** para consultas de facturación
- **Interfaz natural** mediante HeyGen + WebRTC

### 💰 Módulo de Consultas de Facturación
- **Preguntas predefinidas** sobre discrepancias contractuales
- **Validación de email obligatoria** antes de usar funcionalidades
- **Respuesta inmediata** + proceso UiPath en segundo plano
- **Email automático** con análisis contractual detallado

### 📄 Módulo de Validación de Facturas
- **OCR inteligente** con OpenAI Vision API
- **Extracción automática** de conceptos, tarifas y totales
- **Drag & drop** para subir facturas (JPG, PNG)
- **Validación contractual** automática vía UiPath
- **Detección de conceptos no contractuales**

### 🔧 Integración UiPath
- **Agente unificado** para consultas y facturas
- **Parámetros dinámicos**: InCorreo (email) + InCaso (datos)
- **Proceso automatizado** de análisis y notificación
- **Orquestación cloud** con tokens PAT

## 🏗️ Arquitectura

```
┌─────────────────┐   Email Input    ┌─────────────────┐    UiPath API    ┌─────────────────┐
│   Frontend      │◄─────────────────│   Backend       │◄─────────────────│   UiPath        │
│   (avatar.html) │  Consultation    │   (FastAPI)     │   Validation     │   Orchestrator  │
│                 │  + Invoice OCR   │                 │   Process        │                 │
│ ┌─────────────┐ │                  │ ┌─────────────┐ │                  │ ┌─────────────┐ │
│ │ AlicIA      │ │   WebSocket      │ │ Session +   │ │                  │ │ Contract    │ │
│ │ Avatar +    │ │◄─────────────────┼─┤ UiPath Mgr  │ │                  │ │ Validation  │ │
│ │ UI Controls │ │                  │ │             │ │                  │ │ + Email     │ │
│ └─────────────┘ │                  │ └─────────────┘ │                  │ └─────────────┘ │
└─────────────────┘                  └─────────────────┘                  └─────────────────┘
          ↑                                   ↑
    ┌─────────────┐                  ┌─────────────┐
    │ HeyGen      │                  │ OpenAI      │
    │ Streaming   │                  │ Vision API  │
    │ Avatar API  │                  │ (OCR)       │
    └─────────────┘                  └─────────────┘
```

### Componentes principales

**Frontend (avatar.html)**
- **Validación de Email** - Campo obligatorio con verificación de formato
- **Consultas Predefinidas** - Botones para casos comunes de facturación
- **Upload de Facturas** - Drag & drop con preview y extracción OCR
- **Avatar AlicIA** - Streaming en tiempo real con chroma key

**Backend (main.py)**
- **FastAPI + WebSocket** - API REST y comunicación en tiempo real
- **Email Validation System** - Validación y asociación por sesión
- **OpenAI Vision Integration** - Extracción OCR de datos de facturas
- **UiPath Manager** - Orquestación de workflows de validación

**UiPath Integration (uipath_integration.py)**
- **Contract Validation Agent** - Análisis automático de discrepancias
- **Dynamic Parameters** - Email + datos específicos por consulta/factura
- **Email Notifications** - Envío automático de resultados de análisis

## 🚀 Instalación y configuración

### Requisitos previos

- Python 3.8+
- Cuenta HeyGen con API key
- Cuenta OpenAI con acceso a Vision API
- Acceso a UiPath Orchestrator Cloud
- Navegador web moderno con soporte WebRTC

### 1. Clonar el repositorio

```bash
git clone [url-del-repositorio]
cd V-UiPath
```

### 2. Crear entorno virtual

```bash
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Crea un archivo `.env` con las siguientes configuraciones:

```env
# HeyGen Configuration
HEYGEN_API_KEY=tu_heygen_api_key
HEYGEN_BASE_URL=https://api.heygen.com/v1

# Avatar Configuration
AVATAR_ID=Marianne_ProfessionalLook2_public
VOICE_ID=b03cee81247e42d391cecc6b60f0f042
SESSION_QUALITY=medium

# OpenAI Configuration
OPENAI_API_KEY=tu_openai_api_key
OPENAI_SYSTEM_MESSAGE="Eres AlicIA, asistente de Indra..."

# UiPath Configuration
UIPATH_ORGANIZATION=minsacsvndlb
UIPATH_TENANT=CO_DEMO
UIPATH_PAT=tu_uipath_personal_access_token
UIPATH_PROCESS_NAME=RPA.Workflow

# Server Configuration
HOST=0.0.0.0
PORT=8000
ALLOWED_ORIGINS=*
```

### 5. Iniciar la aplicación

```bash
# Opción 1: Directamente con Python
python main.py

# Opción 2: Con Uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Acceder al cliente

Abre tu navegador y ve a:
```
http://localhost:8000
```

## 🎮 Guía de uso

### 1. Validación de Email (Obligatorio)

1. **Ingresa tu email** en el campo "Validación de Correo Electrónico"
2. **Presiona "Validar Email"** - El sistema verificará el formato
3. **Confirmación** - Los botones se habilitarán con email válido

### 2. Consultas de Facturación Predefinidas

1. **Selecciona una consulta** de los botones disponibles:
   - "¿Por qué me están cobrando un dashboard interactivo?"
   - "La tarifa del desarrollador RPA senior es incorrecta"
   - "¿Qué tarifa se aplica para soporte fuera de horario?"

2. **Respuesta inmediata** - AlicIA responderá:
   *"Estamos analizando el contrato y tu caso de uso, en un momento recibirás en tu correo el análisis completo"*

3. **Proceso automático** - UiPath analizará tu consulta vs contrato
4. **Email de resultados** - Recibirás análisis detallado en tu correo

### 3. Validación de Facturas

1. **Sube tu factura** - Arrastra o haz clic para seleccionar imagen (JPG/PNG)
2. **Extracción automática** - OpenAI Vision extraerá:
   - Datos básicos (empresa, número, fecha)
   - Conceptos facturados con valores
   - Total de la factura
   - Observaciones sobre conceptos no contractuales

3. **Revisa los datos** - Verifica que la extracción sea correcta
4. **Validar factura** - Presiona "Validar Factura vs Contrato"
5. **Análisis automático** - UiPath comparará factura vs contrato
6. **Email de resultados** - Recibirás análisis detallado de discrepancias

### 4. Interacción con AlicIA

- **Crear sesión** - Conecta con el avatar de Indra
- **Conversación natural** - Puedes chatear libremente sobre temas de Indra
- **Chroma key** - El avatar aparece con fondo transparente
- **Audio sincronizado** - Escucha las respuestas de AlicIA

## 📡 API Reference

### Endpoints de Email

#### Validar email
```http
POST /api/email/validate
Content-Type: application/json

{
  "email": "usuario@empresa.com"
}
```

#### Asociar email con sesión
```http
POST /api/sessions/{session_id}/email
Content-Type: application/json

{
  "session_id": "uuid",
  "email": "usuario@empresa.com"
}
```

### Endpoints de Facturas

#### Extraer datos de factura
```http
POST /api/invoice/extract
Content-Type: multipart/form-data

[invoice_file: image/jpeg]
```

**Respuesta:**
```json
{
  "success": true,
  "extracted_data": {
    "tipo_documento": "factura",
    "empresa_emisora": "NovaIA",
    "numero_factura": "FAC-2024-001",
    "total_factura": 6100000,
    "conceptos": [
      {
        "descripcion": "Desarrollo RPA Senior",
        "total_concepto": 3600000
      }
    ],
    "observaciones": "Dashboard no contractual detectado"
  },
  "message": "Datos extraídos exitosamente"
}
```

### Endpoints UiPath

#### Trigger manual de workflow
```http
POST /api/uipath/trigger
Content-Type: application/json

{
  "question": "¿Por qué me cobran dashboard?"
}
```

#### Verificar estado de job
```http
GET /api/uipath/job/{job_id}
```

### WebSocket Events

#### Consultas predefinidas
```javascript
ws.send(JSON.stringify({
  type: 'task',
  text: 'Pregunta del usuario',
  question_case: 'Texto completo del botón'
}));
```

#### Validación de facturas
```javascript
ws.send(JSON.stringify({
  type: 'task',
  text: 'Validación de factura vs contrato',
  question_case: JSON.stringify(extracted_invoice_data)
}));
```

## ⚙️ Configuración avanzada

### Personalización de UiPath

Modifica las variables de entorno para tu tenant:

```env
UIPATH_ORGANIZATION=tu_organizacion
UIPATH_TENANT=tu_tenant
UIPATH_PAT=tu_token_pat
UIPATH_PROCESS_NAME=tu_proceso_validacion
```

### Configuración de OpenAI Vision

El sistema usa `gpt-4-vision-preview` con prompt especializado para extraer datos financieros estructurados. Puedes ajustar el prompt en `main.py`:

```python
system_prompt = """
Eres un experto en análisis de facturas. Extrae TODOS los datos financieros...
"""
```

### Personalización del Avatar

Ajusta las configuraciones en `.env`:

```env
AVATAR_ID=tu_avatar_preferido
VOICE_ID=tu_voz_preferida
SESSION_QUALITY=high  # low, medium, high
```

## 🛠️ Desarrollo

### Estructura del proyecto

```
V-UiPath/
├── main.py                 # Backend FastAPI + OpenAI Vision
├── uipath_integration.py   # Gestión de workflows UiPath
├── avatar.html             # Frontend completo con módulos
├── requirements.txt        # Dependencias Python
├── .env                    # Variables de entorno
├── CLAUDE.md              # Documentación para Claude
└── README.md              # Este archivo
```

### Ejecutar en modo desarrollo

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Testing del sistema

1. **Validación de email** - Probar formato correcto/incorrecto
2. **Consultas predefinidas** - Verificar activación de UiPath
3. **OCR de facturas** - Subir imágenes de prueba
4. **Integración UiPath** - Verificar recepción de parámetros
5. **Emails automáticos** - Confirmar envío de análisis

## 🐛 Troubleshooting

### Problemas comunes

**Error: "Debes validar tu email antes de usar esta funcionalidad"**
- Verifica que hayas ingresado un email con formato válido
- Confirma que veas el checkmark verde de validación

**OCR no extrae datos correctamente**
- Usa imágenes de alta calidad (mín. 300 DPI)
- Asegúrate de que el texto sea legible
- Formatos soportados: JPG, PNG (máx. 10MB)

**UiPath no se activa**
- Verifica tu PAT token en variables de entorno
- Confirma que el proceso esté publicado en Orchestrator
- Revisa logs del backend para errores de API

**Avatar no se conecta**
- Verifica tu API key de HeyGen
- Confirma conexión a internet estable
- Revisa créditos disponibles en tu cuenta HeyGen

### Logs útiles

**Backend:**
```bash
INFO: [EMAIL VALIDATION] Email válido almacenado: user@example.com
INFO: [UIPATH] Using validated email for UiPath: user@example.com
INFO: [INVOICE] Datos extraídos exitosamente de factura.jpg
INFO: [PREDEFINED] Using predefined response for question case
```

**Frontend (Consola):**
```javascript
✅ Email válido: usuario@empresa.com
📄 Extrayendo datos de la factura...
✅ Datos extraídos exitosamente de la factura
📋 Enviando factura para validación contractual...
```

## 📦 Dependencias

### Backend Python
- `fastapi` - Framework web moderno y rápido
- `uvicorn[standard]` - Servidor ASGI de alta performance
- `websockets` - Comunicación tiempo real
- `requests` - Cliente HTTP para APIs externas
- `pydantic` - Validación y serialización de datos
- `python-multipart` - Manejo de uploads de archivos
- `aiofiles` - Operaciones de archivos asíncronas
- `deepgram-sdk` - Speech-to-text (funcionalidad adicional)
- `openai` - OpenAI Vision API para OCR
- `python-dotenv` - Gestión de variables de entorno
- `Pillow` - Procesamiento de imágenes

### APIs Externas
- **HeyGen Streaming API** - Avatar IA y video streaming
- **OpenAI Vision API** - OCR inteligente de facturas
- **UiPath Orchestrator** - Automatización y validación contractual
- **LiveKit** - Infraestructura WebRTC (via HeyGen)

## 🤝 Contribución

1. Fork del repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar validación de contratos mejorada'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.

## 👥 Créditos

- **Indra Colombia** - Desarrollo y arquitectura del sistema
- **AlicIA** - Avatar especializado en contratos y servicios Indra
- **HeyGen** - Plataforma de avatares IA
- **OpenAI** - Vision API para extracción de datos
- **UiPath** - Plataforma de automatización RPA

## 📞 Soporte

Para soporte técnico y consultas sobre el sistema:

- 🏢 **Indra Colombia** - Equipo de Desarrollo
- 📧 **Email técnico**: [soporte@indracompany.com]
- 🤖 **AlicIA**: Usa el sistema para consultas sobre funcionalidades

---

## ⚠️ Notas importantes

- **Requiere APIs activas**: HeyGen, OpenAI Vision y UiPath Orchestrator
- **Costos por uso**: Las APIs externas tienen tarifas según consumo
- **Datos sensibles**: El sistema maneja información contractual confidencial
- **Validación obligatoria**: Email requerido para todas las funcionalidades

---

## 🎯 Casos de uso principales

### Para Usuarios de Negocio
- ✅ Validar facturas recibidas de NovaIA automáticamente
- ✅ Consultar discrepancias contractuales específicas
- ✅ Recibir análisis detallados vía email
- ✅ Detectar cobros no acordados en contratos

### Para Equipos de Contratos
- ✅ Automatizar revisión de facturas vs contratos
- ✅ Identificar patrones de discrepancias
- ✅ Generar reportes automáticos de diferencias
- ✅ Acelerar procesos de validación contractual

---

<p align="center">
  <strong>🏛️ Desarrollado por Indra Colombia para optimizar la validación contractual con NovaIA</strong>
</p>