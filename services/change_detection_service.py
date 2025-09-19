import os
import json
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.auth.exceptions import GoogleAuthError
import requests
from dataclasses import dataclass, asdict

@dataclass
class DocumentChange:
    """Representa un cambio en un documento"""
    document_id: str
    document_title: str
    revision_id: str
    last_modified: datetime
    change_type: str  # 'created', 'modified', 'deleted'
    content_preview: Optional[str] = None
    webhook_id: Optional[str] = None

@dataclass
class WebhookConfig:
    """Configuración de webhook"""
    document_id: str
    webhook_url: str
    webhook_id: str
    resource_id: str
    expiration: datetime
    active: bool = True

@dataclass
class FolderConfig:
    """Configuración de monitoreo de carpeta"""
    folder_id: str
    folder_name: str
    webhook_url: str
    webhook_id: str
    resource_id: str
    expiration: datetime
    active: bool = True
    monitored_documents: List[str] = None  # Lista de IDs de documentos monitoreados
    
    def __post_init__(self):
        if self.monitored_documents is None:
            self.monitored_documents = []

class ChangeDetectionService:
    """Servicio para detectar cambios en Google Docs"""
    
    def __init__(self, credentials, project_id: str):
        self.credentials = credentials
        self.project_id = project_id
        self.drive_service = None
        self.docs_service = None
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.folder_webhooks: Dict[str, FolderConfig] = {}
        self.document_states: Dict[str, str] = {}  # document_id -> last_revision_id
        self.change_history: List[DocumentChange] = []
        self.initialized = False
        
    async def initialize(self):
        """Inicializar servicios de Google"""
        try:
            self.drive_service = build('drive', 'v3', credentials=self.credentials)
            self.docs_service = build('docs', 'v1', credentials=self.credentials)
            self.initialized = True
            print("✅ Change Detection Service inicializado")
        except Exception as e:
            raise Exception(f"Error al inicializar Change Detection Service: {str(e)}")
    
    async def setup_webhook(self, document_id: str, webhook_url: str) -> WebhookConfig:
        """Configurar webhook para un documento específico"""
        if not self.initialized:
            await self.initialize()
            
        try:
            # Obtener información del archivo
            file_info = self.drive_service.files().get(
                fileId=document_id,
                fields='id,name,modifiedTime'
            ).execute()
            
            # Configurar webhook
            webhook_request = {
                'id': f"webhook-{document_id}-{int(time.time())}",
                'type': 'web_hook',
                'address': webhook_url,
                'payload': True
            }
            
            # Crear webhook
            webhook_response = self.drive_service.files().watch(
                fileId=document_id,
                body=webhook_request
            ).execute()
            
            # Calcular expiración (máximo 7 días para webhooks)
            expiration = datetime.now() + timedelta(days=6, hours=23, minutes=59)
            
            webhook_config = WebhookConfig(
                document_id=document_id,
                webhook_url=webhook_url,
                webhook_id=webhook_response['id'],
                resource_id=webhook_response['resourceId'],
                expiration=expiration
            )
            
            self.webhooks[document_id] = webhook_config
            
            print(f"✅ Webhook configurado para documento: {file_info.get('name', document_id)}")
            return webhook_config
            
        except Exception as e:
            raise Exception(f"Error al configurar webhook: {str(e)}")
    
    async def remove_webhook(self, document_id: str) -> bool:
        """Remover webhook de un documento"""
        if document_id not in self.webhooks:
            return False
            
        try:
            webhook_config = self.webhooks[document_id]
            
            # Detener webhook
            self.drive_service.channels().stop(
                body={
                    'id': webhook_config.webhook_id,
                    'resourceId': webhook_config.resource_id
                }
            ).execute()
            
            del self.webhooks[document_id]
            print(f"✅ Webhook removido para documento: {document_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error al remover webhook: {str(e)}")
            return False
    
    async def check_document_changes(self, document_id: str) -> Optional[DocumentChange]:
        """Verificar si un documento ha cambiado"""
        if not self.initialized:
            await self.initialize()
            
        try:
            # Obtener información del documento
            doc_info = self.docs_service.documents().get(documentId=document_id).execute()
            current_revision_id = doc_info.get('revisionId')
            document_title = doc_info.get('title', 'Sin título')
            
            # Verificar si es un cambio nuevo
            last_revision_id = self.document_states.get(document_id)
            
            if last_revision_id is None:
                # Primera vez que vemos este documento
                self.document_states[document_id] = current_revision_id
                change = DocumentChange(
                    document_id=document_id,
                    document_title=document_title,
                    revision_id=current_revision_id,
                    last_modified=datetime.now(),
                    change_type='created',
                    content_preview=self._extract_content_preview(doc_info)
                )
            elif last_revision_id != current_revision_id:
                # Documento ha cambiado
                self.document_states[document_id] = current_revision_id
                change = DocumentChange(
                    document_id=document_id,
                    document_title=document_title,
                    revision_id=current_revision_id,
                    last_modified=datetime.now(),
                    change_type='modified',
                    content_preview=self._extract_content_preview(doc_info)
                )
            else:
                # No hay cambios
                return None
            
            # Agregar a historial
            self.change_history.append(change)
            
            # Mantener solo los últimos 100 cambios
            if len(self.change_history) > 100:
                self.change_history = self.change_history[-100:]
            
            return change
            
        except Exception as e:
            print(f"❌ Error al verificar cambios en documento {document_id}: {str(e)}")
            return None
    
    async def poll_documents(self, document_ids: List[str], interval_seconds: int = 300) -> List[DocumentChange]:
        """Verificar cambios en múltiples documentos periódicamente"""
        changes = []
        
        for document_id in document_ids:
            try:
                change = await self.check_document_changes(document_id)
                if change:
                    changes.append(change)
            except Exception as e:
                print(f"❌ Error en polling para documento {document_id}: {str(e)}")
        
        return changes
    
    def _extract_content_preview(self, doc_info: Dict) -> str:
        """Extraer una vista previa del contenido del documento"""
        try:
            content = doc_info.get('body', {}).get('content', [])
            text_parts = []
            
            for element in content[:5]:  # Solo primeros 5 elementos
                if 'paragraph' in element:
                    paragraph = element['paragraph']
                    for text_run in paragraph.get('elements', []):
                        if 'textRun' in text_run:
                            text = text_run['textRun'].get('content', '')
                            if text.strip():
                                text_parts.append(text.strip())
            
            preview = ' '.join(text_parts)[:200]  # Máximo 200 caracteres
            return preview + '...' if len(preview) == 200 else preview
            
        except Exception:
            return "No se pudo extraer contenido"
    
    async def get_change_history(self, limit: int = 50) -> List[Dict]:
        """Obtener historial de cambios"""
        return [asdict(change) for change in self.change_history[-limit:]]
    
    async def get_active_webhooks(self) -> List[Dict]:
        """Obtener lista de webhooks activos"""
        return [asdict(webhook) for webhook in self.webhooks.values()]
    
    async def setup_folder_webhook(self, folder_id: str, webhook_url: str) -> FolderConfig:
        """Configurar webhook para una carpeta completa"""
        if not self.initialized:
            await self.initialize()
            
        try:
            # Obtener información de la carpeta
            folder_info = self.drive_service.files().get(
                fileId=folder_id,
                fields='id,name'
            ).execute()
            
            # Configurar webhook para la carpeta
            webhook_request = {
                'id': f"folder-webhook-{folder_id}-{int(time.time())}",
                'type': 'web_hook',
                'address': webhook_url,
                'payload': True
            }
            
            # Crear webhook para la carpeta
            webhook_response = self.drive_service.files().watch(
                fileId=folder_id,
                body=webhook_request
            ).execute()
            
            # Calcular expiración (máximo 7 días para webhooks)
            expiration = datetime.now() + timedelta(days=6, hours=23, minutes=59)
            
            # Obtener lista inicial de documentos en la carpeta
            documents = await self._get_documents_in_folder(folder_id)
            
            folder_config = FolderConfig(
                folder_id=folder_id,
                folder_name=folder_info.get('name', f'Carpeta {folder_id}'),
                webhook_url=webhook_url,
                webhook_id=webhook_response['id'],
                resource_id=webhook_response['resourceId'],
                expiration=expiration,
                monitored_documents=[doc['id'] for doc in documents]
            )
            
            self.folder_webhooks[folder_id] = folder_config
            
            print(f"✅ Webhook configurado para carpeta: {folder_config.folder_name} ({len(documents)} documentos)")
            return folder_config
            
        except Exception as e:
            raise Exception(f"Error al configurar webhook de carpeta: {str(e)}")
    
    async def _get_documents_in_folder(self, folder_id: str) -> List[Dict]:
        """Obtener todos los documentos de Google Docs en una carpeta"""
        try:
            # Buscar documentos de Google Docs en la carpeta
            query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
            
            results = self.drive_service.files().list(
                q=query,
                fields='files(id,name,modifiedTime,createdTime)',
                pageSize=1000
            ).execute()
            
            documents = results.get('files', [])
            print(f"📄 Encontrados {len(documents)} documentos en la carpeta {folder_id}")
            
            return documents
            
        except Exception as e:
            print(f"❌ Error al obtener documentos de la carpeta: {str(e)}")
            return []
    
    async def remove_folder_webhook(self, folder_id: str) -> bool:
        """Remover webhook de una carpeta"""
        if folder_id not in self.folder_webhooks:
            return False
            
        try:
            folder_config = self.folder_webhooks[folder_id]
            
            # Detener webhook
            self.drive_service.channels().stop(
                body={
                    'id': folder_config.webhook_id,
                    'resourceId': folder_config.resource_id
                }
            ).execute()
            
            del self.folder_webhooks[folder_id]
            print(f"✅ Webhook de carpeta removido: {folder_config.folder_name}")
            return True
            
        except Exception as e:
            print(f"❌ Error al remover webhook de carpeta: {str(e)}")
            return False
    
    async def get_folder_webhooks(self) -> List[Dict]:
        """Obtener lista de webhooks de carpetas activos"""
        return [asdict(folder_webhook) for folder_webhook in self.folder_webhooks.values()]
    
    async def discover_new_documents_in_folder(self, folder_id: str) -> List[DocumentChange]:
        """Descubrir nuevos documentos en una carpeta monitoreada"""
        if folder_id not in self.folder_webhooks:
            return []
        
        try:
            folder_config = self.folder_webhooks[folder_id]
            current_documents = await self._get_documents_in_folder(folder_id)
            current_doc_ids = {doc['id'] for doc in current_documents}
            known_doc_ids = set(folder_config.monitored_documents)
            
            # Encontrar documentos nuevos
            new_doc_ids = current_doc_ids - known_doc_ids
            changes = []
            
            for doc_id in new_doc_ids:
                # Buscar información del documento
                doc_info = next((doc for doc in current_documents if doc['id'] == doc_id), None)
                if doc_info:
                    change = DocumentChange(
                        document_id=doc_id,
                        document_title=doc_info.get('name', 'Sin título'),
                        revision_id=f"new-{int(time.time())}",
                        last_modified=datetime.now(),
                        change_type='created',
                        content_preview=f"Nuevo documento creado en {folder_config.folder_name}"
                    )
                    changes.append(change)
                    self.change_history.append(change)
            
            # Actualizar lista de documentos monitoreados
            folder_config.monitored_documents = list(current_doc_ids)
            
            if changes:
                print(f"🆕 Descubiertos {len(changes)} nuevos documentos en {folder_config.folder_name}")
            
            return changes
            
        except Exception as e:
            print(f"❌ Error al descubrir nuevos documentos: {str(e)}")
            return []
    
    async def check_all_monitored_folders(self) -> List[DocumentChange]:
        """Verificar todos los folders monitoreados en busca de nuevos documentos"""
        all_changes = []
        
        for folder_id in self.folder_webhooks:
            try:
                changes = await self.discover_new_documents_in_folder(folder_id)
                all_changes.extend(changes)
            except Exception as e:
                print(f"❌ Error al verificar carpeta {folder_id}: {str(e)}")
        
        return all_changes
    
    async def cleanup_expired_webhooks(self):
        """Limpiar webhooks expirados"""
        now = datetime.now()
        expired_webhooks = []
        expired_folder_webhooks = []
        
        # Limpiar webhooks de documentos
        for doc_id, webhook in self.webhooks.items():
            if webhook.expiration < now:
                expired_webhooks.append(doc_id)
        
        for doc_id in expired_webhooks:
            await self.remove_webhook(doc_id)
            print(f"🧹 Webhook expirado removido para documento: {doc_id}")
        
        # Limpiar webhooks de carpetas
        for folder_id, folder_webhook in self.folder_webhooks.items():
            if folder_webhook.expiration < now:
                expired_folder_webhooks.append(folder_id)
        
        for folder_id in expired_folder_webhooks:
            await self.remove_folder_webhook(folder_id)
            print(f"🧹 Webhook expirado removido para carpeta: {folder_id}")
    
    def process_webhook_notification(self, notification_data: Dict) -> Optional[DocumentChange]:
        """Procesar notificación de webhook"""
        try:
            # Extraer información de la notificación
            resource_id = notification_data.get('resourceId')
            document_id = notification_data.get('fileId')
            
            if not document_id:
                return None
            
            # Buscar el webhook correspondiente
            webhook_config = None
            for webhook in self.webhooks.values():
                if webhook.resource_id == resource_id:
                    webhook_config = webhook
                    break
            
            if not webhook_config:
                return None
            
            # Crear cambio basado en la notificación
            change = DocumentChange(
                document_id=document_id,
                document_title=f"Documento {document_id}",
                revision_id=f"webhook-{int(time.time())}",
                last_modified=datetime.now(),
                change_type='webhook_notification',
                webhook_id=webhook_config.webhook_id
            )
            
            # Agregar a historial
            self.change_history.append(change)
            
            return change
            
        except Exception as e:
            print(f"❌ Error al procesar notificación de webhook: {str(e)}")
            return None
