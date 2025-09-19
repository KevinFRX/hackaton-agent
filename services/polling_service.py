import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import logging

from .change_detection_service import ChangeDetectionService, DocumentChange
from .notification_service import NotificationService, NotificationType

@dataclass
class PollingConfig:
    """Configuración de polling para un documento"""
    document_id: str
    document_title: str
    interval_seconds: int
    enabled: bool = True
    last_checked: Optional[datetime] = None
    last_change: Optional[datetime] = None
    consecutive_failures: int = 0
    max_failures: int = 5

@dataclass
class FolderPollingConfig:
    """Configuración de polling para una carpeta"""
    folder_id: str
    folder_name: str
    interval_seconds: int
    enabled: bool = True
    last_checked: Optional[datetime] = None
    last_discovery: Optional[datetime] = None
    consecutive_failures: int = 0
    max_failures: int = 5

class PollingService:
    """Servicio para polling automático de documentos"""
    
    def __init__(self, change_detection_service: ChangeDetectionService, notification_service: NotificationService):
        self.change_detection_service = change_detection_service
        self.notification_service = notification_service
        self.polling_configs: Dict[str, PollingConfig] = {}
        self.folder_polling_configs: Dict[str, FolderPollingConfig] = {}
        self.running = False
        self.polling_task: Optional[asyncio.Task] = None
        self.logger = logging.getLogger(__name__)
        
        # Configuración por defecto
        self.default_interval = 300  # 5 minutos
        self.min_interval = 60      # 1 minuto mínimo
        self.max_interval = 3600    # 1 hora máximo
        
    async def start_polling(self):
        """Iniciar el servicio de polling"""
        if self.running:
            self.logger.warning("Polling service ya está ejecutándose")
            return
        
        self.running = True
        self.polling_task = asyncio.create_task(self._polling_loop())
        self.logger.info("🚀 Polling service iniciado")
    
    async def stop_polling(self):
        """Detener el servicio de polling"""
        if not self.running:
            return
        
        self.running = False
        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("🛑 Polling service detenido")
    
    async def add_document(self, document_id: str, document_title: str = None, interval_seconds: int = None) -> bool:
        """Agregar documento para polling"""
        try:
            if document_id in self.polling_configs:
                self.logger.warning(f"Documento {document_id} ya está en polling")
                return False
            
            interval = interval_seconds or self.default_interval
            interval = max(self.min_interval, min(interval, self.max_interval))
            
            config = PollingConfig(
                document_id=document_id,
                document_title=document_title or f"Documento {document_id}",
                interval_seconds=interval
            )
            
            self.polling_configs[document_id] = config
            self.logger.info(f"✅ Documento agregado al polling: {config.document_title} (cada {interval}s)")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error al agregar documento al polling: {str(e)}")
            return False
    
    async def remove_document(self, document_id: str) -> bool:
        """Remover documento del polling"""
        try:
            if document_id not in self.polling_configs:
                self.logger.warning(f"Documento {document_id} no está en polling")
                return False
            
            config = self.polling_configs.pop(document_id)
            self.logger.info(f"✅ Documento removido del polling: {config.document_title}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error al remover documento del polling: {str(e)}")
            return False
    
    async def update_document_interval(self, document_id: str, interval_seconds: int) -> bool:
        """Actualizar intervalo de polling para un documento"""
        try:
            if document_id not in self.polling_configs:
                self.logger.warning(f"Documento {document_id} no está en polling")
                return False
            
            interval = max(self.min_interval, min(interval_seconds, self.max_interval))
            self.polling_configs[document_id].interval_seconds = interval
            
            self.logger.info(f"✅ Intervalo actualizado para {document_id}: {interval}s")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error al actualizar intervalo: {str(e)}")
            return False
    
    async def enable_document_polling(self, document_id: str) -> bool:
        """Habilitar polling para un documento"""
        if document_id in self.polling_configs:
            self.polling_configs[document_id].enabled = True
            self.logger.info(f"✅ Polling habilitado para documento: {document_id}")
            return True
        return False
    
    async def disable_document_polling(self, document_id: str) -> bool:
        """Deshabilitar polling para un documento"""
        if document_id in self.polling_configs:
            self.polling_configs[document_id].enabled = False
            self.logger.info(f"⏸️ Polling deshabilitado para documento: {document_id}")
            return True
        return False
    
    async def _polling_loop(self):
        """Loop principal de polling"""
        self.logger.info("🔄 Iniciando loop de polling")
        
        while self.running:
            try:
                await self._check_all_documents()
                await asyncio.sleep(10)  # Verificar cada 10 segundos si hay documentos listos
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Error en polling loop: {str(e)}")
                await asyncio.sleep(30)  # Esperar 30 segundos antes de reintentar
    
    async def _check_all_documents(self):
        """Verificar todos los documentos y carpetas configurados"""
        now = datetime.now()
        documents_to_check = []
        folders_to_check = []
        
        # Verificar documentos
        for config in self.polling_configs.values():
            if not config.enabled:
                continue
            
            # Verificar si es hora de hacer polling
            if config.last_checked is None:
                # Primera verificación
                documents_to_check.append(config)
            else:
                time_since_last_check = (now - config.last_checked).total_seconds()
                if time_since_last_check >= config.interval_seconds:
                    documents_to_check.append(config)
        
        # Verificar carpetas
        for config in self.folder_polling_configs.values():
            if not config.enabled:
                continue
            
            # Verificar si es hora de hacer polling
            if config.last_checked is None:
                # Primera verificación
                folders_to_check.append(config)
            else:
                time_since_last_check = (now - config.last_checked).total_seconds()
                if time_since_last_check >= config.interval_seconds:
                    folders_to_check.append(config)
        
        if not documents_to_check and not folders_to_check:
            return
        
        self.logger.info(f"🔍 Verificando {len(documents_to_check)} documentos y {len(folders_to_check)} carpetas")
        
        # Verificar documentos y carpetas en paralelo
        tasks = []
        for config in documents_to_check:
            task = asyncio.create_task(self._check_single_document(config))
            tasks.append(task)
        
        for config in folders_to_check:
            task = asyncio.create_task(self._check_single_folder(config))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_single_document(self, config: PollingConfig):
        """Verificar un documento individual"""
        try:
            # Actualizar timestamp de última verificación
            config.last_checked = datetime.now()
            
            # Verificar cambios
            change = await self.change_detection_service.check_document_changes(config.document_id)
            
            if change:
                # Documento ha cambiado
                config.last_change = datetime.now()
                config.consecutive_failures = 0
                
                self.logger.info(f"📝 Cambio detectado en: {config.document_title}")
                
                # Crear y enviar notificación
                notification = await self.notification_service.create_document_change_notification(
                    document_id=config.document_id,
                    document_title=config.document_title,
                    change_type='polling_detected',
                    content_preview=change.content_preview
                )
                
                await self.notification_service.send_notification(notification)
                
            else:
                # No hay cambios
                config.consecutive_failures = 0
                
        except Exception as e:
            config.consecutive_failures += 1
            self.logger.error(f"❌ Error al verificar documento {config.document_id}: {str(e)}")
            
            # Si hay demasiados fallos consecutivos, deshabilitar temporalmente
            if config.consecutive_failures >= config.max_failures:
                config.enabled = False
                self.logger.warning(f"⚠️ Documento {config.document_id} deshabilitado por {config.max_failures} fallos consecutivos")
    
    async def _check_single_folder(self, config: FolderPollingConfig):
        """Verificar una carpeta individual en busca de nuevos documentos"""
        try:
            # Actualizar timestamp de última verificación
            config.last_checked = datetime.now()
            
            # Descubrir nuevos documentos en la carpeta
            changes = await self.change_detection_service.discover_new_documents_in_folder(config.folder_id)
            
            if changes:
                # Se encontraron nuevos documentos
                config.last_discovery = datetime.now()
                config.consecutive_failures = 0
                
                self.logger.info(f"🆕 {len(changes)} nuevos documentos encontrados en: {config.folder_name}")
                
                # Enviar notificaciones para cada nuevo documento
                for change in changes:
                    notification = await self.notification_service.create_document_change_notification(
                        document_id=change.document_id,
                        document_title=change.document_title,
                        change_type='created',
                        content_preview=change.content_preview
                    )
                    
                    await self.notification_service.send_notification(notification)
                
            else:
                # No hay nuevos documentos
                config.consecutive_failures = 0
                
        except Exception as e:
            config.consecutive_failures += 1
            self.logger.error(f"❌ Error al verificar carpeta {config.folder_id}: {str(e)}")
            
            # Si hay demasiados fallos consecutivos, deshabilitar temporalmente
            if config.consecutive_failures >= config.max_failures:
                config.enabled = False
                self.logger.warning(f"⚠️ Carpeta {config.folder_id} deshabilitada por {config.max_failures} fallos consecutivos")
    
    async def get_polling_status(self) -> Dict:
        """Obtener estado del servicio de polling"""
        now = datetime.now()
        active_documents = 0
        documents_ready = 0
        active_folders = 0
        folders_ready = 0
        
        # Contar documentos
        for config in self.polling_configs.values():
            if config.enabled:
                active_documents += 1
                if config.last_checked is None:
                    documents_ready += 1
                else:
                    time_since_last_check = (now - config.last_checked).total_seconds()
                    if time_since_last_check >= config.interval_seconds:
                        documents_ready += 1
        
        # Contar carpetas
        for config in self.folder_polling_configs.values():
            if config.enabled:
                active_folders += 1
                if config.last_checked is None:
                    folders_ready += 1
                else:
                    time_since_last_check = (now - config.last_checked).total_seconds()
                    if time_since_last_check >= config.interval_seconds:
                        folders_ready += 1
        
        return {
            'running': self.running,
            'total_documents': len(self.polling_configs),
            'active_documents': active_documents,
            'documents_ready_for_check': documents_ready,
            'total_folders': len(self.folder_polling_configs),
            'active_folders': active_folders,
            'folders_ready_for_check': folders_ready,
            'default_interval': self.default_interval,
            'min_interval': self.min_interval,
            'max_interval': self.max_interval
        }
    
    async def get_document_status(self, document_id: str) -> Optional[Dict]:
        """Obtener estado de polling para un documento específico"""
        if document_id not in self.polling_configs:
            return None
        
        config = self.polling_configs[document_id]
        now = datetime.now()
        
        time_since_last_check = None
        if config.last_checked:
            time_since_last_check = (now - config.last_checked).total_seconds()
        
        time_since_last_change = None
        if config.last_change:
            time_since_last_change = (now - config.last_change).total_seconds()
        
        return {
            'document_id': config.document_id,
            'document_title': config.document_title,
            'enabled': config.enabled,
            'interval_seconds': config.interval_seconds,
            'last_checked': config.last_checked.isoformat() if config.last_checked else None,
            'last_change': config.last_change.isoformat() if config.last_change else None,
            'time_since_last_check': time_since_last_check,
            'time_since_last_change': time_since_last_change,
            'consecutive_failures': config.consecutive_failures,
            'max_failures': config.max_failures,
            'ready_for_check': time_since_last_check is None or time_since_last_check >= config.interval_seconds
        }
    
    async def get_all_documents_status(self) -> List[Dict]:
        """Obtener estado de todos los documentos en polling"""
        statuses = []
        for document_id in self.polling_configs:
            status = await self.get_document_status(document_id)
            if status:
                statuses.append(status)
        return statuses
    
    # --- Métodos para Polling de Carpetas ---
    
    async def add_folder_to_polling(self, folder_id: str, folder_name: str = None, interval_seconds: int = None) -> bool:
        """Agregar carpeta para polling de nuevos documentos"""
        try:
            if folder_id in self.folder_polling_configs:
                self.logger.warning(f"Carpeta {folder_id} ya está en polling")
                return False
            
            interval = interval_seconds or self.default_interval
            interval = max(self.min_interval, min(interval, self.max_interval))
            
            config = FolderPollingConfig(
                folder_id=folder_id,
                folder_name=folder_name or f"Carpeta {folder_id}",
                interval_seconds=interval
            )
            
            self.folder_polling_configs[folder_id] = config
            self.logger.info(f"✅ Carpeta agregada al polling: {config.folder_name} (cada {interval}s)")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error al agregar carpeta al polling: {str(e)}")
            return False
    
    async def remove_folder_from_polling(self, folder_id: str) -> bool:
        """Remover carpeta del polling"""
        try:
            if folder_id not in self.folder_polling_configs:
                self.logger.warning(f"Carpeta {folder_id} no está en polling")
                return False
            
            config = self.folder_polling_configs.pop(folder_id)
            self.logger.info(f"✅ Carpeta removida del polling: {config.folder_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error al remover carpeta del polling: {str(e)}")
            return False
    
    async def get_folder_polling_status(self, folder_id: str) -> Optional[Dict]:
        """Obtener estado de polling para una carpeta específica"""
        if folder_id not in self.folder_polling_configs:
            return None
        
        config = self.folder_polling_configs[folder_id]
        now = datetime.now()
        
        time_since_last_check = None
        if config.last_checked:
            time_since_last_check = (now - config.last_checked).total_seconds()
        
        time_since_last_discovery = None
        if config.last_discovery:
            time_since_last_discovery = (now - config.last_discovery).total_seconds()
        
        return {
            'folder_id': config.folder_id,
            'folder_name': config.folder_name,
            'enabled': config.enabled,
            'interval_seconds': config.interval_seconds,
            'last_checked': config.last_checked.isoformat() if config.last_checked else None,
            'last_discovery': config.last_discovery.isoformat() if config.last_discovery else None,
            'time_since_last_check': time_since_last_check,
            'time_since_last_discovery': time_since_last_discovery,
            'consecutive_failures': config.consecutive_failures,
            'max_failures': config.max_failures,
            'ready_for_check': time_since_last_check is None or time_since_last_check >= config.interval_seconds
        }
    
    async def get_all_folders_status(self) -> List[Dict]:
        """Obtener estado de todas las carpetas en polling"""
        statuses = []
        for folder_id in self.folder_polling_configs:
            status = await self.get_folder_polling_status(folder_id)
            if status:
                statuses.append(status)
        return statuses
