import asyncio
import requests
import json
import os
import logging
import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.adk.agents import LlmAgent
from vertexai.preview.reasoning_engines import AdkApp
from dotenv import load_dotenv

# Carga segura de variables de entorno
load_dotenv()
logging.basicConfig(level=logging.INFO)

# --- Variables de entorno ---
SLACK_API_TOKEN = os.environ.get("SLACK_API_TOKEN")
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")
SLACK_CANVAS_ID = os.environ.get("SLACK_CANVAS_ID")
GOOGLE_DOCS_ID = os.environ.get("GOOGLE_DOCS_ID")

# --- Herramienta para leer Google Docs ---
def get_notes_from_google_docs(document_id: str) -> str:
    """
    Lee y devuelve el contenido de un documento de Google Docs.
    
    Args:
        document_id: El ID del documento de Google Docs.
    
    Returns:
        Una cadena de texto con el contenido del documento, incluyendo el título.
    """
    logging.info(f"Llamando a la API de Google Docs para leer el documento con ID: {document_id}")
    
    try:
        creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/documents.readonly'])
        service = build('docs', 'v1', credentials=creds)
        document = service.documents().get(documentId=document_id).execute()
        
        content = ""
        for element in document.get('body', {}).get('content', []):
            if 'paragraph' in element:
                for text_run in element['paragraph']['elements']:
                    content += text_run.get('textRun', {}).get('content', '')
        
        title = document.get('title', 'Notas de reunión')
        
        return f"TÍTULO DE LA REUNIÓN: {title}\n{content}"

    except HttpError as err:
        logging.error(f"Error al acceder a Google Docs: {err}")
        return f"Error: No se pudo acceder al documento con ID {document_id}"

# --- Herramientas para interactuar con Slack ---
def update_slack_canvas(canvas_id: str, markdown_content: str) -> str:
    """
    Actualiza el contenido de un canvas de Slack existente.
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

# --- Definición del agente principal ---
meeting_notes_agent = LlmAgent(
    name="meeting_notes_agent",
    model="gemini-2.5-pro",
    description="Agente que procesa notas de reuniones para crear/actualizar canvas en Slack.",
    instruction=(
        "Tu tarea es procesar las notas de una reunión, extraer las tareas pendientes y generar "
        "solo el contenido de las notas en formato Markdown. No generes JSON. "
        "Usa '#' para el título principal y '##' para secciones. "
        "Las tareas pendientes deben ir en listas con '-' y mencionar al responsable en negrita. "
        "Usa la herramienta 'get_notes_from_google_docs' primero para obtener el contenido en texto plano."
    ),
    output_key="meeting_notes",
    tools=[get_notes_from_google_docs, update_slack_canvas, create_slack_canvas]
)
# Creación de la app para Uvicorn (con Flask)
app = AdkApp(agent=meeting_notes_agent)

# --- Endpoint HTTP para el webhook de Drive ---
# @app.route("/", methods=["POST"])
# async def drive_webhook():
#     """Maneja las notificaciones push de la API de Drive."""
#     document_id = request.headers.get("X-Goog-Resource-Id")
#     if not document_id:
#         return jsonify({"message": "Notificación de Drive recibida, pero sin ID de documento."}), 200

#     logging.info(f"Notificación de Drive recibida para el documento: {document_id}")
    
#     title, document_content = get_notes_from_google_docs(document_id)

#     if "Error" in title:
#         return jsonify({"message": f"Error al procesar el documento: {document_content}"}), 500

#     if SLACK_CHANNEL_ID:
#         query = f"Crea un nuevo canvas en el canal '{SLACK_CHANNEL_ID}' con el título '{title}' y las notas '{document_content}'."
#     elif SLACK_CANVAS_ID:
#         query = f"Actualiza el canvas '{SLACK_CANVAS_ID}' con las notas '{document_content}'."
#     else:
#         return jsonify({"message": "Error: SLACK_CANVAS_ID o SLACK_CHANNEL_ID no configurado."}), 500

#     response_generator = app.async_stream_query(query=query)
    
#     final_response = "El agente está trabajando..."
#     async for event in response_generator:
#         if event.response:
#             final_response = event.response
#             logging.info(f"Respuesta final del agente: {final_response}")
#             break

#     return jsonify({"message": final_response}), 200

# --- Lógica de prueba local ---
if __name__ == "__main__":
    async def run_local_test():
        if not os.environ.get("GOOGLE_DOCS_ID"):
            print("Error: GOOGLE_DOCS_ID no configurado para pruebas locales.")
            return
        if not SLACK_API_TOKEN:
            print("Error: SLACK_API_TOKEN no configurado para pruebas locales.")
            return

        if SLACK_CHANNEL_ID:
            query = (f"Crea un nuevo canvas en el canal '{SLACK_CHANNEL_ID}' con las notas del documento '{GOOGLE_DOCS_ID}'.")
            print(f"Ejecutando el agente para crear un nuevo canvas en el canal: {SLACK_CHANNEL_ID}")
        elif SLACK_CANVAS_ID:
            query = (f"Actualiza el canvas '{SLACK_CANVAS_ID}' con las notas del documento '{GOOGLE_DOCS_ID}'.")
            print(f"Ejecutando el agente para actualizar el canvas: {SLACK_CANVAS_ID}")
        else:
            print("Error: Debes configurar SLACK_CHANNEL_ID o SLACK_CANVAS_ID para pruebas locales. Terminado.")
            return

        print(f"\n--- Ejecutando agente con la siguiente consulta: {query} ---")
        async for event in app.async_stream_query(message=query, user_id="local_test"):
            print("Resultado final:", event)
        
    asyncio.run(run_local_test())