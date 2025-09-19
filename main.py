import asyncio
import requests
import json
import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from vertexai.preview.reasoning_engines import AdkApp

# Carga segura de variables de entorno
load_dotenv()
SLACK_API_TOKEN = os.environ.get("SLACK_API_TOKEN")
GOOGLE_DOCS_ID = os.environ.get("GOOGLE_DOCS_ID")
SLACK_CANVAS_ID = os.environ.get("SLACK_CANVAS_ID")
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")

# --- 1. Herramienta para leer Google Docs ---
def get_notes_from_google_docs(document_id: str) -> str:
    """
    Lee y devuelve el contenido de un documento de Google Docs.

    Args:
        document_id: El ID del documento de Google Docs.
    
    Returns:
        Una cadena de texto con el contenido del documento.
    """
    print(f"Llamando a la API de Google Docs para leer el documento con ID: {document_id}")
    sample_content = """
    TÍTULO DE LA REUNIÓN: KickOff con el cliente
    Resumen de la reunión del equipo:
    - Estado del proyecto X: En curso, sin retrasos.
    - Tareas pendientes:
        - Tarea 1: Actualizar el reporte de ventas. (Responsable: Juan)
        - Tarea 2: Enviar el resumen de la reunión a todo el equipo. (Responsable: María)
        - Tarea 3: Investigar la nueva API. (Responsable: Pedro)
    """
    return sample_content

# --- Herramientas para interactuar con Slack ---
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

# --- 3. Definición del agente principal ---
async def main():
    # Validar que todas las variables de entorno necesarias están configuradas
    if not GOOGLE_DOCS_ID:
        print("Error: La variable de entorno GOOGLE_DOCS_ID no está configurada.")
        return
    if not SLACK_API_TOKEN:
        print("Error: La variable de entorno SLACK_API_TOKEN no está configurada.")
        return
    
    # Decidir qué caso de uso ejecutar
    if SLACK_CHANNEL_ID:
        # Ejemplo para crear un nuevo canvas
        query_to_run = (f"Crea un nuevo canvas en el canal '{SLACK_CHANNEL_ID}' con las notas del "
                           f"documento '{GOOGLE_DOCS_ID}'.")
    elif SLACK_CANVAS_ID:
        # Ejemplo para actualizar un canvas existente
        query_to_run = (f"Actualiza el canvas '{SLACK_CANVAS_ID}' con las notas del "
                           f"documento '{GOOGLE_DOCS_ID}'.")
    else:
        print("Error: Debes configurar SLACK_CHANNEL_ID o SLACK_CANVAS_ID.")
        return

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

    # --- 4. Ejecución del agente con la consulta seleccionada ---
    app = AdkApp(agent=meeting_notes_agent)
    
    print(f"\n--- Ejecutando agente con la siguiente consulta: {query_to_run} ---")
    async for event in app.async_stream_query(message=query_to_run, user_id="123"):
        print(event)

if __name__ == "__main__":
    asyncio.run(main())