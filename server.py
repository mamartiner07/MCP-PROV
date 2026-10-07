import argparse
import json
import logging
import sys
from typing import Any, Dict, Optional

import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import MCP_API_KEY, MCP_HOST, MCP_PATH, MCP_PORT, MCP_TRANSPORT
from client_api import (
    reset_user_ad_request,
    send_totp_request,
    validate_totp_request,
)
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

# Configuración de logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mcp-provident")

# Inicialización del servidor MCP
mcp_server = MCPServer("Provident MCP Server")


@mcp_server.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Ruta de verificación de estado del servicio."""
    return JSONResponse(
        {
            "status": "ok",
            "service": "mcp-provident",
            "version": "1.0.0",
        }
    )


@mcp_server.custom_route("/", methods=["GET"])
async def root_info(request: Request) -> JSONResponse:
    """Ruta informativa raíz."""
    return JSONResponse(
        {
            "service": "Provident MCP Server",
            "status": "running",
            "mcp_endpoint": MCP_PATH,
            "health_check": "/health",
        }
    )


@mcp_server.tool(
    name="send_totp_provident",
    description="Envía un código de seguridad TOTP / SMS al teléfono registrado del empleado de Provident.",
)
async def send_totp_provident(
    numero_empleado: str,
    token: Optional[str] = None,
) -> str:
    """
    Envía un código OTP/TOTP a un empleado de Provident.

    Args:
        numero_empleado: Número de identificación del empleado.
        token: (Opcional) Token Bearer JWT personalizado para autenticación.
    """
    result = await send_totp_request(numero_empleado=numero_empleado, token=token)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp_server.tool(
    name="validate_totp_provident",
    description="Valida el código de verificación TOTP / OTP ingresado por el empleado de Provident.",
)
async def validate_totp_provident(
    numero_empleado: str,
    otp: str,
    token: Optional[str] = None,
) -> str:
    """
    Valida el código OTP de un empleado de Provident.

    Args:
        numero_empleado: Número de identificación del empleado.
        otp: Código TOTP de 6 dígitos recibido por el empleado.
        token: (Opcional) Token Bearer JWT personalizado para autenticación.
    """
    result = await validate_totp_request(
        numero_empleado=numero_empleado, otp=otp, token=token
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp_server.tool(
    name="reset_user_ad_sa",
    description="Restablece la contraseña de una cuenta en Active Directory (AD) de Provident. El servidor genera automáticamente una contraseña temporal segura de al menos 12 caracteres (con mayúsculas, minúsculas, números y un signo) y la retorna en 'temporary_password' para que el asistente se la entregue al usuario.",
)
async def reset_user_ad_sa(
    sam_account_name: str,
    new_password: Optional[str] = None,
    ad_user: Optional[str] = None,
    ad_server: Optional[str] = None,
    token: Optional[str] = None,
) -> str:
    """
    Restablece la contraseña de un usuario en Active Directory.

    Args:
        sam_account_name: Nombre de usuario o cuenta SamAccountName.
        new_password: (Opcional) Contraseña en texto plano. Si se omite, el servidor genera una automáticamente.
        ad_user: (Opcional) Usuario administrador del AD (por defecto configurado en .env).
        ad_server: (Opcional) Servidor AD destino (por defecto configurado en .env).
        token: (Opcional) Token Bearer JWT personalizado para autenticación.
    """
    result = await reset_user_ad_request(
        sam_account_name=sam_account_name,
        new_password=new_password,
        ad_user=ad_user,
        ad_server=ad_server,
        token=token,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware de autenticación por API Key para solicitudes HTTP entrantes (Copilot Studio).
    Valida el header 'X-API-Key' o 'Authorization: Bearer <key>'.
    Permite acceso libre a endpoints públicos como /health, / y solicitudes OPTIONS (CORS preflight).
    """

    def __init__(self, app, api_key: Optional[str] = None):
        super().__init__(app)
        self.api_key = (api_key if api_key is not None else MCP_API_KEY).strip()

    async def dispatch(self, request: Request, call_next):
        # Permitir preflight CORS y rutas públicas de verificación
        if request.method == "OPTIONS" or request.url.path in ("/health", "/"):
            return await call_next(request)

        # Si hay una API Key configurada, validarla
        if self.api_key:
            header_key = request.headers.get("x-api-key")
            auth_header = request.headers.get("authorization")

            is_valid = False
            if header_key and header_key.strip() == self.api_key:
                is_valid = True
            elif auth_header:
                token = auth_header.strip()
                if token.lower().startswith("bearer "):
                    token = token[7:].strip()
                if token == self.api_key:
                    is_valid = True

            if not is_valid:
                client_ip = request.client.host if request.client else "desconocido"
                logger.warning(
                    f"Petición no autorizada rechazada en {request.url.path} desde {client_ip}"
                )
                return JSONResponse(
                    {
                        "error": "Unauthorized",
                        "message": "API Key inválida o ausente. Configure el header 'X-API-Key' o 'Authorization: Bearer <token>' en Copilot Studio.",
                    },
                    status_code=401,
                )

        return await call_next(request)


