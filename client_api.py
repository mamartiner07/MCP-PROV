import asyncio
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
    SNOW_API_URL,
    SNOW_ASSIGNMENT_GROUP,
    SNOW_BUSINESS_SERVICE,
    SNOW_CATEGORY,
    SNOW_DEFAULT_REQUESTOR,
    SNOW_MANAGER_FALLBACK,
    SNOW_PRIORITY,
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
            email = None
            name = None
            if is_successful and isinstance(data, dict):
                result_obj = data.get("result")
                ad_raw = ""
                if isinstance(result_obj, dict):
                    ad_raw = result_obj.get("AD") or result_obj.get("ad") or ""
                    phone_raw = result_obj.get("phone") or result_obj.get("telefono") or ""
                    if phone_raw:
                        phone = str(phone_raw).strip()

                    email_cand = str(result_obj.get("email") or result_obj.get("correo") or "").strip()
                    name_cand = str(result_obj.get("name") or result_obj.get("nombre") or "").strip()
                    if "@" in email_cand:
                        email = email_cand
                        name = name_cand if name_cand else None
                    elif "@" in name_cand:
                        email = name_cand
                        name = email_cand if email_cand else None
                    else:
                        email = email_cand if email_cand else None
                        name = name_cand if name_cand else None
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
                "email": email,
                "name": name,
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
    una contraseña segura de al menos 12 caracteres (con mayúsculas, minúsculas, números y un signo).
    La contraseña se codifica automáticamente en Base64 para el envío.
    Si se proporciona 'phone', se envía de inmediato un SMS con la contraseña vía ChatBridge.
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

                # Si se proporcionó número telefónico, enviar la contraseña por SMS vía ChatBridge
                if phone and str(phone).strip():
                    clean_phone = str(phone).strip()
                    sms_message = f"Tu contrasena de Active Directory es: {password_to_set}."
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


async def unlock_user_ad_request(
    sam_account_name: str,
    ad_server: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Desbloquea la cuenta de un usuario en Active Directory (sin modificar su contraseña).
    Endpoint: PUT /Active Directory/SA/unlockUserADSA (puerto 6443)
    Payload:
      {"ADSAServer": "...", "SamAccountName": "..."}
    """
    url = f"{AD_API_URL}/Active Directory/SA/unlockUserADSA"
    headers = _get_headers(token)

    cleaned_sam = sanitize_sam_account_name(sam_account_name)
    payload = {
        "ADSAServer": (ad_server or AD_DEFAULT_SERVER).strip(),
        "SamAccountName": cleaned_sam if cleaned_sam else str(sam_account_name).strip(),
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

            return {
                "http_status": response.status_code,
                "success": is_successful,
                "data": data,
                "sam_account_name": cleaned_sam or sam_account_name,
            }
    except httpx.TimeoutException as exc:
        logger.error(
            f"Timeout de espera ({HTTP_TIMEOUT}s) al contactar Active Directory (unlockUserADSA): {type(exc).__name__}"
        )
        return {
            "http_status": 504,
            "success": False,
            "error": f"El servicio de Active Directory tardó más de {HTTP_TIMEOUT} segundos en responder (Timeout).",
        }
    except httpx.RequestError as exc:
        logger.error(f"Error de conexión en unlock_user_ad ({type(exc).__name__}): {exc}")
        return {
            "http_status": 500,
            "success": False,
            "error": f"Error de conexión con el servicio de Active Directory: {type(exc).__name__} - {str(exc)}",
        }


# ==============================================================================
# Endpoints ServiceNow (Fase de Documentación y Cierre de Tickets)
# ==============================================================================


async def get_snow_user(
    email: str, token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Busca un usuario en ServiceNow por su dirección de correo electrónico.
    Endpoint: GET /PROVIDENT/SNOW/Test/User/getUser?email={email}
    """
    clean_email = str(email).strip()
    url = f"{SNOW_API_URL}/PROVIDENT/SNOW/Test/User/getUser"
    headers = _get_headers(token)
    params = {"email": clean_email}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=VERIFY_SSL) as client:
            response = await client.get(url, headers=headers, params=params)
            try:
                data = response.json()
            except Exception:
                data = {"raw_response": response.text}

            is_successful = response.is_success
            user_sys_id = None
            manager_sys_id = None
            name = None
            phone = None

            if isinstance(data, dict):
                status_str = str(data.get("status", "")).strip().lower()
                return_code = data.get("returnCode")
                if status_str == "success" or return_code in (200, 302):
                    is_successful = True

                result_list = data.get("result")
                if isinstance(result_list, list) and len(result_list) > 0:
                    user_record = result_list[0]
                    user_sys_id = user_record.get("sys_id")
                    name = user_record.get("name")
                    phone = (
                        user_record.get("phone")
                        or user_record.get("mobile_phone")
                        or None
                    )
                    manager_data = user_record.get("manager")
                    if isinstance(manager_data, dict):
                        manager_sys_id = manager_data.get("value")
                    elif isinstance(manager_data, str) and manager_data.strip():
                        manager_sys_id = manager_data.strip()

            if not manager_sys_id:
                manager_sys_id = SNOW_MANAGER_FALLBACK

            return {
                "http_status": response.status_code,
                "success": is_successful and bool(user_sys_id),
                "user_sys_id": user_sys_id,
                "manager_sys_id": manager_sys_id,
                "name": name,
                "phone": phone,
                "email": clean_email,
                "data": data,
            }
    except httpx.RequestError as exc:
        logger.error(f"Error de conexión en get_snow_user: {exc}")
        return {
            "http_status": 500,
            "success": False,
            "error": f"Error de conexión con ServiceNow (getUser): {str(exc)}",
        }


