import asyncio
import os
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, Any, Optional
import requests
import json

# Importar nuestros servicios
from services.docs_service import DocsService
from services.auth_service import AuthService
from services.change_detection_service import ChangeDetectionService
from services.notification_service import NotificationService
from services.polling_service import PollingService

# Importar Google ADK
from google.adk.agents import LlmAgent
from vertexai.preview.reasoning_engines import AdkApp

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Google Docs API + ADK Agent",
    description="API para conectar con Google Docs y procesar documentos con IA usando Google ADK",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
auth_service = AuthService()
docs_service = DocsService()
change_detection_service = None
notification_service = NotificationService()
polling_service = None

# Variables de entorno para Slack
SLACK_API_TOKEN = os.environ.get("SLACK_API_TOKEN")
SLACK_CANVAS_ID = os.environ.get("SLACK_CANVAS_ID")
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")

# Dependency to check authentication
async def get_authenticated_service():
    if not auth_service.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="No autenticado. Ejecuta: gcloud auth application-default login"
        )
    return docs_service

# Initialize change detection services
async def initialize_change_detection_services():
    """Initialize change detection and polling services"""
    global change_detection_service, polling_service
    
    if not auth_service.is_authenticated():
        await auth_service.initialize()
    
    if change_detection_service is None:
        change_detection_service = ChangeDetectionService(
            credentials=auth_service.get_credentials(),
            project_id=auth_service.project_id
        )
        await change_detection_service.initialize()
    
    if polling_service is None:
        polling_service = PollingService(change_detection_service, notification_service)
        await polling_service.start_polling()

# --- Herramientas para el agente ADK ---

def get_notes_from_google_docs(document_id: str) -> str:
    """
    Lee y devuelve el contenido de un documento de Google Docs usando nuestra API.
    
    Args:
        document_id: El ID del documento de Google Docs.
    
    Returns:
        Una cadena de texto con el contenido del documento.
    """
    try:
        # Usar nuestro servicio de documentos
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        document = loop.run_until_complete(docs_service.get_document_by_id(document_id))
        loop.close()
        
        return document.get("plain_text", "No se pudo obtener el contenido del documento")
    except Exception as e:
        return f"Error al leer el documento: {str(e)}"

def update_slack_canvas(canvas_id: str, markdown_content: str) -> str:
    """
    Actualiza el contenido de un canvas de Slack existente.

    Args:
        canvas_id: La ID del canvas de Slack que se va a editar.
        markdown_content: El texto en formato Markdown para actualizar el canvas.

    Returns:
        Un mensaje de confirmación o error de la API de Slack.
    """
    if not SLACK_API_TOKEN:
        return "Error: SLACK_API_TOKEN no configurado."
    
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {SLACK_API_TOKEN}"}
    url = "https://slack.com/api/canvases.edit"
    
    payload = {
        "canvas_id": canvas_id,
        "changes": [
            {
                "operation": "replace",
                "document_content": {
                    "type": "markdown",
                    "markdown": markdown_content
                }
            }
        ]
    }

    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if data.get("ok"):
            return f"Canvas {canvas_id} actualizado correctamente."
        return f"Error Slack: {data.get('error')}"
    except requests.exceptions.RequestException as e:
        return f"Error API Slack: {e}"

def create_slack_canvas(channel_id: str, title: str, markdown_content: str) -> str:
    """
    Crea un nuevo canvas de Slack en un canal específico.

    Args:
        channel_id: La ID del canal de Slack donde se creará el canvas.
        title: El título del nuevo canvas.
        markdown_content: El texto en formato Markdown para el nuevo canvas.

    Returns:
        Un mensaje de confirmación o error de la API de Slack.
    """
    if not SLACK_API_TOKEN:
        return "Error: SLACK_API_TOKEN no configurado."
    
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {SLACK_API_TOKEN}"}
    url = "https://slack.com/api/canvases.create"
    
    payload = {
        "title": title,
        "channel_id": channel_id,
        "document_content": {
            "type": "markdown",
            "markdown": markdown_content
        }
    }

    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if data.get("ok"):
            return f"Nuevo canvas creado en el canal {channel_id}. ID: {data.get('canvas_id')}"
        return f"Error Slack: {data.get('error')}"
    except requests.exceptions.RequestException as e:
        return f"Error API Slack: {e}"