def create_streamable_http_app(
    path: str = MCP_PATH,
    host: str = MCP_HOST,
    api_key: Optional[str] = None,
):
    """Crea y configura la aplicación Starlette para Streamable HTTP con seguridad y autenticación."""
    security_settings = TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    )
    app = mcp_server.streamable_http_app(
        streamable_http_path=path,
        transport_security=security_settings,
        host=host,
    )
    app.add_middleware(APIKeyAuthMiddleware, api_key=api_key)
    return app


def main():
    # Desempaquetar argumentos si vinieron agrupados en una sola cadena (típico en interfaces web como MCP Inspector)
    if len(sys.argv) > 1 and any(" " in arg for arg in sys.argv[1:]):
        import shlex
        expanded_argv = [sys.argv[0]]
        for arg in sys.argv[1:]:
            expanded_argv.extend(shlex.split(arg))
        sys.argv = expanded_argv

    parser = argparse.ArgumentParser(
        description="Servidor MCP para servicios Provident (Compatible con Copilot Studio)"
    )
    parser.add_argument(
        "--transport",
        choices=["streamable-http", "stdio", "sse"],
        default=MCP_TRANSPORT,
        help=f"Tipo de transporte MCP. Use 'streamable-http' para Copilot Studio o 'stdio' para clientes locales (por defecto: {MCP_TRANSPORT}).",
    )
    parser.add_argument(
        "--host",
        default=MCP_HOST,
        help=f"Host donde escuchar peticiones HTTP (por defecto: {MCP_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=MCP_PORT,
        help=f"Puerto donde escuchar peticiones HTTP (por defecto: {MCP_PORT})",
    )
    parser.add_argument(
        "--path",
        default=MCP_PATH,
        help=f"Ruta del endpoint MCP Streamable HTTP (por defecto: {MCP_PATH})",
    )

    args = parser.parse_args()

    logger.info(f"Iniciando Servidor MCP Provident con transporte: {args.transport}")

    if args.transport == "stdio":
        mcp_server.run(transport="stdio")
    elif args.transport == "sse":
        mcp_server.run(transport="sse", host=args.host, port=args.port)
    else:
        # streamable-http (Requerido para Microsoft Copilot Studio)
        app = create_streamable_http_app(path=args.path, host=args.host)

        if MCP_API_KEY:
            logger.info("Autenticación por API Key activada (Header requerido: X-API-Key o Authorization)")
        else:
            logger.warning("ADVERTENCIA: MCP_API_KEY no configurada. El servidor responderá sin autenticación.")

        logger.info(f"Servidor listo para Copilot Studio en http://{args.host}:{args.port}{args.path}")
        logger.info(f"Healthcheck disponible en http://{args.host}:{args.port}/health")

        uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
