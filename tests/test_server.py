import asyncio
import base64
import json
import unittest
from unittest.mock import AsyncMock, patch

from client_api import (
    encode_base64,
    generate_secure_password,
    reset_user_ad_request,
    sanitize_sam_account_name,
    send_sms_chatbridge_request,
    send_totp_request,
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
        """Verifica la extracción automática de sam_account_name desde result.AD."""
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

    def test_mcp_tools_registration(self):
        """Verifica que las 4 herramientas estén registradas en el servidor MCP con sus esquemas."""
        tools = asyncio.run(mcp_server.list_tools())
        tool_names = [t.name for t in tools]

        self.assertIn("send_totp_provident", tool_names)
        self.assertIn("validate_totp_provident", tool_names)
        self.assertIn("reset_user_ad_sa", tool_names)
        self.assertIn("send_sms_provident", tool_names)

        # Validar herramienta reset_user_ad_sa
        tool_reset = next(t for t in tools if t.name == "reset_user_ad_sa")
        properties = tool_reset.input_schema["properties"]
        self.assertIn("sam_account_name", properties)
        self.assertIn("phone", properties)
        self.assertIn("sam_account_name", tool_reset.input_schema["required"])
        self.assertNotIn("phone", tool_reset.input_schema.get("required", []))
        self.assertNotIn("new_password", tool_reset.input_schema.get("required", []))

        # Validar herramienta send_sms_provident
        tool_sms = next(t for t in tools if t.name == "send_sms_provident")
        sms_properties = tool_sms.input_schema["properties"]
        self.assertIn("to", sms_properties)
        self.assertIn("text", sms_properties)
        self.assertIn("to", tool_sms.input_schema["required"])
        self.assertIn("text", tool_sms.input_schema["required"])


if __name__ == "__main__":
    unittest.main()

