import os
import google.auth
from googleapiclient.discovery import build
import uuid

FOLDER_IDS = os.environ.get("FOLDER_IDS", "").split(',')
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

def get_drive_service():
    """Autentica y devuelve el servicio de la API de Drive."""
    creds, _ = google.auth.default(scopes=SCOPES)
    return build("drive", "v3", credentials=creds)

def register_drive_watches():
    """Registra un canal de notificaciones (watch) para cada ID de carpeta."""
    if not FOLDER_IDS or not WEBHOOK_URL:
        print("Error: Las variables de entorno FOLDER_IDS o WEBHOOK_URL no están configuradas.")
        return

    drive_service = get_drive_service()
    
    for folder_id in FOLDER_IDS:
        folder_id = folder_id.strip()
        if not folder_id:
            continue
        
        channel_id = str(uuid.uuid4())
        
        print(f"Registrando watch para la carpeta con ID: {folder_id}...")
        
        request_body = {
            'id': channel_id,
            'type': 'web_hook',
            'address': WEBHOOK_URL,
            'token': 'drive_notifications'
        }
        
        try:
            drive_service.files().watch(
                fileId=folder_id,
                body=request_body,
                supportsAllDrives=True
            ).execute()
            print(f"Watch registrado exitosamente para la carpeta {folder_id} con Channel ID: {channel_id}")
        except Exception as e:
            print(f"Error al registrar watch para la carpeta {folder_id}: {e}")

if __name__ == "__main__":
    register_drive_watches()