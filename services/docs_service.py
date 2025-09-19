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
    
    async def get_document_tabs(self, document_id: str) -> Dict[str, Any]:
        """Get tabs/sections structure from a Google Docs document"""
        try:
            await self._initialize_services()
            
            # Get the document
            doc = self.docs_service.documents().get(documentId=document_id).execute()
            
            # Extract tabs/sections from the document structure
            tabs = []
            current_tab = None
            tab_index = 0
            
            # Process document content to identify tabs/sections
            content = doc.get('body', {}).get('content', [])
            
            for element in content:
                if 'paragraph' in element:
                    paragraph = element['paragraph']
                    text_content = self._extract_paragraph_text(paragraph)
                    
                    # Check if this looks like a tab/section header
                    if self._is_tab_header(text_content):
                        # Save previous tab if exists
                        if current_tab:
                            tabs.append(current_tab)
                        
                        # Start new tab
                        current_tab = {
                            'index': tab_index,
                            'title': text_content.strip(),
                            'content': [],
                            'start_position': element.get('startIndex', 0),
                            'end_position': element.get('endIndex', 0)
                        }
                        tab_index += 1
                    
                    # Add content to current tab
                    if current_tab:
                        current_tab['content'].append({
                            'type': 'paragraph',
                            'text': text_content,
                            'position': element.get('startIndex', 0)
                        })
                        current_tab['end_position'] = element.get('endIndex', 0)
                
                elif 'table' in element:
                    # Handle tables
                    if current_tab:
                        table_content = self._extract_table_content(element['table'])
                        current_tab['content'].append({
                            'type': 'table',
                            'data': table_content,
                            'position': element.get('startIndex', 0)
                        })
                        current_tab['end_position'] = element.get('endIndex', 0)
            
            # Add the last tab if exists
            if current_tab:
                tabs.append(current_tab)
            
            # If no tabs found, create a single tab with all content
            if not tabs:
                tabs = [{
                    'index': 0,
                    'title': 'Documento completo',
                    'content': self._extract_all_content(content),
                    'start_position': 0,
                    'end_position': len(content)
                }]
            
            return {
                'success': True,
                'document_id': document_id,
                'document_title': doc.get('title', 'Sin título'),
                'tabs': tabs,
                'total_tabs': len(tabs),
                'metadata': {
                    'revision_id': doc.get('revisionId'),
                    'document_id': document_id
                }
            }
            
        except HttpError as e:
            if e.resp.status == 404:
                raise Exception(f"Documento no encontrado: {document_id}")
            else:
                raise Exception(f"Error de Google Docs API: {str(e)}")
        except Exception as e:
            raise Exception(f"Error al obtener tabs del documento: {str(e)}")
    
    def _is_tab_header(self, text: str) -> bool:
        """Check if text looks like a tab/section header"""
        if not text or not text.strip():
            return False
        
        text = text.strip()
        
        # Check for common tab/section patterns
        tab_patterns = [
            # Numbered sections
            r'^\d+\.\s+',  # "1. Section"
            r'^\d+\)\s+',  # "1) Section"
            # Bullet points that might be tabs
            r'^[-•*]\s+',  # "- Section", "• Section", "* Section"
            # All caps (might be headers)
            r'^[A-Z\s]{3,}$',  # "SECTION TITLE"
            # Common tab keywords
            r'^(tab|pestaña|sección|section|parte|part)\s*\d*:?\s*',
            # Date patterns (common in meeting notes)
            r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
            # Time patterns
            r'^\d{1,2}:\d{2}',
        ]
        
        import re
        for pattern in tab_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        # Check if text is short and looks like a title
        if len(text) < 50 and any(keyword in text.lower() for keyword in 
                                 ['agenda', 'notes', 'meeting', 'reunión', 'summary', 'resumen']):
            return True
        
        return False
    
    def _extract_paragraph_text(self, paragraph: Dict) -> str:
        """Extract text content from a paragraph element"""
        text_parts = []
        
        for element in paragraph.get('elements', []):
            if 'textRun' in element:
                text_run = element['textRun']
                content = text_run.get('content', '')
                text_parts.append(content)
        
        return ''.join(text_parts)
    
    def _extract_table_content(self, table: Dict) -> List[List[str]]:
        """Extract content from a table element"""
        table_data = []
        
        for row in table.get('tableRows', []):
            row_data = []
            for cell in row.get('tableCells', []):
                cell_text = []
                for content in cell.get('content', []):
                    if 'paragraph' in content:
                        cell_text.append(self._extract_paragraph_text(content['paragraph']))
                row_data.append(' '.join(cell_text).strip())
            table_data.append(row_data)
        
        return table_data
    
    def _extract_all_content(self, content: List[Dict]) -> List[Dict]:
        """Extract all content when no tabs are found"""
        all_content = []
        
        for element in content:
            if 'paragraph' in element:
                text = self._extract_paragraph_text(element['paragraph'])
                if text.strip():
                    all_content.append({
                        'type': 'paragraph',
                        'text': text,
                        'position': element.get('startIndex', 0)
                    })
            elif 'table' in element:
                table_data = self._extract_table_content(element['table'])
                all_content.append({
                    'type': 'table',
                    'data': table_data,
                    'position': element.get('startIndex', 0)
                })
        
        return all_content

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
