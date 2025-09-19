import asyncio
from typing import Dict, List, Any, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .auth_service import AuthService

class DocsService:
    def __init__(self):
        self.auth_service = AuthService()
        self.docs_service = None
        self.drive_service = None
        self.initialized = False

    async def _initialize_services(self) -> None:
        """Initialize Google Docs and Drive services"""
        if self.initialized:
            return

        try:
            # Initialize auth service first
            await self.auth_service.initialize()
            
            # Get credentials from auth service
            credentials = self.auth_service.get_credentials()
            
            # Build services
            self.docs_service = build('docs', 'v1', credentials=credentials)
            self.drive_service = build('drive', 'v3', credentials=credentials)
            self.initialized = True
            
        except Exception as e:
            raise Exception(f"Error al inicializar servicios de Google: {str(e)}")

    async def get_documents_list(self, page_size: int = 10, page_token: str = None) -> Dict[str, Any]:
        """Get list of documents from Google Drive"""
        try:
            await self._initialize_services()
            
            # Query for Google Docs files
            query = "mimeType='application/vnd.google-apps.document'"
            
            results = self.drive_service.files().list(
                q=query,
                pageSize=page_size,
                pageToken=page_token,
                fields='nextPageToken, files(id, name, createdTime, modifiedTime, webViewLink)',
                orderBy='modifiedTime desc'
            ).execute()
            
            files = results.get('files', [])
            
            return {
                "documents": files,
                "next_page_token": results.get('nextPageToken'),
                "total_count": len(files)
            }
            
        except HttpError as e:
            raise Exception(f"Error de Google API: {str(e)}")
        except Exception as e:
            raise Exception(f"Error al obtener lista de documentos: {str(e)}")

    async def get_document_by_id(self, document_id: str) -> Dict[str, Any]:
        """Get document by ID"""
        try:
            await self._initialize_services()
            
            # Get document
            document = self.docs_service.documents().get(documentId=document_id).execute()
            
            return self._parse_document_content(document)
            
        except HttpError as e:
            if e.resp.status == 404:
                raise Exception(f"Documento con ID '{document_id}' no encontrado")
            else:
                raise Exception(f"Error de Google API: {str(e)}")
        except Exception as e:
            raise Exception(f"Error al obtener documento: {str(e)}")

    async def get_document_by_name(self, document_name: str) -> Dict[str, Any]:
        """Get document by name"""
        try:
            await self._initialize_services()
            
            # Search for document by name
            query = f"name='{document_name}' and mimeType='application/vnd.google-apps.document'"
            
            results = self.drive_service.files().list(
                q=query,
                fields='files(id, name)'
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                raise Exception(f"Documento '{document_name}' no encontrado")
            
            document_id = files[0]['id']
            return await self.get_document_by_id(document_id)
            
        except Exception as e:
            raise Exception(f"Error al obtener documento por nombre: {str(e)}")

    async def search_documents(self, query: str, page_size: int = 10) -> Dict[str, Any]:
        """Search documents by content"""
        try:
            await self._initialize_services()
            
            # Search for documents containing the query
            search_query = f"fullText contains '{query}' and mimeType='application/vnd.google-apps.document'"
            
            results = self.drive_service.files().list(
                q=search_query,
                pageSize=page_size,
                fields='files(id, name, createdTime, modifiedTime, webViewLink)',
                orderBy='modifiedTime desc'
            ).execute()
            
            files = results.get('files', [])
            
            return {
                "documents": files,
                "query": query,
                "total_count": len(files)
            }
            
        except Exception as e:
            raise Exception(f"Error al buscar documentos: {str(e)}")

    def _parse_document_content(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Parse document content from Google Docs API response"""
        content = {
            "id": document.get("documentId"),
            "title": document.get("title", ""),
            "content": "",
            "plain_text": "",
            "elements": [],
            "metadata": {
                "revision_id": document.get("revisionId"),
                "document_id": document.get("documentId")
            }
        }

        if document.get("body") and document.get("body").get("content"):
            elements = document["body"]["content"]
            content["content"] = self._extract_text_from_elements(elements)
            content["plain_text"] = self._extract_plain_text(elements)
            content["elements"] = self._parse_elements(elements)

        return content

    def _extract_text_from_elements(self, elements: List[Dict[str, Any]]) -> str:
        """Extract formatted text from document elements"""
        text = ""
        
        for element in elements:
            if "paragraph" in element:
                text += self._extract_paragraph_text(element["paragraph"]) + "\n"
            elif "table" in element:
                text += self._extract_table_text(element["table"]) + "\n"
            elif "sectionBreak" in element:
                text += "\n---\n"
        
        return text.strip()

    def _extract_plain_text(self, elements: List[Dict[str, Any]]) -> str:
        """Extract plain text without formatting"""
        text = ""
        
        for element in elements:
            if "paragraph" in element:
                text += self._extract_plain_paragraph_text(element["paragraph"]) + "\n"
            elif "table" in element:
                text += self._extract_plain_table_text(element["table"]) + "\n"
        
        return text.strip()

    def _extract_paragraph_text(self, paragraph: Dict[str, Any]) -> str:
        """Extract text from paragraph with formatting"""
        if not paragraph.get("elements"):
            return ""
        
        return "".join([
            element.get("textRun", {}).get("content", "")
            for element in paragraph["elements"]
        ])

    def _extract_plain_paragraph_text(self, paragraph: Dict[str, Any]) -> str:
        """Extract plain text from paragraph"""
        if not paragraph.get("elements"):
            return ""
        
        text = "".join([
            element.get("textRun", {}).get("content", "").replace("\n", " ").strip()
            for element in paragraph["elements"]
        ])
        
        return text.strip()

    def _extract_table_text(self, table: Dict[str, Any]) -> str:
        """Extract text from table"""
        if not table.get("tableRows"):
            return ""
        
        rows = []
        for row in table["tableRows"]:
            if not row.get("tableCells"):
                continue
            
            cells = []
            for cell in row["tableCells"]:
                cell_content = self._extract_text_from_elements(cell.get("content", []))
                cells.append(cell_content)
            
            rows.append(" | ".join(cells))
        
        return "\n".join(rows)

    def _extract_plain_table_text(self, table: Dict[str, Any]) -> str:
        """Extract plain text from table"""
        if not table.get("tableRows"):
            return ""
        
        rows = []
        for row in table["tableRows"]:
            if not row.get("tableCells"):
                continue
            
            cells = []
            for cell in row["tableCells"]:
                cell_content = self._extract_plain_text(cell.get("content", []))
                cells.append(cell_content)
            
            rows.append(" | ".join(cells))
        
        return "\n".join(rows)

    def _parse_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse elements for structured data"""
        parsed_elements = []
        
        for index, element in enumerate(elements):
            parsed = {
                "index": index,
                "type": self._get_element_type(element)
            }

            if "paragraph" in element:
                parsed["content"] = self._extract_paragraph_text(element["paragraph"])
                parsed["plain_text"] = self._extract_plain_paragraph_text(element["paragraph"])
                parsed["style"] = element["paragraph"].get("paragraphStyle")
            elif "table" in element:
                parsed["content"] = self._extract_table_text(element["table"])
                parsed["plain_text"] = self._extract_plain_table_text(element["table"])
                parsed["rows"] = len(element["table"].get("tableRows", []))

            parsed_elements.append(parsed)

        return parsed_elements

    def _get_element_type(self, element: Dict[str, Any]) -> str:
        """Get element type"""
        if "paragraph" in element:
            return "paragraph"
        elif "table" in element:
            return "table"
        elif "sectionBreak" in element:
            return "sectionBreak"
        else:
            return "unknown"