# --- Endpoints de la API ---

@app.get("/")
async def root():
    return {
        "message": "Google Docs API + ADK Agent",
        "version": "2.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "Google Docs API",
            "ADK Agent Integration",
            "Slack Canvas Integration"
        ]
    }

@app.get("/health")
async def health_check():
    return {
        "status": "OK",
        "message": "Google Docs API + ADK Agent is running",
        "timestamp": datetime.now().isoformat()
    }

# Authentication endpoints
@app.get("/api/auth/status")
async def auth_status():
    try:
        project_info = await auth_service.get_project_info()
        return {
            "success": True,
            "authenticated": project_info["authenticated"],
            "project_id": project_info.get("project_id"),
            "message": (f"Autenticado con proyecto: {project_info.get('project_id')}" 
                if project_info["authenticated"] 
                else "No autenticado. Ejecuta: gcloud auth application-default login")
        }
    except Exception as e:
        return {
            "success": False,
            "error": "Error al verificar autenticación",
            "message": str(e)
        }

@app.post("/api/auth/init")
async def init_auth():
    try:
        await auth_service.initialize()
        return {
            "success": True,
            "message": "Autenticación inicializada correctamente",
            "authenticated": auth_service.is_authenticated()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al inicializar autenticación: {str(e)}"
        )

# Documents endpoints (mantenemos los originales)
@app.get("/api/docs")
async def get_documents(
    page_size: int = 10,
    page_token: str = None,
    service: DocsService = Depends(get_authenticated_service)
):
    try:
        result = await service.get_documents_list(page_size, page_token)
        return {
            "success": True,
            "data": result,
            "message": f"Encontrados {result['total_count']} documentos"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener lista de documentos: {str(e)}"
        )

@app.get("/api/docs/{document_id}")
async def get_document_by_id(
    document_id: str,
    format: str = "full",
    service: DocsService = Depends(get_authenticated_service)
):
    try:
        document = await service.get_document_by_id(document_id)
        
        # Return different formats based on query parameter
        if format == "text":
            response_data = {
                "id": document["id"],
                "title": document["title"],
                "content": document["plain_text"]
            }
        elif format == "metadata":
            response_data = {
                "id": document["id"],
                "title": document["title"],
                "metadata": document["metadata"],
                "element_count": len(document["elements"])
            }
        else:
            response_data = document
        
        return {
            "success": True,
            "data": response_data,
            "message": f"Documento '{document['title']}' obtenido correctamente"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener documento: {str(e)}"
        )

@app.get("/api/docs/{document_id}/tabs")
async def get_document_tabs(
    document_id: str,
    service: DocsService = Depends(get_authenticated_service)
):
    """Get tabs/sections from a specific document"""
    try:
        result = await service.get_document_tabs(document_id)
        return {
            "success": True,
            "data": result,
            "message": f"Tabs obtenidos correctamente: {result.get('total_tabs', 0)} tabs encontrados"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener tabs del documento: {str(e)}"
        )

@app.get("/api/docs/{document_id}/tabs/visual")
async def get_document_tabs_visual(
    document_id: str,
    service: DocsService = Depends(get_authenticated_service)
):
    """Get tabs in a visual format similar to mobile app interface"""
    try:
        result = await service.get_document_tabs(document_id)
        
        # Transform tabs into visual format
        visual_tabs = []
        
        for tab in result.get('tabs', []):
            # Determine tab type and icon based on content
            tab_type, icon = _determine_tab_type_and_icon(tab)
            
            visual_tab = {
                "id": f"tab_{tab['index']}",
                "index": tab['index'],
                "title": tab['title'],
                "type": tab_type,
                "icon": icon,
                "is_active": tab['index'] == 0,  # First tab is active by default
                "content": {
                    "text": _extract_tab_text_content(tab),
                    "word_count": len(_extract_tab_text_content(tab).split()),
                    "has_content": len(tab.get('content', [])) > 0
                },
                "metadata": {
                    "start_position": tab.get('start_position', 0),
                    "end_position": tab.get('end_position', 0),
                    "content_items": len(tab.get('content', []))
                }
            }
            visual_tabs.append(visual_tab)
        
        return {
            "success": True,
            "data": {
                "document_id": result.get('document_id'),
                "document_title": result.get('document_title'),
                "tabs": visual_tabs,
                "total_tabs": len(visual_tabs),
                "active_tab": visual_tabs[0]['id'] if visual_tabs else None,
                "ui_config": {
                    "show_add_button": True,
                    "allow_reorder": True,
                    "theme": "light"
                }
            },
            "message": f"Tabs visuales generados: {len(visual_tabs)} tabs encontrados"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener tabs visuales: {str(e)}"
        )

