import base64
import logging
import secrets
import string
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


def generate_secure_password(length: int = 12) -> str:
    """
    Genera una contraseña aleatoria de al menos 12 caracteres.
    Incluye obligatoriamente mayúsculas, minúsculas, números y al menos un signo/carácter especial.
    """
    if length < 12:
        length = 12

    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    symbols = "!@#$%&*-_=+"

    # Garantizar al menos un carácter de cada conjunto requerido
    chosen = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]

    all_characters = uppercase + lowercase + digits + symbols
    chosen += [secrets.choice(all_characters) for _ in range(length - 4)]

    # Mezclar aleatoriamente las posiciones
    secrets.SystemRandom().shuffle(chosen)
    return "".join(chosen)


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
    new_password: Optional[str] = None,
    ad_user: Optional[str] = None,
    ad_psw: Optional[str] = None,
    ad_server: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Restablece la contraseña de un usuario en Active Directory.
    Endpoint: PUT /Active Directory/SA/resetUserADSA (puerto 6443)
    Si 'new_password' no se proporciona o está vacío, el servidor genera automáticamente
    una contraseña temporal segura de al menos 12 caracteres (con mayúsculas, minúsculas, números y un signo).
    La contraseña se codifica automáticamente en Base64 para el envío.
    """
    url = f"{AD_API_URL}/Active Directory/SA/resetUserADSA"
    headers = _get_headers(token)

    # Si no se pasó contraseña, generarla automáticamente en el servidor
    if new_password and new_password.strip():
        password_to_set = new_password.strip()
    else:
        password_to_set = generate_secure_password(12)

    encoded_password = encode_base64(password_to_set)

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

            result: Dict[str, Any] = {
                "http_status": response.status_code,
                "success": response.is_success,
                "data": data,
            }
            if response.is_success:
                result["temporary_password"] = password_to_set

            return result
    except httpx.TimeoutException as exc:
        logger.error(
            f"Timeout de espera ({HTTP_TIMEOUT}s) al contactar Active Directory: {type(exc).__name__}"
        )
        return {
            "http_status": 504,
            "success": False,
            "error": f"El servicio de Active Directory tardó más de {HTTP_TIMEOUT} segundos en responder (Timeout).",
        }
    except httpx.RequestError as exc:
        logger.error(f"Error de conexión en reset_user_ad ({type(exc).__name__}): {exc}")
        return {
            "http_status": 500,
            "success": False,
            "error": f"Error de conexión con el servicio de Active Directory: {type(exc).__name__} - {str(exc)}",
        }
