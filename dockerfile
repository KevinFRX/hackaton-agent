# Usa una imagen base de Python oficial y ligera
FROM python:3.12-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia los archivos de requisitos e instálalos
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia tu script principal y los archivos de configuración
COPY .env .
COPY main.py .

# El comando a ejecutar para iniciar el servidor web con tu agente
# El comando usa `uvicorn`, un servidor web ligero y rápido
# para aplicaciones asíncronas.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]