# --- Funciones auxiliares para tabs visuales ---

def _determine_tab_type_and_icon(tab: dict) -> tuple:
    """Determine tab type and icon based on content and title"""
    title = tab.get('title', '').lower()
    content = _extract_tab_text_content(tab).lower()
    
    # Notes tab
    if any(keyword in title for keyword in ['notes', 'notas', 'summary', 'resumen']):
        return "notes", "📝"
    
    # Transcript tab
    if any(keyword in title for keyword in ['transcript', 'transcripción', 'details', 'detalles']):
        return "transcript", "📖"
    
    # Meeting tab
    if any(keyword in title for keyword in ['meeting', 'reunión', 'agenda']):
        return "meeting", "👥"
    
    # Attachments tab
    if any(keyword in title for keyword in ['attachment', 'adjunto', 'file', 'archivo']):
        return "attachments", "📎"
    
    # Invited tab
    if any(keyword in title for keyword in ['invited', 'invitado', 'participant', 'participante']):
        return "participants", "👤"
    
    # Records tab
    if any(keyword in title for keyword in ['record', 'registro', 'log']):
        return "records", "📋"
    
    # Next steps tab
    if any(keyword in title for keyword in ['next', 'siguiente', 'step', 'paso', 'action', 'acción']):
        return "actions", "✅"
    
    # Default tab
    return "general", "📄"

def _extract_tab_text_content(tab: dict) -> str:
    """Extract all text content from a tab"""
    text_parts = []
    
    for content_item in tab.get('content', []):
        if content_item.get('type') == 'paragraph':
            text = content_item.get('text', '').strip()
            if text:
                text_parts.append(text)
        elif content_item.get('type') == 'table':
            # Extract text from table
            table_data = content_item.get('data', [])
            for row in table_data:
                for cell in row:
                    if cell.strip():
                        text_parts.append(cell.strip())
    
    return ' '.join(text_parts)

# --- Nuevos endpoints para el agente ADK ---

@app.post("/api/agent/process-meeting-notes")
async def process_meeting_notes(
    document_id: str,
    action: str = "create",  # "create" o "update"
    channel_id: Optional[str] = None,
    canvas_id: Optional[str] = None,
    title: Optional[str] = None
):
    """
    Procesa las notas de una reunión usando el agente ADK y las envía a Slack.
    
    Args:
        document_id: ID del documento de Google Docs
        action: "create" para crear nuevo canvas o "update" para actualizar existente
        channel_id: ID del canal de Slack (requerido para crear)
        canvas_id: ID del canvas de Slack (requerido para actualizar)
        title: Título del canvas (opcional)
    """
    try:
        # Validar parámetros
        if action == "create" and not channel_id:
            raise HTTPException(
                status_code=400,
                detail="channel_id es requerido para crear un nuevo canvas"
            )
        if action == "update" and not canvas_id:
            raise HTTPException(
                status_code=400,
                detail="canvas_id es requerido para actualizar un canvas existente"
            )
        
        # Crear el agente
        meeting_notes_agent = LlmAgent(
            name="meeting_notes_agent",
            model="gemini-2.5-pro",
            description="Un asistente que procesa notas de reuniones para crear o actualizar canvases en Slack.",
            instruction="""
            Tu tarea es procesar las notas de una reunión, extraer las tareas pendientes y generar solo el contenido de las notas en formato Markdown. No generes JSON.
            Usa '#' para el título principal y '##' para secciones.
            Las tareas pendientes deben ir en listas con '-' y mencionar al responsable en negrita.
            Usa la herramienta 'get_notes_from_google_docs' primero para obtener el contenido en texto plano.
            """,
            output_key="meeting_notes",
            tools=[get_notes_from_google_docs, update_slack_canvas, create_slack_canvas]
        )
        
        # Determinar la consulta
        if action == "create":
            query_to_run = f"Crea un nuevo canvas en el canal '{channel_id}' con las notas del documento '{document_id}'."
            if title:
                query_to_run += f" Usa '{title}' como título del canvas."
        else:
            query_to_run = f"Actualiza el canvas '{canvas_id}' con las notas del documento '{document_id}'."
        
        # Ejecutar el agente
        app_adk = AdkApp(agent=meeting_notes_agent)
        
        result = []
        async for event in app_adk.async_stream_query(message=query_to_run, user_id="api_user"):
            result.append(str(event))
        
        return {
            "success": True,
            "message": f"Procesamiento completado para documento {document_id}",
            "action": action,
            "result": result
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar notas de reunión: {str(e)}"
        )

