import asyncio
import base64
import json
import unittest
from unittest.mock import AsyncMock, patch

from client_api import encode_base64, reset_user_ad_request, send_totp_request, validate_totp_request
from server import mcp_server


class TestProvidentMCP(unittest.TestCase):

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

        # Verificar payload
        call_args = mock_post.call_args
        self.assertIn("/RA/PROVIDENT/validateTOTPProvident", call_args[0][0])
        self.assertEqual(call_args[1]["json"], {"numeroEmpleado": "10005", "otp": "493927"})

    @patch("httpx.AsyncClient.put")
    def test_reset_user_ad_request_mocked(self, mock_put):
        """Verifica la codificación de contraseña y construcción de PUT para resetUserADSA."""
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
        self.assertEqual(result["http_status"], 200)

        # Verificar llamada
        call_args = mock_put.call_args
        self.assertIn("/Active Directory/SA/resetUserADSA", call_args[0][0])
        sent_payload = call_args[1]["json"]
        self.assertEqual(sent_payload["SamAccountName"], "ramiroha")
        self.assertEqual(sent_payload["psw"], "TnVldmFQc3dTRVRYWC4u")
        self.assertEqual(sent_payload["ADUser"], "chatbot.connect")
        self.assertEqual(sent_payload["ADPsw"], "InpqcVN6Uk4xRnpUQWFq")
        self.assertEqual(sent_payload["ADSAServer"], "ADProviTest01.ProvidentMX.Test")

    def test_mcp_tools_registration(self):
        """Verifica que las 3 herramientas estén registradas en el servidor MCP con sus esquemas."""
        tools = asyncio.run(mcp_server.list_tools())
        tool_names = [t.name for t in tools]

        self.assertIn("send_totp_provident", tool_names)
        self.assertIn("validate_totp_provident", tool_names)
        self.assertIn("reset_user_ad_sa", tool_names)

        # Validar herramienta reset_user_ad_sa
        tool_reset = next(t for t in tools if t.name == "reset_user_ad_sa")
        properties = tool_reset.input_schema["properties"]
        self.assertIn("sam_account_name", properties)
        self.assertIn("new_password", properties)
        self.assertIn("sam_account_name", tool_reset.input_schema["required"])
        self.assertIn("new_password", tool_reset.input_schema["required"])


if __name__ == "__main__":
    unittest.main()
