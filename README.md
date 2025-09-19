# Google Docs API - Python

Una API de Python que se conecta con Google Docs y permite leer documentos de forma programática usando FastAPI.

## Características

- 🐍 **Python + FastAPI** - Framework moderno y rápido
- 🔐 **Autenticación con gcloud CLI** - Simple y directo
- 📖 **Lectura de documentos** de Google Docs
- 🔍 **Búsqueda de documentos** por contenido
- 📝 **Extracción de texto** plano y formateado
- 🗂️ **Listado de documentos** disponibles
- 📊 **Metadatos** y elementos estructurados
- 🚀 **Documentación automática** con Swagger UI

## Instalación

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar autenticación con Google Cloud

```bash
# Autenticarse con Google Cloud
gcloud auth login

# Configurar el proyecto
gcloud config set project docdash-ai-dev

# Configurar Application Default Credentials
gcloud auth application-default login
```

### 3. Habilitar APIs necesarias

```bash
# Habilitar Google Docs API
gcloud services enable docs.googleapis.com

# Habilitar Google Drive API
gcloud services enable drive.googleapis.com
```

## Uso

### Iniciar el servidor

```bash
# Desarrollo
python main.py

# O con uvicorn directamente
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

El servidor estará disponible en:
- **API**: http://localhost:8000
- **Documentación**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Endpoints de la API

### Autenticación

- `GET /api/auth/status` - Verificar estado de autenticación
- `POST /api/auth/init` - Inicializar autenticación

### Documentos

- `GET /api/docs` - Listar todos los documentos
- `GET /api/docs/{document_id}` - Obtener documento por ID
- `GET /api/docs/name/{document_name}` - Obtener documento por nombre
- `GET /api/docs/search/{query}` - Buscar documentos por contenido
- `GET /api/docs/{document_id}/text` - Obtener texto plano del documento
- `GET /api/docs/{document_id}/elements` - Obtener elementos estructurados
- `GET /api/docs/{document_id}/metadata` - Obtener metadatos del documento

### Parámetros de consulta

- `page_size` - Número de documentos por página (default: 10)
- `page_token` - Token para paginación
- `format` - Formato de respuesta: `full`, `text`, `metadata`

## Ejemplos de uso

### 1. Verificar autenticación

```bash
curl http://localhost:8000/api/auth/status
```

### 2. Listar documentos

```bash
curl http://localhost:8000/api/docs
```

### 3. Obtener documento por ID

```bash
curl http://localhost:8000/api/docs/DOCUMENT_ID
```

### 4. Obtener solo texto plano

```bash
curl http://localhost:8000/api/docs/DOCUMENT_ID/text
```

### 5. Buscar documentos

```bash
curl http://localhost:8000/api/docs/search/TERMINO_DE_BUSQUEDA
```

## Estructura del proyecto

```
├── services/
│   ├── __init__.py
│   ├── auth_service.py      # Servicio de autenticación
│   └── docs_service.py      # Servicio para Google Docs
├── main.py                  # Aplicación principal FastAPI
├── requirements.txt         # Dependencias Python
├── .env                     # Variables de entorno
└── README.md               # Este archivo
```

## Dependencias principales

- **FastAPI** - Framework web moderno y rápido
- **google-api-python-client** - SDK oficial de Google APIs
- **google-auth** - Autenticación con Google
- **uvicorn** - Servidor ASGI
- **python-dotenv** - Carga de variables de entorno

## Respuestas de la API

### Respuesta exitosa:
```json
{
  "success": true,
  "data": { ... },
  "message": "Mensaje descriptivo"
}
```

### Respuesta de error:
```json
{
  "success": false,
  "error": "Descripción del error",
  "status_code": 500
}
```

## Desarrollo

### Variables de entorno

```env
PORT=8000
HOST=0.0.0.0
DEBUG=True
GOOGLE_CLOUD_PROJECT=docdash-ai-dev
```

### Comandos útiles

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar en modo desarrollo
python main.py

# Ejecutar con uvicorn
uvicorn main:app --reload

# Ver documentación interactiva
# Abrir http://localhost:8000/docs en el navegador
```

## Solución de problemas

### Error de autenticación

Si recibes errores de autenticación:

```bash
# Re-autenticarse
gcloud auth application-default login

# Verificar proyecto
gcloud config get-value project

# Verificar APIs habilitadas
gcloud services list --enabled
```

### Error de permisos

Asegúrate de que las APIs estén habilitadas:

```bash
gcloud services enable docs.googleapis.com
gcloud services enable drive.googleapis.com
```

## Licencia

MIT

## Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request