@app.post("/api/agent/process-document")
async def process_document_with_agent(
    document_id: str,
    custom_instruction: str,
    background_tasks: BackgroundTasks
):
    """
    Procesa un documento con instrucciones personalizadas usando el agente ADK.
    """
    try:
        # Crear agente personalizado
        custom_agent = LlmAgent(
            name="custom_document_agent",
            model="gemini-2.5-pro",
            description="Un asistente que procesa documentos de Google Docs con instrucciones personalizadas.",
            instruction=custom_instruction,
            output_key="processed_content",
            tools=[get_notes_from_google_docs]
        )
        
        # Ejecutar en background
        async def process_in_background():
            app_adk = AdkApp(agent=custom_agent)
            query = f"Procesa el documento '{document_id}' siguiendo las instrucciones proporcionadas."
            
            result = []
            async for event in app_adk.async_stream_query(message=query, user_id="api_user"):
                result.append(str(event))
            
            return result
        
        # Agregar tarea en background
        background_tasks.add_task(process_in_background)
        
        return {
            "success": True,
            "message": f"Procesamiento iniciado para documento {document_id}",
            "status": "processing"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar documento: {str(e)}"
        )

# Endpoint de prueba (sin autenticación)
@app.get("/api/test/sample-document")
async def get_sample_document():
    """Endpoint de prueba que devuelve un documento de ejemplo"""
    return {
        "success": True,
        "data": {
            "id": "sample-doc-123",
            "title": "Notas de Reunión - KickOff",
            "content": """
            TÍTULO DE LA REUNIÓN: KickOff con el cliente
            Resumen de la reunión del equipo:
            - Estado del proyecto X: En curso, sin retrasos.
            - Tareas pendientes:
                - Tarea 1: Actualizar el reporte de ventas. (Responsable: Juan)
                - Tarea 2: Enviar el resumen de la reunión a todo el equipo. (Responsable: María)
                - Tarea 3: Investigar la nueva API. (Responsable: Pedro)
            """,
            "plain_text": "TÍTULO DE LA REUNIÓN: KickOff con el cliente. Resumen de la reunión del equipo: - Estado del proyecto X: En curso, sin retrasos. - Tareas pendientes: - Tarea 1: Actualizar el reporte de ventas. (Responsable: Juan) - Tarea 2: Enviar el resumen de la reunión a todo el equipo. (Responsable: María) - Tarea 3: Investigar la nueva API. (Responsable: Pedro)",
            "elements": [
                {"index": 0, "type": "paragraph", "content": "TÍTULO DE LA REUNIÓN: KickOff con el cliente"},
                {"index": 1, "type": "paragraph", "content": "Resumen de la reunión del equipo:"},
                {"index": 2, "type": "paragraph", "content": "- Estado del proyecto X: En curso, sin retrasos."},
                {"index": 3, "type": "paragraph", "content": "- Tareas pendientes:"},
                {"index": 4, "type": "paragraph", "content": "    - Tarea 1: Actualizar el reporte de ventas. (Responsable: Juan)"},
                {"index": 5, "type": "paragraph", "content": "    - Tarea 2: Enviar el resumen de la reunión a todo el equipo. (Responsable: María)"},
                {"index": 6, "type": "paragraph", "content": "    - Tarea 3: Investigar la nueva API. (Responsable: Pedro)"}
            ],
            "metadata": {
                "revision_id": "sample-revision-123",
                "document_id": "sample-doc-123"
            }
        },
        "message": "Documento de ejemplo obtenido correctamente"
    }

