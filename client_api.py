import base64
import logging
from typing import Any, Dict, Optional
import httpx

from config import (
    AD_API_URL,
    AD_DEFAULT_PSW,
    AD_DEFAULT_SERVER,
    AD_DEFAULT_USER,
    BASE_API_URL,
    DEFAULT_BEARER_TOKEN,
    HTTP_TIMEOUT,
    VERIFY_SSL,
)

logger = logging.getLogger("mcp-provident")


def encode_base64(text: str) -> str:
    """Codifica una cadena de texto en Base64."""
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")


def _get_headers(token: Optional[str] = None) -> Dict[str, str]:
    """Genera las cabeceras HTTP necesarias incluyendo el token Bearer."""
    auth_token = token or DEFAULT_BEARER_TOKEN
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}",
    }


async def send_totp_request(
    numero_empleado: str, token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Envía un código TOTP vía SMS al número de empleado proporcionado.
    Endpoint: POST /RA/PROVIDENT/sendTOTPProvident
    """
    url = f"{BASE_API_URL}/RA/PROVIDENT/sendTOTPProvident"
    headers = _get_headers(token)
    payload = {"numeroEmpleado": str(numero_empleado).strip()}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=VERIFY_SSL) as client:
            response = await client.post(url, headers=headers, json=payload)
            try:
                data = response.json()
            except Exception:
                data = {"raw_response": response.text}

            return {
                "http_status": response.status_code,
                "success": response.is_success,
                "data": data,
            }
    except httpx.RequestError as exc:
        logger.error(f"Error de conexión en send_totp: {exc}")
        return {
            "http_status": 500,
            "success": False,
            "error": f"Error de conexión con el servicio: {str(exc)}",
        }


async def validate_totp_request(
    numero_empleado: str, otp: str, token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Valida el código TOTP / OTP recibido por el empleado.
    Endpoint: POST /RA/PROVIDENT/validateTOTPProvident
    """
    url = f"{BASE_API_URL}/RA/PROVIDENT/validateTOTPProvident"
    headers = _get_headers(token)
    payload = {
        "numeroEmpleado": str(numero_empleado).strip(),
        "otp": str(otp).strip(),
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=VERIFY_SSL) as client:
            response = await client.post(url, headers=headers, json=payload)
            try:
                data = response.json()
            except Exception:
                data = {"raw_response": response.text}

            return {
                "http_status": response.status_code,
                "success": response.is_success,
                "data": data,
            }
    except httpx.RequestError as exc:
        logger.error(f"Error de conexión en validate_totp: {exc}")
        return {
            "http_status": 500,
            "success": False,
            "error": f"Error de conexión con el servicio: {str(exc)}",
        }


async def reset_user_ad_request(
    sam_account_name: str,
    new_password: str,
    ad_user: Optional[str] = None,
    ad_psw: Optional[str] = None,
    ad_server: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Restablece la contraseña de un usuario en Active Directory.
    Endpoint: PUT /Active Directory/SA/resetUserADSA (puerto 6443)
    La contraseña 'new_password' se codifica automáticamente en Base64.
    """
    url = f"{AD_API_URL}/Active Directory/SA/resetUserADSA"
    headers = _get_headers(token)

    encoded_password = encode_base64(new_password)

    payload = {
        "ADUser": (ad_user or AD_DEFAULT_USER).strip(),
        "ADPsw": (ad_psw or AD_DEFAULT_PSW).strip(),
        "ADSAServer": (ad_server or AD_DEFAULT_SERVER).strip(),
        "SamAccountName": str(sam_account_name).strip(),
        "psw": encoded_password,
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=VERIFY_SSL) as client:
            response = await client.put(url, headers=headers, json=payload)
            try:
                data = response.json()
            except Exception:
                data = {"raw_response": response.text}

            return {
                "http_status": response.status_code,
                "success": response.is_success,
                "data": data,
            }
    except httpx.RequestError as exc:
        logger.error(f"Error de conexión en reset_user_ad: {exc}")
        return {
            "http_status": 500,
            "success": False,
            "error": f"Error de conexión con el servicio de Active Directory: {str(exc)}",
        }