async def create_snow_generic_req(
    user_sys_id: str,
    manager_sys_id: Optional[str] = None,
    short_description: str = "EVA | INICIO DE SESION | RESET DE CONTRASEÑA",
    description: str = "Usuario solicita reinicio de clave de red",
    requestor_sys_id: Optional[str] = None,
    business_service: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Crea un requerimiento genérico (Generic Request / REQ) en ServiceNow.
    Endpoint: POST /PROVIDENT/SNOW/Test/Request/createGenericReq
    """
    url = f"{SNOW_API_URL}/PROVIDENT/SNOW/Test/Request/createGenericReq"
    headers = _get_headers(token)
    # La pasarela de Provident utiliza <salto> para representar los saltos de línea.
    # Se reemplazan saltos de línea reales (\r\n, \n, \r) y '\\n' por <salto>.
    raw_desc = str(description or "")
    sanitized_desc = (
        raw_desc.replace("\r\n", "<salto>")
        .replace("\n", "<salto>")
        .replace("\r", "<salto>")
        .replace("\\n", "<salto>")
    )

    payload = {
        "generic_short_description": short_description,
        "vs_requestor": (requestor_sys_id or SNOW_DEFAULT_REQUESTOR).strip(),
        "generic_description": sanitized_desc,
        "vs_requested_for": True,
        "u_business_service": (business_service or SNOW_BUSINESS_SERVICE).strip(),
        "vs_requested_for_user": str(user_sys_id).strip(),
        "vs_requestor_manager": (manager_sys_id or SNOW_MANAGER_FALLBACK).strip(),
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=VERIFY_SSL) as client:
            response = await client.post(url, headers=headers, json=payload)
            try:
                data = response.json()
            except Exception:
                data = {"raw_response": response.text}

            is_successful = response.is_success
            request_sys_id = None
            request_number = None

            if isinstance(data, dict):
                status_str = str(data.get("status", "")).strip().lower()
                return_code = data.get("returnCode")
                if status_str == "success" or return_code in (200, 201, 302):
                    is_successful = True

                result_obj = data.get("result")
                if isinstance(result_obj, dict):
                    request_sys_id = result_obj.get("sys_id") or result_obj.get("request_id")
                    request_number = result_obj.get("number") or result_obj.get("request_number")

            return {
                "http_status": response.status_code,
                "success": is_successful and bool(request_sys_id),
                "request_sys_id": request_sys_id,
                "request_number": request_number,
                "data": data,
            }
    except httpx.RequestError as exc:
        logger.error(f"Error de conexión en create_snow_generic_req: {exc}")
        return {
            "http_status": 500,
            "success": False,
            "error": f"Error de conexión con ServiceNow (createGenericReq): {str(exc)}",
        }


async def get_snow_task_from_req(
    request_sys_id: str,
    max_retries: int = 4,
    delay_seconds: float = 2.5,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Obtiene el número de la tarea técnica (sc_task) vinculada a un requerimiento (REQ).
    Incluye reintentos con pausa para aguardar la instanciación asíncrona de la tarea en ServiceNow.
    Endpoint: GET /PROVIDENT/SNOW/Test/Task/getTaskKeyListQuery?query=request_item.request%3D{req_sys_id}...
    """
    url = f"{SNOW_API_URL}/PROVIDENT/SNOW/Test/Task/getTaskKeyListQuery"
    headers = _get_headers(token)
    query_param = f"request_item.request={request_sys_id.strip()}&sysparm_fields=sys_id,number,request_item.number"
    params = {"query": query_param}

    last_data: Any = None
    last_status = 500

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=VERIFY_SSL) as client:
            for attempt in range(max_retries):
                if attempt > 0:
                    logger.info(
                        f"Reintentando consulta de tarea técnica para REQ {request_sys_id} (intento {attempt + 1}/{max_retries})..."
                    )
                    await asyncio.sleep(delay_seconds)

                response = await client.get(url, headers=headers, params=params)
                last_status = response.status_code
                try:
                    last_data = response.json()
                except Exception:
                    last_data = {"raw_response": response.text}

                if response.is_success and isinstance(last_data, dict):
                    result_obj = last_data.get("result")
                    if isinstance(result_obj, dict):
                        tasks = result_obj.get("task")
                        if isinstance(tasks, list) and len(tasks) > 0:
                            task_number = tasks[0].get("number")
                            if task_number:
                                return {
                                    "http_status": response.status_code,
                                    "success": True,
                                    "task_number": task_number,
                                    "data": last_data,
                                }

            return {
                "http_status": last_status,
                "success": False,
                "error": f"No se encontró ninguna tarea técnica (sc_task) generada para el request {request_sys_id} tras {max_retries} intentos.",
                "data": last_data,
            }
    except httpx.RequestError as exc:
        logger.error(f"Error de conexión en get_snow_task_from_req: {exc}")
        return {
            "http_status": 500,
            "success": False,
            "error": f"Error de conexión con ServiceNow (getTaskKeyListQuery): {str(exc)}",
        }