# --- Endpoints de Detección de Cambios ---

@app.post("/api/changes/init")
async def initialize_change_detection():
    """Inicializar servicios de detección de cambios"""
    try:
        await initialize_change_detection_services()
        return {
            "success": True,
            "message": "Servicios de detección de cambios inicializados correctamente"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al inicializar servicios: {str(e)}")

@app.post("/api/changes/webhook/setup")
async def setup_webhook(document_id: str, webhook_url: str):
    """Configurar webhook para un documento"""
    try:
        await initialize_change_detection_services()
        webhook_config = await change_detection_service.setup_webhook(document_id, webhook_url)
        return {
            "success": True,
            "data": {
                "document_id": webhook_config.document_id,
                "webhook_id": webhook_config.webhook_id,
                "webhook_url": webhook_config.webhook_url,
                "expiration": webhook_config.expiration.isoformat()
            },
            "message": "Webhook configurado correctamente"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al configurar webhook: {str(e)}")

@app.delete("/api/changes/webhook/{document_id}")
async def remove_webhook(document_id: str):
    """Remover webhook de un documento"""
    try:
        await initialize_change_detection_services()
        success = await change_detection_service.remove_webhook(document_id)
        if success:
            return {
                "success": True,
                "message": f"Webhook removido para documento {document_id}"
            }
        else:
            raise HTTPException(status_code=404, detail="Webhook no encontrado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al remover webhook: {str(e)}")

@app.get("/api/changes/webhooks")
async def get_active_webhooks():
    """Obtener lista de webhooks activos"""
    try:
        await initialize_change_detection_services()
        webhooks = await change_detection_service.get_active_webhooks()
        return {
            "success": True,
            "data": webhooks,
            "count": len(webhooks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener webhooks: {str(e)}")

@app.post("/api/changes/polling/add")
async def add_document_to_polling(document_id: str, document_title: str = None, interval_seconds: int = 300):
    """Agregar documento al polling automático"""
    try:
        await initialize_change_detection_services()
        success = await polling_service.add_document(document_id, document_title, interval_seconds)
        if success:
            return {
                "success": True,
                "message": f"Documento {document_id} agregado al polling (cada {interval_seconds}s)"
            }
        else:
            raise HTTPException(status_code=400, detail="Error al agregar documento al polling")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al agregar documento: {str(e)}")

@app.delete("/api/changes/polling/{document_id}")
async def remove_document_from_polling(document_id: str):
    """Remover documento del polling"""
    try:
        await initialize_change_detection_services()
        success = await polling_service.remove_document(document_id)
        if success:
            return {
                "success": True,
                "message": f"Documento {document_id} removido del polling"
            }
        else:
            raise HTTPException(status_code=404, detail="Documento no encontrado en polling")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al remover documento: {str(e)}")

@app.get("/api/changes/polling/status")
async def get_polling_status():
    """Obtener estado del servicio de polling"""
    try:
        await initialize_change_detection_services()
        status = await polling_service.get_polling_status()
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estado: {str(e)}")

@app.get("/api/changes/polling/documents")
async def get_polling_documents():
    """Obtener estado de todos los documentos en polling"""
    try:
        await initialize_change_detection_services()
        documents = await polling_service.get_all_documents_status()
        return {
            "success": True,
            "data": documents,
            "count": len(documents)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener documentos: {str(e)}")

@app.get("/api/changes/check/{document_id}")
async def check_document_changes(document_id: str):
    """Verificar cambios en un documento específico"""
    try:
        await initialize_change_detection_services()
        change = await change_detection_service.check_document_changes(document_id)
        if change:
            # Enviar notificación si hay cambios
            notification = await notification_service.create_document_change_notification(
                document_id=change.document_id,
                document_title=change.document_title,
                change_type=change.change_type,
                content_preview=change.content_preview
            )
            await notification_service.send_notification(notification)
            
            return {
                "success": True,
                "data": {
                    "document_id": change.document_id,
                    "document_title": change.document_title,
                    "revision_id": change.revision_id,
                    "change_type": change.change_type,
                    "last_modified": change.last_modified.isoformat(),
                    "content_preview": change.content_preview
                },
                "message": "Cambios detectados en el documento"
            }
        else:
            return {
                "success": True,
                "data": None,
                "message": "No se detectaron cambios en el documento"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al verificar cambios: {str(e)}")

@app.get("/api/changes/history")
async def get_change_history(limit: int = 50):
    """Obtener historial de cambios"""
    try:
        await initialize_change_detection_services()
        history = await change_detection_service.get_change_history(limit)
        return {
            "success": True,
            "data": history,
            "count": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener historial: {str(e)}")

@app.get("/api/notifications/history")
async def get_notification_history(limit: int = 100):
    """Obtener historial de notificaciones"""
    try:
        history = await notification_service.get_notification_history(limit)
        return {
            "success": True,
            "data": history,
            "count": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener historial: {str(e)}")

@app.get("/api/notifications/stats")
async def get_notification_stats():
    """Obtener estadísticas de notificaciones"""
    try:
        stats = await notification_service.get_notification_stats()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {str(e)}")

@app.post("/api/notifications/webhook/add")
async def add_notification_webhook(webhook_url: str):
    """Agregar endpoint de webhook para notificaciones"""
    try:
        notification_service.add_webhook_endpoint(webhook_url)
        return {
            "success": True,
            "message": f"Webhook endpoint agregado: {webhook_url}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al agregar webhook: {str(e)}")

@app.post("/api/changes/webhook/receive")
async def receive_webhook_notification(request_data: dict):
    """Endpoint para recibir notificaciones de webhook de Google Drive"""
    try:
        await initialize_change_detection_services()
        change = change_detection_service.process_webhook_notification(request_data)
        
        if change:
            # Enviar notificación
            notification = await notification_service.create_document_change_notification(
                document_id=change.document_id,
                document_title=change.document_title,
                change_type=change.change_type,
                content_preview=change.content_preview
            )
            await notification_service.send_notification(notification)
            
            return {
                "success": True,
                "message": "Notificación de webhook procesada correctamente",
                "change_detected": True
            }
        else:
            return {
                "success": True,
                "message": "Notificación de webhook recibida pero no procesada",
                "change_detected": False
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar webhook: {str(e)}")

# --- Endpoints para Monitoreo de Carpetas ---

@app.post("/api/changes/folder/webhook/setup")
async def setup_folder_webhook(folder_id: str, webhook_url: str):
    """Configurar webhook para una carpeta completa"""
    try:
        await initialize_change_detection_services()
        folder_config = await change_detection_service.setup_folder_webhook(folder_id, webhook_url)
        return {
            "success": True,
            "data": {
                "folder_id": folder_config.folder_id,
                "folder_name": folder_config.folder_name,
                "webhook_id": folder_config.webhook_id,
                "webhook_url": folder_config.webhook_url,
                "expiration": folder_config.expiration.isoformat(),
                "monitored_documents": len(folder_config.monitored_documents)
            },
            "message": f"Webhook configurado para carpeta: {folder_config.folder_name}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al configurar webhook de carpeta: {str(e)}")

@app.delete("/api/changes/folder/webhook/{folder_id}")
async def remove_folder_webhook(folder_id: str):
    """Remover webhook de una carpeta"""
    try:
        await initialize_change_detection_services()
        success = await change_detection_service.remove_folder_webhook(folder_id)
        if success:
            return {
                "success": True,
                "message": f"Webhook removido para carpeta {folder_id}"
            }
        else:
            raise HTTPException(status_code=404, detail="Webhook de carpeta no encontrado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al remover webhook de carpeta: {str(e)}")

@app.get("/api/changes/folder/webhooks")
async def get_folder_webhooks():
    """Obtener lista de webhooks de carpetas activos"""
    try:
        await initialize_change_detection_services()
        webhooks = await change_detection_service.get_folder_webhooks()
        return {
            "success": True,
            "data": webhooks,
            "count": len(webhooks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener webhooks de carpetas: {str(e)}")

@app.post("/api/changes/folder/polling/add")
async def add_folder_to_polling(folder_id: str, folder_name: str = None, interval_seconds: int = 300):
    """Agregar carpeta al polling automático"""
    try:
        await initialize_change_detection_services()
        success = await polling_service.add_folder_to_polling(folder_id, folder_name, interval_seconds)
        if success:
            return {
                "success": True,
                "message": f"Carpeta {folder_id} agregada al polling (cada {interval_seconds}s)"
            }
        else:
            raise HTTPException(status_code=400, detail="Error al agregar carpeta al polling")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al agregar carpeta: {str(e)}")

@app.delete("/api/changes/folder/polling/{folder_id}")
async def remove_folder_from_polling(folder_id: str):
    """Remover carpeta del polling"""
    try:
        await initialize_change_detection_services()
        success = await polling_service.remove_folder_from_polling(folder_id)
        if success:
            return {
                "success": True,
                "message": f"Carpeta {folder_id} removida del polling"
            }
        else:
            raise HTTPException(status_code=404, detail="Carpeta no encontrada en polling")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al remover carpeta: {str(e)}")

@app.get("/api/changes/folder/polling/status")
async def get_folder_polling_status():
    """Obtener estado del polling de carpetas"""
    try:
        await initialize_change_detection_services()
        status = await polling_service.get_polling_status()
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estado: {str(e)}")

@app.get("/api/changes/folder/polling/folders")
async def get_folder_polling_folders():
    """Obtener estado de todas las carpetas en polling"""
    try:
        await initialize_change_detection_services()
        folders = await polling_service.get_all_folders_status()
        return {
            "success": True,
            "data": folders,
            "count": len(folders)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener carpetas: {str(e)}")

@app.get("/api/changes/folder/check/{folder_id}")
async def check_folder_for_new_documents(folder_id: str):
    """Verificar nuevos documentos en una carpeta específica"""
    try:
        await initialize_change_detection_services()
        changes = await change_detection_service.discover_new_documents_in_folder(folder_id)
        
        if changes:
            # Enviar notificaciones para cada nuevo documento
            for change in changes:
                notification = await notification_service.create_document_change_notification(
                    document_id=change.document_id,
                    document_title=change.document_title,
                    change_type=change.change_type,
                    content_preview=change.content_preview
                )
                await notification_service.send_notification(notification)
            
            return {
                "success": True,
                "data": {
                    "folder_id": folder_id,
                    "new_documents": len(changes),
                    "documents": [
                        {
                            "document_id": change.document_id,
                            "document_title": change.document_title,
                            "change_type": change.change_type,
                            "last_modified": change.last_modified.isoformat(),
                            "content_preview": change.content_preview
                        }
                        for change in changes
                    ]
                },
                "message": f"Se encontraron {len(changes)} nuevos documentos en la carpeta"
            }
        else:
            return {
                "success": True,
                "data": {
                    "folder_id": folder_id,
                    "new_documents": 0,
                    "documents": []
                },
                "message": "No se encontraron nuevos documentos en la carpeta"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al verificar carpeta: {str(e)}")

@app.get("/api/changes/folder/documents/{folder_id}")
async def get_documents_in_folder(folder_id: str):
    """Obtener lista de documentos en una carpeta"""
    try:
        await initialize_change_detection_services()
        documents = await change_detection_service._get_documents_in_folder(folder_id)
        return {
            "success": True,
            "data": {
                "folder_id": folder_id,
                "documents": documents,
                "count": len(documents)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener documentos de la carpeta: {str(e)}")

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Error interno del servidor",
            "message": str(exc) if os.getenv("DEBUG") == "True" else "Error interno"
        }
    )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "False").lower() == "true"
    
    print(f"🚀 Iniciando servidor integrado en http://{host}:{port}")
    print(f"📖 Health check: http://{host}:{port}/health")
    print(f"📚 Docs API: http://{host}:{port}/api/docs")
    print(f"🤖 Agent API: http://{host}:{port}/api/agent/")
    print(f"📖 Documentación: http://{host}:{port}/docs")
    
    uvicorn.run(
        "main_integrated:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if not debug else "debug"
    )
