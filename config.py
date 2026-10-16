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
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "120.0"))
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() in ("true", "1", "yes")

# Configuración del servidor MCP HTTP (Copilot Studio)
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("PORT", os.getenv("MCP_PORT", "8000")))
MCP_PATH = os.getenv("MCP_PATH", "/mcp")
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "streamable-http")

# Clave de autenticación para clientes MCP entrantes (Copilot Studio)
MCP_API_KEY = os.getenv("MCP_API_KEY", "")

# Configuración del servicio ChatBridge SMS
CHATBRIDGE_API_KEY = os.getenv("CHATBRIDGE_API_KEY", "")
CHATBRIDGE_SMS_URL = os.getenv(
    "CHATBRIDGE_SMS_URL", "https://connect.chatbridge.mx/v1/sms/messages"
)
CHATBRIDGE_SMS_MASK = os.getenv(
    "CHATBRIDGE_SMS_MASK", "6aac0ecdb99ccfcfa56bbc2d"
)

# Configuración ServiceNow (Creación y Documentación de Tickets)
SNOW_API_URL = os.getenv(
    "PROVIDENT_SNOW_URL", "https://api.supporttsmx.com.mx:8443"
)
SNOW_DEFAULT_REQUESTOR = os.getenv(
    "SNOW_DEFAULT_REQUESTOR", "0e966fba838ff6d063a134326daad374"
)
SNOW_BUSINESS_SERVICE = os.getenv(
    "SNOW_BUSINESS_SERVICE", "0f873c450f5802003e6c85ece1050e4f"
)
SNOW_ASSIGNMENT_GROUP = os.getenv(
    "SNOW_ASSIGNMENT_GROUP", "64bb9f64378fe200d8a8579543990eee"
)
SNOW_MANAGER_FALLBACK = os.getenv(
    "SNOW_MANAGER_FALLBACK", "d8423b640fd402003e6c85ece1050e1e"
)
SNOW_PRIORITY = os.getenv("SNOW_PRIORITY", "4")
SNOW_CATEGORY = os.getenv("SNOW_CATEGORY", "Active Directory")

