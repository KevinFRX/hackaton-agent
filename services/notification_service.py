import os
import json
import asyncio
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

class NotificationType(Enum):
    """Tipos de notificaciones"""
    DOCUMENT_CHANGED = "document_changed"
    DOCUMENT_CREATED = "document_created"
    DOCUMENT_DELETED = "document_deleted"
    WEBHOOK_RECEIVED = "webhook_received"
    POLLING_DETECTED = "polling_detected"

@dataclass
class Notification:
    """Representa una notificación"""
    id: str
    type: NotificationType
    document_id: str
    document_title: str
    message: str
    timestamp: datetime
    data: Optional[Dict] = None
    sent: bool = False
    error: Optional[str] = None

class NotificationService:
    """Servicio para enviar notificaciones sobre cambios en documentos"""
    
    def __init__(self):
        self.notifications: List[Notification] = []
        self.webhook_endpoints: List[str] = []
        self.slack_config = {
            'token': os.getenv('SLACK_API_TOKEN'),
            'channel': os.getenv('SLACK_CHANNEL_ID')
        }
        self.email_config = {
            'smtp_server': os.getenv('SMTP_SERVER'),
            'smtp_port': int(os.getenv('SMTP_PORT', 587)),
            'username': os.getenv('EMAIL_USERNAME'),
            'password': os.getenv('EMAIL_PASSWORD'),
            'from_email': os.getenv('FROM_EMAIL')
        }
    
    def add_webhook_endpoint(self, url: str):
        """Agregar endpoint de webhook para notificaciones"""
        if url not in self.webhook_endpoints:
            self.webhook_endpoints.append(url)
            print(f"✅ Webhook endpoint agregado: {url}")
    
    def remove_webhook_endpoint(self, url: str):
        """Remover endpoint de webhook"""
        if url in self.webhook_endpoints:
            self.webhook_endpoints.remove(url)
            print(f"✅ Webhook endpoint removido: {url}")
    
    async def send_notification(self, notification: Notification) -> bool:
        """Enviar notificación a todos los canales configurados"""
        success = True
        
        # Enviar a webhooks
        for webhook_url in self.webhook_endpoints:
            if not await self._send_webhook_notification(notification, webhook_url):
                success = False
        
        # Enviar a Slack si está configurado
        if self.slack_config['token'] and self.slack_config['channel']:
            if not await self._send_slack_notification(notification):
                success = False
        
        # Enviar por email si está configurado
        if self.email_config['username'] and self.email_config['password']:
            if not await self._send_email_notification(notification):
                success = False
        
        notification.sent = success
        self.notifications.append(notification)
        
        # Mantener solo las últimas 1000 notificaciones
        if len(self.notifications) > 1000:
            self.notifications = self.notifications[-1000:]
        
        return success
    
    async def _send_webhook_notification(self, notification: Notification, webhook_url: str) -> bool:
        """Enviar notificación a webhook"""
        try:
            payload = {
                'notification': asdict(notification),
                'timestamp': notification.timestamp.isoformat(),
                'source': 'google-docs-change-detector'
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Notificación enviada a webhook: {webhook_url}")
                return True
            else:
                print(f"❌ Error en webhook {webhook_url}: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error al enviar webhook a {webhook_url}: {str(e)}")
            return False
    
    async def _send_slack_notification(self, notification: Notification) -> bool:
        """Enviar notificación a Slack"""
        try:
            # Crear mensaje para Slack
            emoji_map = {
                NotificationType.DOCUMENT_CHANGED: "📝",
                NotificationType.DOCUMENT_CREATED: "📄",
                NotificationType.DOCUMENT_DELETED: "🗑️",
                NotificationType.WEBHOOK_RECEIVED: "🔔",
                NotificationType.POLLING_DETECTED: "🔍"
            }
            
            emoji = emoji_map.get(notification.type, "📋")
            
            message = {
                'channel': self.slack_config['channel'],
                'text': f"{emoji} {notification.message}",
                'blocks': [
                    {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': f"*{notification.message}*\n\n"
                                   f"📄 *Documento:* {notification.document_title}\n"
                                   f"🆔 *ID:* `{notification.document_id}`\n"
                                   f"⏰ *Hora:* {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    }
                ]
            }
            
            if notification.data and 'content_preview' in notification.data:
                message['blocks'].append({
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f"*Vista previa:*\n```{notification.data['content_preview'][:200]}...```"
                    }
                })
            
            response = requests.post(
                'https://slack.com/api/chat.postMessage',
                headers={
                    'Authorization': f"Bearer {self.slack_config['token']}",
                    'Content-Type': 'application/json'
                },
                json=message,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    print(f"✅ Notificación enviada a Slack")
                    return True
                else:
                    print(f"❌ Error en Slack: {result.get('error')}")
                    return False
            else:
                print(f"❌ Error HTTP en Slack: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error al enviar notificación a Slack: {str(e)}")
            return False
    
    async def _send_email_notification(self, notification: Notification) -> bool:
        """Enviar notificación por email"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Crear mensaje de email
            msg = MIMEMultipart()
            msg['From'] = self.email_config['from_email']
            msg['To'] = os.getenv('NOTIFICATION_EMAIL', self.email_config['from_email'])
            msg['Subject'] = f"Cambio detectado en Google Docs: {notification.document_title}"
            
            body = f"""
            Se ha detectado un cambio en un documento de Google Docs:
            
            📄 Documento: {notification.document_title}
            🆔 ID: {notification.document_id}
            ⏰ Hora: {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
            📝 Mensaje: {notification.message}
            
            """
            
            if notification.data and 'content_preview' in notification.data:
                body += f"\nVista previa del contenido:\n{notification.data['content_preview']}\n"
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Enviar email
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['username'], self.email_config['password'])
            text = msg.as_string()
            server.sendmail(self.email_config['from_email'], msg['To'], text)
            server.quit()
            
            print(f"✅ Notificación enviada por email")
            return True
            
        except Exception as e:
            print(f"❌ Error al enviar email: {str(e)}")
            return False
    
    async def create_document_change_notification(
        self, 
        document_id: str, 
        document_title: str, 
        change_type: str,
        content_preview: Optional[str] = None
    ) -> Notification:
        """Crear notificación de cambio en documento"""
        
        type_map = {
            'created': NotificationType.DOCUMENT_CREATED,
            'modified': NotificationType.DOCUMENT_CHANGED,
            'deleted': NotificationType.DOCUMENT_DELETED,
            'webhook_notification': NotificationType.WEBHOOK_RECEIVED,
            'polling_detected': NotificationType.POLLING_DETECTED
        }
        
        notification_type = type_map.get(change_type, NotificationType.DOCUMENT_CHANGED)
        
        message_map = {
            NotificationType.DOCUMENT_CREATED: f"📄 Nuevo documento creado: {document_title}",
            NotificationType.DOCUMENT_CHANGED: f"📝 Documento modificado: {document_title}",
            NotificationType.DOCUMENT_DELETED: f"🗑️ Documento eliminado: {document_title}",
            NotificationType.WEBHOOK_RECEIVED: f"🔔 Webhook recibido para: {document_title}",
            NotificationType.POLLING_DETECTED: f"🔍 Cambio detectado por polling: {document_title}"
        }
        
        notification = Notification(
            id=f"notif-{document_id}-{int(datetime.now().timestamp())}",
            type=notification_type,
            document_id=document_id,
            document_title=document_title,
            message=message_map[notification_type],
            timestamp=datetime.now(),
            data={'content_preview': content_preview} if content_preview else None
        )
        
        return notification
    
    async def get_notification_history(self, limit: int = 100) -> List[Dict]:
        """Obtener historial de notificaciones"""
        return [asdict(notification) for notification in self.notifications[-limit:]]
    
    async def get_notification_stats(self) -> Dict:
        """Obtener estadísticas de notificaciones"""
        total = len(self.notifications)
        sent = sum(1 for n in self.notifications if n.sent)
        failed = total - sent
        
        type_counts = {}
        for notification in self.notifications:
            type_name = notification.type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        return {
            'total_notifications': total,
            'sent_successfully': sent,
            'failed': failed,
            'success_rate': (sent / total * 100) if total > 0 else 0,
            'by_type': type_counts,
            'active_webhooks': len(self.webhook_endpoints),
            'slack_configured': bool(self.slack_config['token']),
            'email_configured': bool(self.email_config['username'])
        }
