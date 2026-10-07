# Base image ligera de Python 3.12
FROM python:3.12-slim

# Evita que Python escriba archivos .pyc y habilita salida sin buffer para logs en tiempo real en Cloud Run
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Instalar dependencias primero para aprovechar la caché de capas de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Exponer el puerto por defecto de Cloud Run (8080)
EXPOSE 8080

# Iniciar el servidor MCP en modo streamable-http
CMD ["python", "server.py", "--transport", "streamable-http"]
