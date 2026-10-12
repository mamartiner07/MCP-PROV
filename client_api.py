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
    CHATBRIDGE_API_KEY,
    CHATBRIDGE_SMS_MASK,
    CHATBRIDGE_SMS_URL,
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


def sanitize_sam_account_name(account_name: Optional[str]) -> str:
    """
    Limpia y extrae el SamAccountName eliminando prefijos de dominio o barras
    (ej. 'PROVIDENTMX/ramiroha' o 'PROVIDENTMX\\ramiroha' -> 'ramiroha').
    Retorna una cadena vacía si no es un valor válido.
    """
    if not account_name:
        return ""
    clean = str(account_name).strip()
    if "/" in clean:
        clean = clean.split("/")[-1].strip()
    if "\\" in clean:
        clean = clean.split("\\")[-1].strip()
    return clean


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

            is_successful = response.is_success
            if isinstance(data, dict):
                status_str = str(data.get("status", "")).strip().lower()
                return_code = data.get("returnCode")
                if status_str == "success" or return_code in (200, 302):
                    is_successful = True

            return {
                "http_status": response.status_code,
                "success": is_successful,
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

            # En Provident, HTTP 302 con returnCode 302 significa "registro encontrado" (éxito)
            is_successful = response.is_success
            if isinstance(data, dict):
                status_str = str(data.get("status", "")).strip().lower()
                return_code = data.get("returnCode")
                if status_str == "success" or return_code in (200, 302):
                    is_successful = True

            ad_account = None
            phone = None
            if is_successful and isinstance(data, dict):
                result_obj = data.get("result")
                ad_raw = ""
                if isinstance(result_obj, dict):
                    ad_raw = result_obj.get("AD") or result_obj.get("ad") or ""
                    phone_raw = result_obj.get("phone") or result_obj.get("telefono") or ""
                    if phone_raw:
                        phone = str(phone_raw).strip()
                elif "AD" in data:
                    ad_raw = data.get("AD") or ""
                if not phone and "phone" in data:
                    phone = str(data.get("phone")).strip()

                clean_ad = sanitize_sam_account_name(ad_raw)
                if clean_ad:
                    ad_account = clean_ad

            return {
                "http_status": response.status_code,
                "success": is_successful,
                "data": data,
                "sam_account_name": ad_account,
                "phone": phone,
            }
    except httpx.RequestError as exc:
        logger.error(f"Error de conexión en validate_totp: {exc}")
        return {
            "http_status": 500,
            "success": False,
            "error": f"Error de conexión con el servicio: {str(exc)}",
        }


async def send_sms_chatbridge_request(
    to: str,
    text: str,
    mask: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Envía un mensaje SMS a través del servicio ChatBridge.
    Endpoint: POST https://connect.chatbridge.mx/v1/sms/messages
    Headers:
      x-api-key: <API_KEY>
      Content-Type: application/json
    Payload:
      {"mask": "...", "to": "...", "text": "..."}
    """
    url = CHATBRIDGE_SMS_URL
    key = (api_key or CHATBRIDGE_API_KEY).strip()
    headers = {
        "Content-Type": "application/json",
        "x-api-key": key,
    }
    payload = {
        "mask": (mask or CHATBRIDGE_SMS_MASK).strip(),
        "to": str(to).strip(),
        "text": str(text).strip(),
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
        logger.error(f"Error de conexión en send_sms_chatbridge: {exc}")
        return {
            "http_status": 500,
            "success": False,
            "error": f"Error de conexión con el servicio ChatBridge SMS: {str(exc)}",
        }


async def reset_user_ad_request(
    sam_account_name: str,
    phone: Optional[str] = None,
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
    Si se proporciona 'phone', se envía de inmediato un SMS con la contraseña temporal vía ChatBridge.
    """
    url = f"{AD_API_URL}/Active Directory/SA/resetUserADSA"
    headers = _get_headers(token)

    # Si no se pasó contraseña, generarla automáticamente en el servidor
    if new_password and new_password.strip():
        password_to_set = new_password.strip()
    else:
        password_to_set = generate_secure_password(12)

    encoded_password = encode_base64(password_to_set)

    # Sanitizar SamAccountName eliminando prefijos de dominio (ej. PROVIDENTMX/usuario)
    cleaned_sam = sanitize_sam_account_name(sam_account_name)

    payload = {
        "ADUser": (ad_user or AD_DEFAULT_USER).strip(),
        "ADPsw": (ad_psw or AD_DEFAULT_PSW).strip(),
        "ADSAServer": (ad_server or AD_DEFAULT_SERVER).strip(),
        "SamAccountName": cleaned_sam if cleaned_sam else str(sam_account_name).strip(),
        "psw": encoded_password,
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=VERIFY_SSL) as client:
            response = await client.put(url, headers=headers, json=payload)
            try:
                data = response.json()
            except Exception:
                data = {"raw_response": response.text}

            is_successful = response.is_success
            if isinstance(data, dict):
                status_str = str(data.get("status", "")).strip().lower()
                return_code = data.get("returnCode")
                if status_str == "success" or return_code in (200, 302):
                    is_successful = True

            result: Dict[str, Any] = {
                "http_status": response.status_code,
                "success": is_successful,
                "data": data,
            }
            if is_successful:
                result["temporary_password"] = password_to_set

                # Si se proporcionó número telefónico, enviar la contraseña temporal por SMS vía ChatBridge
                if phone and str(phone).strip():
                    clean_phone = str(phone).strip()
                    sms_message = (
                        f"Tu contrasena temporal de Active Directory es: {password_to_set}. "
                        "Por seguridad, el sistema te solicitara cambiarla en tu primer acceso."
                    )
                    sms_response = await send_sms_chatbridge_request(
                        to=clean_phone,
                        text=sms_message,
                    )
                    result["sms_notification"] = {
                        "sent": sms_response.get("success", False),
                        "to": clean_phone,
                        "http_status": sms_response.get("http_status"),
                        "details": sms_response.get("data") or sms_response.get("error"),
                    }

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
