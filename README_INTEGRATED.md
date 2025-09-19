# Google Docs API + ADK Agent - Solución Integrada

Una API de Python que combina la lectura de Google Docs con procesamiento de IA usando Google ADK (Agent Development Kit) y integración con Slack.

## 🚀 Características

- 🐍 **Python + FastAPI** - Framework moderno y rápido
- 🔐 **Autenticación con gcloud CLI** - Simple y directo
- 📖 **Lectura de documentos** de Google Docs
- 🤖 **Procesamiento con IA** usando Google ADK
- 📝 **Extracción y procesamiento** de notas de reuniones
- 💬 **Integración con Slack** - Crear/actualizar canvases
- 🔍 **Búsqueda de documentos** por contenido
- 📊 **Metadatos** y elementos estructurados
- 🚀 **Documentación automática** con Swagger UI

## 📋 Requisitos

- Python 3.8+
- Cuenta de Google Cloud con proyecto configurado
- gcloud CLI instalado y configurado
- Token de Slack (opcional, para integración con Slack)

## 🛠️ Instalación

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar autenticación con Google Cloud

```bash
# Autenticarse con Google Cloud
gcloud auth login

# Configurar el proyecto
gcloud config set project docdash-ai-dev

# Configurar Application Default Credentials
gcloud auth application-default login
```

### 3. Habilitar APIs necesarias

```bash
# Habilitar Google Docs API
gcloud services enable docs.googleapis.com

# Habilitar Google Drive API
gcloud services enable drive.googleapis.com

# Habilitar Vertex AI API (para ADK)
gcloud services enable aiplatform.googleapis.com
```

### 4. Configurar variables de entorno

Edita el archivo `.env`:

```env
# Server Configuration
PORT=8000
HOST=0.0.0.0
DEBUG=True

# Google Cloud Project
GOOGLE_CLOUD_PROJECT=docdash-ai-dev

# Slack Configuration (opcional)
SLACK_API_TOKEN=your_slack_api_token_here
SLACK_CANVAS_ID=your_slack_canvas_id_here
SLACK_CHANNEL_ID=your_slack_channel_id_here
```

## 🚀 Uso

### Iniciar el servidor

```bash
# Versión integrada (recomendada)
python main_integrated.py

# O versión solo API de Google Docs
python main.py

# Con uvicorn directamente
uvicorn main_integrated:app --reload --host 0.0.0.0 --port 8000
```

El servidor estará disponible en:
- **API**: http://localhost:8000
- **Documentación**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 📚 Endpoints de la API

### Autenticación

- `GET /api/auth/status` - Verificar estado de autenticación
- `POST /api/auth/init` - Inicializar autenticación

### Documentos (API original)

- `GET /api/docs` - Listar todos los documentos
- `GET /api/docs/{document_id}` - Obtener documento por ID
- `GET /api/docs/name/{document_name}` - Obtener documento por nombre
- `GET /api/docs/search/{query}` - Buscar documentos por contenido
- `GET /api/docs/{document_id}/text` - Obtener texto plano del documento
- `GET /api/docs/{document_id}/elements` - Obtener elementos estructurados
- `GET /api/docs/{document_id}/metadata` - Obtener metadatos del documento

### Agente ADK (Nuevos endpoints)

- `POST /api/agent/process-meeting-notes` - Procesar notas de reunión y enviar a Slack
- `POST /api/agent/process-document` - Procesar documento con instrucciones personalizadas

## 🤖 Ejemplos de uso del Agente ADK

### 1. Procesar notas de reunión y crear canvas en Slack

```bash
curl -X POST "http://localhost:8000/api/agent/process-meeting-notes" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "DOCUMENT_ID",
    "action": "create",
    "channel_id": "SLACK_CHANNEL_ID",
    "title": "Notas de Reunión - KickOff"
  }'
```

### 2. Actualizar canvas existente con nuevas notas

```bash
curl -X POST "http://localhost:8000/api/agent/process-meeting-notes" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "DOCUMENT_ID",
    "action": "update",
    "canvas_id": "SLACK_CANVAS_ID"
  }'
```