async def get_snow_task_details(
    task_number: str, token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Obtiene el detalle y sys_id de una tarea técnica a partir de su número (ej. TASK0487110).
    Endpoint: GET /PROVIDENT/SNOW/Test/Task/getTask?number={task_number}
    """
    url = f"{SNOW_API_URL}/PROVIDENT/SNOW/Test/Task/getTask"
    headers = _get_headers(token)
    params = {"number": str(task_number).strip()}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=VERIFY_SSL) as client:
            response = await client.get(url, headers=headers, params=params)
            try:
                data = response.json()
            except Exception:
                data = {"raw_response": response.text}

            is_successful = response.is_success
            task_sys_id = None

            if isinstance(data, dict):
                status_str = str(data.get("status", "")).strip().lower()
                return_code = data.get("returnCode")
                if status_str == "success" or return_code in (200, 302):
                    is_successful = True

                result_list = data.get("result")
                if isinstance(result_list, list) and len(result_list) > 0:
                    task_sys_id = result_list[0].get("sys_id")
                elif isinstance(result_list, dict):
                    task_sys_id = result_list.get("sys_id")

            return {
                "http_status": response.status_code,
                "success": is_successful and bool(task_sys_id),
                "task_sys_id": task_sys_id,
                "task_number": task_number,
                "data": data,
            }
    except httpx.RequestError as exc:
        logger.error(f"Error de conexión en get_snow_task_details: {exc}")
        return {
            "http_status": 500,
            "success": False,
            "error": f"Error de conexión con ServiceNow (getTask): {str(exc)}",
        }


async def update_snow_task(
    task_sys_id: str,
    assignment_group: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Asigna grupo resolutor, prioridad, categoría y subcategoría en la tarea técnica.
    Endpoint: PUT /PROVIDENT/SNOW/Test/Task/updateTask
    """
    url = f"{SNOW_API_URL}/PROVIDENT/SNOW/Test/Task/updateTask"
    headers = _get_headers(token)
    payload = {
        "sys_id": str(task_sys_id).strip(),
        "assignment_group": (assignment_group or SNOW_ASSIGNMENT_GROUP).strip(),
        "priority": str(priority or SNOW_PRIORITY).strip(),
        "u_category": (category or SNOW_CATEGORY).strip(),
        "u_subcategory": (subcategory or "Reset Password").strip(),
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

            return {
                "http_status": response.status_code,
                "success": is_successful,
                "data": data,
            }
    except httpx.RequestError as exc:
        logger.error(f"Error de conexión en update_snow_task: {exc}")
        return {
            "http_status": 500,
            "success": False,
            "error": f"Error de conexión con ServiceNow (updateTask): {str(exc)}",
        }


async def close_snow_task(
    task_sys_id: str,
    comments: Optional[str] = None,
    work_notes: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cierra la tarea técnica en estado Closed Complete con comentarios visibles y notas técnicas.
    Endpoint: PUT /PROVIDENT/SNOW/Test/Task/putTaskInClosedComplete
    """
    url = f"{SNOW_API_URL}/PROVIDENT/SNOW/Test/Task/putTaskInClosedComplete"
    headers = _get_headers(token)
    raw_comments = str(
        comments or "Hola, tu solicitud ha sido atendida y completada con éxito"
    ).strip()
    raw_work_notes = str(
        work_notes or "Ticket completado automáticamente por EVA"
    ).strip()

    sanitized_comments = (
        raw_comments.replace("\r\n", "<salto>")
        .replace("\n", "<salto>")
        .replace("\r", "<salto>")
        .replace("\\n", "<salto>")
    )
    sanitized_work_notes = (
        raw_work_notes.replace("\r\n", "<salto>")
        .replace("\n", "<salto>")
        .replace("\r", "<salto>")
        .replace("\\n", "<salto>")
    )

    payload = {
        "sys_id": str(task_sys_id).strip(),
        "comments": sanitized_comments,
        "work_notes": sanitized_work_notes,
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=VERIFY_SSL) as client:
            response = await client.put(url, headers=headers, json=payload)
            try:
                data = response.json()
            except Exception:
                data = {"raw_response": response.text}

            is_successful = response.is_success
            state = None
            task_number = None

            if isinstance(data, dict):
                status_str = str(data.get("status", "")).strip().lower()
                return_code = data.get("returnCode")
                if status_str == "success" or return_code in (200, 302):
                    is_successful = True

                result_obj = data.get("result")
                if isinstance(result_obj, dict):
                    state = result_obj.get("state")
                    task_number = result_obj.get("number")

            return {
                "http_status": response.status_code,
                "success": is_successful,
                "state": state or "Closed Complete",
                "task_number": task_number,
                "data": data,
            }
    except httpx.RequestError as exc:
        logger.error(f"Error de conexión en close_snow_task: {exc}")
        return {
            "http_status": 500,
            "success": False,
            "error": f"Error de conexión con ServiceNow (putTaskInClosedComplete): {str(exc)}",
        }


async def document_servicenow_ticket_process(
    email: str,
    operation_type: str = "reset",
    user_name: Optional[str] = None,
    phone: Optional[str] = None,
    short_description: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    comments: Optional[str] = None,
    work_notes: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Orquesta el flujo integral de documentación en ServiceNow (reinicio de contraseña o desbloqueo de cuenta):
    1. Obtiene el sys_id, manager, nombre y teléfono del usuario por su email (getUser).
    2. Construye la descripción estandarizada requerida:
         Usuario se comunica via copilot para solicitar acceso a su cuenta.
         Nombre: <Nombre>
         Telefono: <Teléfono>
         Correo: <correo>
    3. Define título y subcategoría según el tipo de operación:
       - Reset: 'EVA | INICIO DE SESION | RESET DE CONTRASEÑA' / 'Reset Password'
       - Unlock: 'EVA | INICIO DE SESION | DESBLOQUEO DE CUENTA' / 'Unlock Account'
    4. Crea el requerimiento genérico (createGenericReq).
    5. Aguarda y consulta la tarea técnica sc_task asociada (getTaskKeyListQuery).
    6. Obtiene el sys_id de la sc_task (getTask).
    7. Actualiza asignación, prioridad y categoría/subcategoría en la sc_task (updateTask).
    8. Cierra la tarea en Closed Complete con comentarios y notas internas (putTaskInClosedComplete).
    """
    clean_email = str(email).strip()
    if not clean_email:
        return {
            "success": False,
            "http_status": 400,
            "error": "Debe proporcionarse un correo electrónico válido para registrar el ticket en ServiceNow.",
        }

    op_type = str(operation_type or "").strip().lower()
    is_unlock = op_type in ("unlock", "desbloqueo", "desbloquear", "unlock_account")

    if is_unlock:
        target_short_desc = (
            short_description or "EVA | INICIO DE SESION | DESBLOQUEO DE CUENTA"
        ).strip()
        target_subcategory = (subcategory or "Unlock Account").strip()
        target_comments = (
            comments or "Hola, tu solicitud de desbloqueo de cuenta ha sido atendida y completada con éxito."
        ).strip()
        target_work_notes = (
            work_notes or "Cuenta desbloqueada y ticket completado automáticamente por EVA"
        ).strip()
    else:
        target_short_desc = (
            short_description or "EVA | INICIO DE SESION | RESET DE CONTRASEÑA"
        ).strip()
        target_subcategory = (subcategory or "Reset Password").strip()
        target_comments = (
            comments or "Hola, tu solicitud ha sido atendida y completada con éxito"
        ).strip()
        target_work_notes = (
            work_notes or "Ticket completado automáticamente por EVA"
        ).strip()

    target_category = (category or SNOW_CATEGORY).strip()

    logger.info(
        f"Iniciando flujo de documentación ServiceNow ({target_subcategory}) para {clean_email}..."
    )

    # Paso 1: Buscar usuario
    user_res = await get_snow_user(email=clean_email, token=token)
    if not user_res.get("success") or not user_res.get("user_sys_id"):
        return {
            "success": False,
            "step": "get_user",
            "http_status": user_res.get("http_status", 500),
            "error": f"No fue posible encontrar al usuario con correo '{clean_email}' en ServiceNow.",
            "details": user_res.get("data") or user_res.get("error"),
        }

    user_sys_id = user_res["user_sys_id"]
    manager_sys_id = user_res.get("manager_sys_id") or SNOW_MANAGER_FALLBACK
    snow_name = user_res.get("name")
    snow_phone = user_res.get("phone")

    resolved_name = (user_name or snow_name or "").strip()
    resolved_phone = (phone or snow_phone or "").strip()
    resolved_email = clean_email

    # Plantilla estandarizada de descripción requerida (con saltos de línea como <salto>):
    if not description or description.strip() in (
        "Usuario solicita reinicio de clave de red",
        "Usuario solicita desbloqueo de cuenta",
    ):
        target_description = (
            f"Usuario se comunica via copilot para solicitar acceso a su cuenta.<salto>"
            f"Nombre: {resolved_name}<salto>"
            f"Telefono: {resolved_phone}<salto>"
            f"Correo: {resolved_email}"
        )
    else:
        target_description = (
            description.strip()
            .replace("\r\n", "<salto>")
            .replace("\n", "<salto>")
            .replace("\r", "<salto>")
            .replace("\\n", "<salto>")
        )

    # Paso 2: Crear Requerimiento
    req_res = await create_snow_generic_req(
        user_sys_id=user_sys_id,
        manager_sys_id=manager_sys_id,
        short_description=target_short_desc,
        description=target_description,
        token=token,
    )
    if not req_res.get("success") or not req_res.get("request_sys_id"):
        return {
            "success": False,
            "step": "create_generic_req",
            "http_status": req_res.get("http_status", 500),
            "error": "Fallo al crear la solicitud (REQ) en ServiceNow.",
            "details": req_res.get("data") or req_res.get("error"),
        }

    request_sys_id = req_res["request_sys_id"]
    request_number = req_res.get("request_number")

    # Paso 3: Consultar tarea generada (con retries/espera)
    task_res = await get_snow_task_from_req(
        request_sys_id=request_sys_id, token=token
    )
    if not task_res.get("success") or not task_res.get("task_number"):
        return {
            "success": False,
            "step": "get_task_from_req",
            "request_number": request_number,
            "request_sys_id": request_sys_id,
            "http_status": task_res.get("http_status", 500),
            "error": f"Se creó el requerimiento {request_number}, pero no se pudo localizar su tarea técnica vinculada.",
            "details": task_res.get("data") or task_res.get("error"),
        }

    task_number = task_res["task_number"]

    # Paso 4: Obtener sys_id de la tarea técnica
    task_detail_res = await get_snow_task_details(
        task_number=task_number, token=token
    )
    if not task_detail_res.get("success") or not task_detail_res.get("task_sys_id"):
        return {
            "success": False,
            "step": "get_task_details",
            "request_number": request_number,
            "task_number": task_number,
            "http_status": task_detail_res.get("http_status", 500),
            "error": f"No se pudo consultar el sys_id de la tarea técnica {task_number}.",
            "details": task_detail_res.get("data") or task_detail_res.get("error"),
        }

    task_sys_id = task_detail_res["task_sys_id"]

    # Paso 5: Asignar y clasificar tarea con subcategoría dinámica
    update_res = await update_snow_task(
        task_sys_id=task_sys_id,
        category=target_category,
        subcategory=target_subcategory,
        token=token,
    )
    if not update_res.get("success"):
        logger.warning(
            f"Advertencia: No se pudo actualizar la clasificación de la tarea {task_number}: {update_res}"
        )

    # Paso 6: Cerrar tarea técnica en Closed Complete
    close_res = await close_snow_task(
        task_sys_id=task_sys_id,
        comments=target_comments,
        work_notes=target_work_notes,
        token=token,
    )
    if not close_res.get("success"):
        return {
            "success": False,
            "step": "close_task",
            "request_number": request_number,
            "request_sys_id": request_sys_id,
            "task_number": task_number,
            "task_sys_id": task_sys_id,
            "http_status": close_res.get("http_status", 500),
            "error": f"La solicitud {request_number} y tarea {task_number} fueron creadas pero no se pudieron cerrar.",
            "details": close_res.get("data") or close_res.get("error"),
        }

    logger.info(
        f"Flujo ServiceNow concluido con éxito: REQ={request_number}, TASK={task_number} (Closed Complete)"
    )

    return {
        "success": True,
        "http_status": 200,
        "request_number": request_number,
        "request_sys_id": request_sys_id,
        "task_number": task_number,
        "task_sys_id": task_sys_id,
        "operation_type": "unlock" if is_unlock else "reset",
        "subcategory": target_subcategory,
        "state": close_res.get("state", "Closed Complete"),
        "user_name": resolved_name,
        "user_email": clean_email,
        "message": f"Solicitud {request_number} y tarea {task_number} creadas, asignadas y cerradas exitosamente en ServiceNow ({target_subcategory}).",
    }


async def document_password_reset_ticket(
    email: str,
    short_description: Optional[str] = None,
    description: Optional[str] = None,
    comments: Optional[str] = None,
    work_notes: Optional[str] = None,
    token: Optional[str] = None,
    operation_type: str = "reset",
    user_name: Optional[str] = None,
    phone: Optional[str] = None,
    subcategory: Optional[str] = None,
) -> Dict[str, Any]:
    """Función de compatibilidad para el flujo de documentación."""
    return await document_servicenow_ticket_process(
        email=email,
        operation_type=operation_type,
        user_name=user_name,
        phone=phone,
        short_description=short_description,
        description=description,
        subcategory=subcategory,
        comments=comments,
        work_notes=work_notes,
        token=token,
    )
