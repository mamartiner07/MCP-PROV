import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Token de Autorización Bearer por defecto (cargado desde .env)
DEFAULT_BEARER_TOKEN = os.getenv("PROVIDENT_BEARER_TOKEN", "")

# URLs base de los servicios
BASE_API_URL = os.getenv("PROVIDENT_BASE_URL", "https://api.supporttsmx.com.mx")
AD_API_URL = os.getenv("PROVIDENT_AD_URL", "https://api.supporttsmx.com.mx:6443")

# Credenciales y servidor de Active Directory por defecto (cargados desde .env)
AD_DEFAULT_USER = os.getenv("AD_DEFAULT_USER", "chatbot.connect")
# ADPsw se espera pre-codificado en Base64 o según el endpoint
AD_DEFAULT_PSW = os.getenv("AD_DEFAULT_PSW", "")
AD_DEFAULT_SERVER = os.getenv("AD_DEFAULT_SERVER", "ADProviTest01.ProvidentMX.Test")

# Configuración de red y timeouts
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30.0"))
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() in ("true", "1", "yes")

# Configuración del servidor MCP HTTP (Copilot Studio)
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("PORT", os.getenv("MCP_PORT", "8000")))
MCP_PATH = os.getenv("MCP_PATH", "/mcp")
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "streamable-http")
