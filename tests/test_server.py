import asyncio
import base64
import json
import unittest
from unittest.mock import AsyncMock, patch

from client_api import (
    close_snow_task,
    create_snow_generic_req,
    document_password_reset_ticket,
    document_servicenow_ticket_process,
    encode_base64,
    generate_secure_password,
    get_snow_task_details,
    get_snow_task_from_req,
    get_snow_user,
    reset_user_ad_request,
    sanitize_sam_account_name,
    send_sms_chatbridge_request,
    send_totp_request,
    unlock_user_ad_request,
    update_snow_task,
    validate_totp_request,
)
from server import mcp_server


class TestProvidentMCP(unittest.TestCase):

    def test_sanitize_sam_account_name(self):
        """Verifica la limpieza de prefijos de dominio en SamAccountName."""
        self.assertEqual(sanitize_sam_account_name("PROVIDENTMX/ramiroha"), "ramiroha")
        self.assertEqual(sanitize_sam_account_name("PROVIDENTMX\\ramiroha"), "ramiroha")
        self.assertEqual(sanitize_sam_account_name("ramiroha"), "ramiroha")
        self.assertEqual(sanitize_sam_account_name("  PROVIDENTMX/ramiroha  "), "ramiroha")
        self.assertEqual(sanitize_sam_account_name(""), "")
        self.assertEqual(sanitize_sam_account_name(None), "")

    def test_generate_secure_password(self):
        """Verifica que la contraseña generada cumpla las políticas mínimas."""
        for _ in range(10):
            pwd = generate_secure_password(12)
            self.assertGreaterEqual(len(pwd), 12)
            self.assertTrue(any(c.isupper() for c in pwd), "Debe contener mayúsculas")
            self.assertTrue(any(c.islower() for c in pwd), "Debe contener minúsculas")
            self.assertTrue(any(c.isdigit() for c in pwd), "Debe contener dígitos")
            self.assertTrue(any(c in "!@#$%&*-_=+" for c in pwd), "Debe contener un signo especial")

    def test_base64_encoding(self):
        """Verifica que la codificación Base64 coincida con el formato esperado."""
        plain_text = "NuevaPswSETXX.."
        expected_b64 = "TnVldmFQc3dTRVRYWC4u"
        self.assertEqual(encode_base64(plain_text), expected_b64)

    @patch("httpx.AsyncClient.post")
    def test_send_totp_request_mocked(self, mock_post):
        """Verifica la construcción de la petición para send_totp."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "message": "mensaje sms enviado",
            "function": "sendTOTPProvident",
            "returnCode": 200,
        }
        mock_post.return_value = mock_response

        result = asyncio.run(send_totp_request(numero_empleado="10005"))

        self.assertTrue(result["success"])
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["data"]["status"], "success")

        # Verificar argumentos enviados a httpx.post
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn("/RA/PROVIDENT/sendTOTPProvident", call_args[0][0])
        self.assertEqual(call_args[1]["json"], {"numeroEmpleado": "10005"})
        self.assertIn("Authorization", call_args[1]["headers"])

    @patch("httpx.AsyncClient.post")
    def test_validate_totp_request_mocked(self, mock_post):
        """Verifica la construcción de la petición para validate_totp."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "message": "TOTP validado correctamente",
            "returnCode": 200,
        }
        mock_post.return_value = mock_response

        result = asyncio.run(validate_totp_request(numero_empleado="10005", otp="493927"))

        self.assertTrue(result["success"])
        self.assertEqual(result["http_status"], 200)
        self.assertIsNone(result["sam_account_name"])

        # Verificar payload
        call_args = mock_post.call_args
        self.assertIn("/RA/PROVIDENT/validateTOTPProvident", call_args[0][0])
        self.assertEqual(call_args[1]["json"], {"numeroEmpleado": "10005", "otp": "493927"})

    @patch("httpx.AsyncClient.post")
    def test_validate_totp_request_with_ad_result(self, mock_post):
        """Verifica la extracción automática de sam_account_name desde result.AD con HTTP 302."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 302
        mock_response.is_success = False
        mock_response.json.return_value = {
            "status": "success",
            "message": "registro encontrado",
            "function": "validateTOTPProvident",
            "modulo": "Robot Assistant",
            "returnCode": 302,
            "result": {
                "phone": "5519231854",
                "email": "Mario Aldair Reyes Martinez",
                "name": "lupita.chat@provident.com.mx",
                "AD": "PROVIDENTMX/ramiroha",
            },
        }
        mock_post.return_value = mock_response

        result = asyncio.run(validate_totp_request(numero_empleado="10005", otp="493927"))

        self.assertTrue(result["success"])
        self.assertEqual(result["sam_account_name"], "ramiroha")
        self.assertEqual(result["phone"], "5519231854")
        self.assertEqual(result["data"]["result"]["AD"], "PROVIDENTMX/ramiroha")

    @patch("httpx.AsyncClient.post")
    def test_validate_totp_request_with_empty_ad(self, mock_post):
        """Verifica que sam_account_name sea None si el campo AD está vacío."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "message": "registro encontrado",
            "function": "validateTOTPProvident",
            "modulo": "Robot Assistant",
            "returnCode": 302,
            "result": {
                "phone": "5519231854",
                "email": "Mario Aldair Reyes Martinez",
                "name": "lupita.chat@provident.com.mx",
                "AD": "",
            },
        }
        mock_post.return_value = mock_response

        result = asyncio.run(validate_totp_request(numero_empleado="10005", otp="493927"))

        self.assertTrue(result["success"])
        self.assertIsNone(result["sam_account_name"])
        self.assertEqual(result["phone"], "5519231854")

    @patch("httpx.AsyncClient.post")
    def test_send_sms_chatbridge_request(self, mock_post):
        """Verifica la petición HTTP para envío de SMS vía ChatBridge."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "message": "Message sent successfully",
        }
        mock_post.return_value = mock_response

        result = asyncio.run(
            send_sms_chatbridge_request(
                to="5519231854",
                text="Tu contraseña es 12345",
            )
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["http_status"], 200)

        # Verificar headers y payload
        call_args = mock_post.call_args
        self.assertIn("/v1/sms/messages", call_args[0][0])
        self.assertEqual(call_args[1]["headers"]["Content-Type"], "application/json")
        self.assertIn("x-api-key", call_args[1]["headers"])
        sent_payload = call_args[1]["json"]
        self.assertEqual(sent_payload["to"], "5519231854")
        self.assertEqual(sent_payload["text"], "Tu contraseña es 12345")
        self.assertEqual(sent_payload["mask"], "6aac0ecdb99ccfcfa56bbc2d")

    @patch("httpx.AsyncClient.post")
    @patch("httpx.AsyncClient.put")
    def test_reset_user_ad_request_with_phone_triggers_sms(self, mock_put, mock_post):
        """Verifica que si se envía phone a reset_user_ad_request, se despache el SMS automáticamente."""
        ad_response = unittest.mock.MagicMock()
        ad_response.status_code = 200
        ad_response.is_success = True
        ad_response.json.return_value = {"status": "success", "message": "Reset OK"}
        mock_put.return_value = ad_response

        sms_response = unittest.mock.MagicMock()
        sms_response.status_code = 200
        sms_response.is_success = True
        sms_response.json.return_value = {"status": "sent"}
        mock_post.return_value = sms_response

        result = asyncio.run(
            reset_user_ad_request(
                sam_account_name="ramiroha",
                phone="5519231854",
            )
        )

        self.assertTrue(result["success"])
        self.assertIn("sms_notification", result)
        self.assertTrue(result["sms_notification"]["sent"])
        self.assertEqual(result["sms_notification"]["to"], "5519231854")

        # Verificar que httpx.post fue invocado con el SMS conteniendo la contraseña generada
        mock_post.assert_called_once()
        sent_sms = mock_post.call_args[1]["json"]
        self.assertEqual(sent_sms["to"], "5519231854")
        self.assertIn(result["temporary_password"], sent_sms["text"])

    @patch("httpx.AsyncClient.put")
    def test_reset_user_ad_request_sanitizes_domain_prefix(self, mock_put):
        """Verifica que reset_user_ad_request limpie el prefijo de dominio si se envía PROVIDENTMX/."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "message": "Password reset successful",
        }
        mock_put.return_value = mock_response

        result = asyncio.run(
            reset_user_ad_request(
                sam_account_name="PROVIDENTMX/ramiroha",
            )
        )

        self.assertTrue(result["success"])
        sent_payload = mock_put.call_args[1]["json"]
        self.assertEqual(sent_payload["SamAccountName"], "ramiroha")

    @patch("httpx.AsyncClient.put")
    def test_reset_user_ad_request_auto_generated_password(self, mock_put):
        """Verifica que si no se proporciona new_password, el servidor genere una automáticamente."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "message": "Password reset successful",
        }
        mock_put.return_value = mock_response

        result = asyncio.run(
            reset_user_ad_request(
                sam_account_name="ramiroha",
            )
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["http_status"], 200)
        self.assertIn("temporary_password", result)
        generated_pwd = result["temporary_password"]
        self.assertGreaterEqual(len(generated_pwd), 12)

        # Verificar llamada
        call_args = mock_put.call_args
        self.assertIn("/Active Directory/SA/resetUserADSA", call_args[0][0])
        sent_payload = call_args[1]["json"]
        self.assertEqual(sent_payload["SamAccountName"], "ramiroha")
        self.assertEqual(sent_payload["psw"], encode_base64(generated_pwd))
        self.assertEqual(sent_payload["ADUser"], "chatbot.connect")

    @patch("httpx.AsyncClient.put")
    def test_reset_user_ad_request_custom_password(self, mock_put):
        """Verifica el reseteo con contraseña explícita."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "message": "Password reset successful",
        }
        mock_put.return_value = mock_response

        result = asyncio.run(
            reset_user_ad_request(
                sam_account_name="ramiroha",
                new_password="NuevaPswSETXX..",
            )
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["temporary_password"], "NuevaPswSETXX..")
        sent_payload = mock_put.call_args[1]["json"]
        self.assertEqual(sent_payload["psw"], "TnVldmFQc3dTRVRYWC4u")

    @patch("httpx.AsyncClient.get")
    def test_get_snow_user(self, mock_get):
        """Verifica la consulta de usuario en ServiceNow por email."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "message": "User found with dulce.mejia@provident.com.mx",
            "returnCode": 200,
            "result": [
                {
                    "sys_id": "81cea343db872700d4b4adc3ca9619a2",
                    "name": "Dulce Amellaly Mejia Quintero",
                    "email": "dulce.mejia@provident.com.mx",
                    "manager": {
                        "value": "d762422f6fd402005f7790354b3ee467",
                    },
                }
            ],
        }
        mock_get.return_value = mock_response

        result = asyncio.run(get_snow_user(email="dulce.mejia@provident.com.mx"))
        self.assertTrue(result["success"])
        self.assertEqual(result["user_sys_id"], "81cea343db872700d4b4adc3ca9619a2")
        self.assertEqual(result["manager_sys_id"], "d762422f6fd402005f7790354b3ee467")
        self.assertEqual(result["name"], "Dulce Amellaly Mejia Quintero")

    @patch("httpx.AsyncClient.post")
    def test_create_snow_generic_req(self, mock_post):
        """Verifica la creación del requerimiento genérico (REQ) en ServiceNow."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "message": "Generic Request created REQ0431059",
            "returnCode": 200,
            "result": {
                "sys_id": "9e5ed8fb3b3f07507e29d32a85e45abf",
                "number": "REQ0431059",
                "request_number": "REQ0431059",
                "request_id": "9e5ed8fb3b3f07507e29d32a85e45abf",
            },
        }
        mock_post.return_value = mock_response

        result = asyncio.run(
            create_snow_generic_req(
                user_sys_id="81cea343db872700d4b4adc3ca9619a2",
                manager_sys_id="d762422f6fd402005f7790354b3ee467",
            )
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["request_number"], "REQ0431059")
        self.assertEqual(result["request_sys_id"], "9e5ed8fb3b3f07507e29d32a85e45abf")

        sent_payload = mock_post.call_args[1]["json"]
        self.assertEqual(sent_payload["vs_requested_for_user"], "81cea343db872700d4b4adc3ca9619a2")
        self.assertEqual(sent_payload["vs_requestor_manager"], "d762422f6fd402005f7790354b3ee467")

    @patch("httpx.AsyncClient.get")
    def test_get_snow_task_from_req(self, mock_get):
        """Verifica la obtención de la tarea técnica vinculada al requerimiento."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "returnCode": 200,
            "result": {
                "task": [
                    {"number": "TASK0487110"}
                ]
            },
        }
        mock_get.return_value = mock_response

        result = asyncio.run(get_snow_task_from_req(request_sys_id="9e5ed8fb3b3f07507e29d32a85e45abf"))
        self.assertTrue(result["success"])
        self.assertEqual(result["task_number"], "TASK0487110")

    @patch("httpx.AsyncClient.get")
    def test_get_snow_task_details(self, mock_get):
        """Verifica la consulta de detalles de la tarea técnica por su número."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "returnCode": 200,
            "result": [
                {
                    "sys_id": "f25e1cfb3b3f07507e29d32a85e45a32",
                    "number": "TASK0487110",
                }
            ],
        }
        mock_get.return_value = mock_response

        result = asyncio.run(get_snow_task_details(task_number="TASK0487110"))
        self.assertTrue(result["success"])
        self.assertEqual(result["task_sys_id"], "f25e1cfb3b3f07507e29d32a85e45a32")

    @patch("httpx.AsyncClient.put")
    def test_update_snow_task(self, mock_put):
        """Verifica la actualización de grupo, prioridad y categorías en la tarea técnica."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "returnCode": 200,
        }
        mock_put.return_value = mock_response

        result = asyncio.run(update_snow_task(task_sys_id="f25e1cfb3b3f07507e29d32a85e45a32"))
        self.assertTrue(result["success"])
        sent_payload = mock_put.call_args[1]["json"]
        self.assertEqual(sent_payload["sys_id"], "f25e1cfb3b3f07507e29d32a85e45a32")
        self.assertEqual(sent_payload["priority"], "4")
        self.assertEqual(sent_payload["u_category"], "Active Directory")

    @patch("httpx.AsyncClient.put")
    def test_close_snow_task(self, mock_put):
        """Verifica el cierre de la tarea técnica en Closed Complete."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "returnCode": 200,
            "result": {
                "number": "TASK0487110",
                "sys_id": "f25e1cfb3b3f07507e29d32a85e45a32",
                "state": "Closed Complete",
            },
        }
        mock_put.return_value = mock_response

        result = asyncio.run(close_snow_task(task_sys_id="f25e1cfb3b3f07507e29d32a85e45a32"))
        self.assertTrue(result["success"])
        self.assertEqual(result["state"], "Closed Complete")
        sent_payload = mock_put.call_args[1]["json"]
        self.assertEqual(sent_payload["sys_id"], "f25e1cfb3b3f07507e29d32a85e45a32")

    @patch("client_api.get_snow_user")
    @patch("client_api.create_snow_generic_req")
    @patch("client_api.get_snow_task_from_req")
    @patch("client_api.get_snow_task_details")
    @patch("client_api.update_snow_task")
    @patch("client_api.close_snow_task")
    def test_document_password_reset_ticket_orchestration(
        self, mock_close, mock_update, mock_details, mock_from_req, mock_create, mock_get_user
    ):
        """Verifica la orquestación completa de los 6 pasos en document_password_reset_ticket."""
        mock_get_user.return_value = {
            "success": True,
            "user_sys_id": "81cea343db872700d4b4adc3ca9619a2",
            "manager_sys_id": "d762422f6fd402005f7790354b3ee467",
            "name": "Dulce Amellaly Mejia Quintero",
        }
        mock_create.return_value = {
            "success": True,
            "request_sys_id": "9e5ed8fb3b3f07507e29d32a85e45abf",
            "request_number": "REQ0431059",
        }
        mock_from_req.return_value = {
            "success": True,
            "task_number": "TASK0487110",
        }
        mock_details.return_value = {
            "success": True,
            "task_sys_id": "f25e1cfb3b3f07507e29d32a85e45a32",
        }
        mock_update.return_value = {
            "success": True,
        }
        mock_close.return_value = {
            "success": True,
            "state": "Closed Complete",
        }

        result = asyncio.run(
            document_password_reset_ticket(
                email="dulce.mejia@provident.com.mx"
            )
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["request_number"], "REQ0431059")
        self.assertEqual(result["task_number"], "TASK0487110")
        self.assertEqual(result["state"], "Closed Complete")
        self.assertEqual(result["user_name"], "Dulce Amellaly Mejia Quintero")
        self.assertIn("REQ0431059", result["message"])

    @patch("httpx.AsyncClient.put")
    def test_unlock_user_ad_request_mocked(self, mock_put):
        """Verifica la petición HTTP para desbloqueo de cuenta en Active Directory."""
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "message": "user ramiroha unlock in Active Directory",
            "function": "unlockUserADSA",
            "modulo": "Active Directory",
            "returnCode": 200,
        }
        mock_put.return_value = mock_response

        result = asyncio.run(unlock_user_ad_request(sam_account_name="PROVIDENTMX/ramiroha"))

        self.assertTrue(result["success"])
        self.assertEqual(result["sam_account_name"], "ramiroha")
        sent_payload = mock_put.call_args[1]["json"]
        self.assertEqual(sent_payload["SamAccountName"], "ramiroha")
        self.assertIn("unlockUserADSA", mock_put.call_args[0][0])

    @patch("client_api.get_snow_user")
    @patch("client_api.create_snow_generic_req")
    @patch("client_api.get_snow_task_from_req")
    @patch("client_api.get_snow_task_details")
    @patch("client_api.update_snow_task")
    @patch("client_api.close_snow_task")
    def test_document_servicenow_ticket_unlock_orchestration(
        self, mock_close, mock_update, mock_details, mock_from_req, mock_create, mock_get_user
    ):
        """Verifica la orquestación para desbloqueo de cuenta con título, subcategoría y descripción requerida."""
        mock_get_user.return_value = {
            "success": True,
            "user_sys_id": "81cea343db872700d4b4adc3ca9619a2",
            "manager_sys_id": "d762422f6fd402005f7790354b3ee467",
            "name": "Dulce Amellaly Mejia Quintero",
            "phone": "2227391030",
        }
        mock_create.return_value = {
            "success": True,
            "request_sys_id": "9e5ed8fb3b3f07507e29d32a85e45abf",
            "request_number": "REQ0431059",
        }
        mock_from_req.return_value = {
            "success": True,
            "task_number": "TASK0487110",
        }
        mock_details.return_value = {
            "success": True,
            "task_sys_id": "f25e1cfb3b3f07507e29d32a85e45a32",
        }
        mock_update.return_value = {
            "success": True,
        }
        mock_close.return_value = {
            "success": True,
            "state": "Closed Complete",
        }

        result = asyncio.run(
            document_servicenow_ticket_process(
                email="dulce.mejia@provident.com.mx",
                operation_type="unlock",
            )
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["operation_type"], "unlock")
        self.assertEqual(result["subcategory"], "Unlock Account")

        # Verificar parámetros enviados a create_snow_generic_req
        create_args = mock_create.call_args[1]
        self.assertEqual(create_args["short_description"], "EVA | INICIO DE SESION | DESBLOQUEO DE CUENTA")
        self.assertIn("Usuario se comunica via copilot para solicitar acceso a su cuenta.", create_args["description"])
        self.assertIn("Nombre: Dulce Amellaly Mejia Quintero", create_args["description"])
        self.assertIn("Telefono: 2227391030", create_args["description"])
        self.assertIn("Correo: dulce.mejia@provident.com.mx", create_args["description"])

        # Verificar subcategoría enviada a update_snow_task
        update_args = mock_update.call_args[1]
        self.assertEqual(update_args["subcategory"], "Unlock Account")

    def test_mcp_tools_registration(self):
        """Verifica que las 6 herramientas estén registradas en el servidor MCP con sus esquemas."""
        tools = asyncio.run(mcp_server.list_tools())
        tool_names = [t.name for t in tools]

        self.assertIn("send_totp_provident", tool_names)
        self.assertIn("validate_totp_provident", tool_names)
        self.assertIn("reset_user_ad_sa", tool_names)
        self.assertIn("unlock_user_ad_sa", tool_names)
        self.assertIn("send_sms_provident", tool_names)
        self.assertIn("document_servicenow_ticket", tool_names)

        # Validar herramienta reset_user_ad_sa
        tool_reset = next(t for t in tools if t.name == "reset_user_ad_sa")
        properties = tool_reset.input_schema["properties"]
        self.assertIn("sam_account_name", properties)
        self.assertIn("phone", properties)
        self.assertIn("sam_account_name", tool_reset.input_schema["required"])
        self.assertNotIn("phone", tool_reset.input_schema.get("required", []))
        self.assertNotIn("new_password", tool_reset.input_schema.get("required", []))

        # Validar herramienta unlock_user_ad_sa
        tool_unlock = next(t for t in tools if t.name == "unlock_user_ad_sa")
        unlock_props = tool_unlock.input_schema["properties"]
        self.assertIn("sam_account_name", unlock_props)
        self.assertIn("sam_account_name", tool_unlock.input_schema["required"])

        # Validar herramienta send_sms_provident
        tool_sms = next(t for t in tools if t.name == "send_sms_provident")
        sms_properties = tool_sms.input_schema["properties"]
        self.assertIn("to", sms_properties)
        self.assertIn("text", sms_properties)
        self.assertIn("to", tool_sms.input_schema["required"])
        self.assertIn("text", tool_sms.input_schema["required"])

        # Validar herramienta document_servicenow_ticket
        tool_doc = next(t for t in tools if t.name == "document_servicenow_ticket")
        doc_properties = tool_doc.input_schema["properties"]
        self.assertIn("email", doc_properties)
        self.assertIn("operation_type", doc_properties)
        self.assertIn("user_name", doc_properties)
        self.assertIn("phone", doc_properties)
        self.assertIn("short_description", doc_properties)
        self.assertIn("description", doc_properties)
        self.assertIn("comments", doc_properties)
        self.assertIn("work_notes", doc_properties)
        self.assertIn("email", tool_doc.input_schema["required"])


if __name__ == "__main__":
    unittest.main()