### 3. Procesar documento con instrucciones personalizadas

```bash
curl -X POST "http://localhost:8000/api/agent/process-document" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "DOCUMENT_ID",
    "custom_instruction": "Extrae todas las tareas pendientes y organízalas por prioridad"
  }'
```

## 🏗️ Arquitectura

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   Google ADK     │    │   Slack API     │
│                 │    │                  │    │                 │
│ • Auth Service  │◄──►│ • LlmAgent       │◄──►│ • Canvas API    │
│ • Docs Service  │    │ • AdkApp         │    │ • Channel API   │
│ • API Endpoints │    │ • Tools          │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌──────────────────┐
│  Google Docs    │    │   Vertex AI      │
│  API            │    │   (Gemini)       │
└─────────────────┘    └──────────────────┘
```

## 🔧 Configuración de Slack (Opcional)

Para usar la integración con Slack:

1. **Crear una app en Slack:**
   - Ve a [api.slack.com/apps](https://api.slack.com/apps)
   - Crea una nueva app
   - Obtén el token de bot

2. **Configurar permisos:**
   - `canvases:write` - Para crear/editar canvases
   - `channels:read` - Para acceder a canales

3. **Configurar variables de entorno:**
   ```env
   SLACK_API_TOKEN=xoxb-your-token-here
   SLACK_CHANNEL_ID=C1234567890
   SLACK_CANVAS_ID=1234567890
   ```

## 📁 Estructura del proyecto

```
├── services/
│   ├── __init__.py
│   ├── auth_service.py      # Servicio de autenticación
│   └── docs_service.py      # Servicio para Google Docs
├── main.py                  # Aplicación original (solo API)
├── main_integrated.py       # Aplicación integrada (API + ADK)
├── requirements.txt         # Dependencias Python
├── .env                     # Variables de entorno
├── README.md               # Documentación original
└── README_INTEGRATED.md    # Esta documentación
```

## 🧪 Testing

### 1. Verificar autenticación

```bash
curl http://localhost:8000/api/auth/status
```

### 2. Listar documentos

```bash
curl http://localhost:8000/api/docs
```

### 3. Procesar documento con agente

```bash
curl -X POST "http://localhost:8000/api/agent/process-meeting-notes" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "TU_DOCUMENT_ID",
    "action": "create",
    "channel_id": "TU_CHANNEL_ID"
  }'
```

## 🐛 Solución de problemas

### Error de autenticación

```bash
# Re-autenticarse
gcloud auth application-default login

# Verificar proyecto
gcloud config get-value project

# Verificar APIs habilitadas
gcloud services list --enabled
```

### Error de permisos en Slack

- Verifica que el token tenga los permisos correctos
- Asegúrate de que la app esté instalada en el workspace
- Verifica que el canal/canvas exista

### Error de ADK

- Verifica que Vertex AI esté habilitado
- Asegúrate de tener permisos en el proyecto
- Verifica que el modelo Gemini esté disponible

## 📝 Dependencias principales

- **FastAPI** - Framework web moderno
- **google-api-python-client** - SDK de Google APIs
- **google-adk** - Agent Development Kit
- **vertexai** - Vertex AI para modelos de IA
- **requests** - Cliente HTTP para Slack API
- **uvicorn** - Servidor ASGI

## 🔄 Flujo de trabajo típico

1. **Autenticación**: El usuario se autentica con Google Cloud
2. **Lectura**: La API lee documentos de Google Docs
3. **Procesamiento**: El agente ADK procesa el contenido con IA
4. **Integración**: Los resultados se envían a Slack (opcional)
5. **Respuesta**: La API devuelve los resultados procesados

## 📄 Licencia

MIT

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📞 Soporte

Para soporte o preguntas:
- Abre un issue en GitHub
- Revisa la documentación de [Google ADK](https://cloud.google.com/vertex-ai/docs/agent-builder)
- Consulta la [documentación de FastAPI](https://fastapi.tiangolo.com/)
