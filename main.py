from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from dotenv import load_dotenv
from datetime import datetime

from services.docs_service import DocsService
from services.auth_service import AuthService

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Google Docs API",
    description="API para conectar con Google Docs y leer documentos",
    version="1.0.0"
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

# Dependency to check authentication
async def get_authenticated_service():
    if not auth_service.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="No autenticado. Ejecuta: gcloud auth application-default login"
        )
    return docs_service

@app.get("/")
async def root():
    return {
        "message": "Google Docs API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    return {
        "status": "OK",
        "message": "Google Docs API is running",
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

# Documents endpoints
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

@app.get("/api/docs/name/{document_name}")
async def get_document_by_name(
    document_name: str,
    format: str = "full",
    service: DocsService = Depends(get_authenticated_service)
):
    try:
        document = await service.get_document_by_name(document_name)
        
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
            detail=f"Error al obtener documento por nombre: {str(e)}"
        )

@app.get("/api/docs/search/{query}")
async def search_documents(
    query: str,
    page_size: int = 10,
    service: DocsService = Depends(get_authenticated_service)
):
    try:
        result = await service.search_documents(query, page_size)
        return {
            "success": True,
            "data": result,
            "message": f"Encontrados {result['total_count']} documentos que coinciden con '{query}'"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al buscar documentos: {str(e)}"
        )

@app.get("/api/docs/{document_id}/text")
async def get_document_text(
    document_id: str,
    service: DocsService = Depends(get_authenticated_service)
):
    try:
        document = await service.get_document_by_id(document_id)
        return {
            "success": True,
            "data": {
                "id": document["id"],
                "title": document["title"],
                "content": document["plain_text"]
            },
            "message": f"Contenido de texto plano para '{document['title']}'"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener texto del documento: {str(e)}"
        )

@app.get("/api/docs/{document_id}/elements")
async def get_document_elements(
    document_id: str,
    service: DocsService = Depends(get_authenticated_service)
):
    try:
        document = await service.get_document_by_id(document_id)
        return {
            "success": True,
            "data": {
                "id": document["id"],
                "title": document["title"],
                "elements": document["elements"],
                "element_count": len(document["elements"])
            },
            "message": f"Elementos estructurados para '{document['title']}'"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener elementos del documento: {str(e)}"
        )

@app.get("/api/docs/{document_id}/metadata")
async def get_document_metadata(
    document_id: str,
    service: DocsService = Depends(get_authenticated_service)
):
    try:
        document = await service.get_document_by_id(document_id)
        return {
            "success": True,
            "data": {
                "id": document["id"],
                "title": document["title"],
                "metadata": document["metadata"],
                "element_count": len(document["elements"])
            },
            "message": f"Metadatos para '{document['title']}'"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener metadatos del documento: {str(e)}"
        )

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
    
    print(f"🚀 Iniciando servidor en http://{host}:{port}")
    print(f"📖 Health check: http://{host}:{port}/health")
    print(f"📚 Docs API: http://{host}:{port}/api/docs")
    print(f"📖 Documentación: http://{host}:{port}/docs")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if not debug else "debug"
    )
