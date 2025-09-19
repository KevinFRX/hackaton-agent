import os
from google.auth import default
from google.auth.exceptions import DefaultCredentialsError
from google.oauth2 import service_account
import asyncio
from typing import Dict, Any

class AuthService:
    def __init__(self):
        self.credentials = None
        self.project_id = None
        self.authenticated = False

    async def initialize(self) -> None:
        """Initialize authentication using Service Account or Application Default Credentials"""
        try:
            # Try Service Account first
            service_account_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH")
            if service_account_path and os.path.exists(service_account_path):
                self.credentials = service_account.Credentials.from_service_account_file(
                    service_account_path,
                    scopes=[
                        'https://www.googleapis.com/auth/documents.readonly',
                        'https://www.googleapis.com/auth/drive.readonly',
                        'https://www.googleapis.com/auth/cloud-platform'
                    ]
                )
                self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "docdash-ai-dev")
                self.authenticated = True
                print(f"✅ Autenticación exitosa con Service Account: {self.project_id}")
            else:
                # Fallback to Application Default Credentials
                self.credentials, self.project_id = await asyncio.get_event_loop().run_in_executor(
                    None, default
                )
                self.authenticated = True
                print(f"✅ Autenticación exitosa con ADC: {self.project_id}")
        except DefaultCredentialsError as e:
            self.authenticated = False
            raise Exception(f"Error de autenticación: {str(e)}")

    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.authenticated and self.credentials is not None

    async def get_project_info(self) -> Dict[str, Any]:
        """Get current project information"""
        try:
            if not self.authenticated:
                await self.initialize()
            
            return {
                "authenticated": self.authenticated,
                "project_id": self.project_id,
                "message": f"Autenticado con proyecto: {self.project_id}" if self.authenticated else "No autenticado"
            }
        except Exception as e:
            return {
                "authenticated": False,
                "project_id": None,
                "error": str(e),
                "message": "Error al obtener información del proyecto"
            }

    def get_credentials(self):
        """Get current credentials"""
        if not self.authenticated:
            raise Exception("No autenticado. Ejecuta: gcloud auth application-default login")
        return self.credentials

    def get_project_id(self) -> str:
        """Get current project ID"""
        if not self.authenticated:
            raise Exception("No autenticado. Ejecuta: gcloud auth application-default login")
        return self.project_id