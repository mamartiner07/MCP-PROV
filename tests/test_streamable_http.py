import json
import unittest
from unittest.mock import patch, MagicMock

from starlette.testclient import TestClient
from server import create_streamable_http_app


class TestStreamableHTTP(unittest.TestCase):
    def setUp(self):
        self.api_key = "test-secret-key-123"
        self.app = create_streamable_http_app(
            path="/mcp",
            api_key=self.api_key,
        )

    def test_health_check(self):
        with TestClient(self.app) as client:
            resp = client.get("/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["service"], "mcp-provident")

    def test_root_endpoint(self):
        with TestClient(self.app) as client:
            resp = client.get("/")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "running")
            self.assertEqual(data["mcp_endpoint"], "/mcp")

    def test_unauthorized_without_api_key(self):
        with TestClient(self.app) as client:
            resp = client.post("/mcp", json={})
            self.assertEqual(resp.status_code, 401)
            self.assertIn("Unauthorized", resp.text)

    def test_unauthorized_with_wrong_api_key(self):
        with TestClient(self.app) as client:
            resp = client.post("/mcp", json={}, headers={"X-API-Key": "clave_incorrecta"})
            self.assertEqual(resp.status_code, 401)
            self.assertIn("Unauthorized", resp.text)

    @patch("httpx.AsyncClient.post")
    def test_copilot_studio_flow_with_x_api_key(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "status": "success",
            "message": "mensaje sms enviado",
            "returnCode": 200,
        }
        mock_post.return_value = mock_response

        with TestClient(self.app) as client:
            # 1. MCP Handshake / Initialize con Header X-API-Key
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "CopilotStudio", "version": "1.0"},
                },
            }
            resp_init = client.post(
                "/mcp",
                json=init_payload,
                headers={
                    "Accept": "application/json, text/event-stream",
                    "X-API-Key": self.api_key,
                },
            )
            self.assertEqual(resp_init.status_code, 200)

            # Obtener Session ID de la cabecera
            session_id = resp_init.headers.get("mcp-session-id")
            headers = {
                "Accept": "application/json, text/event-stream",
                "X-API-Key": self.api_key,
            }
            if session_id:
                headers["mcp-session-id"] = session_id

            # 2. Copilot Studio descubre las herramientas (tools/list)
            list_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
            resp_list = client.post("/mcp", json=list_payload, headers=headers)
            self.assertEqual(resp_list.status_code, 200)
            self.assertIn("send_totp_provident", resp_list.text)
            self.assertIn("validate_totp_provident", resp_list.text)
            self.assertIn("reset_user_ad_sa", resp_list.text)

            # 3. Copilot Studio invoca una herramienta (tools/call)
            call_payload = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "send_totp_provident",
                    "arguments": {"numero_empleado": "10005"},
                },
            }
            resp_call = client.post("/mcp", json=call_payload, headers=headers)
            self.assertEqual(resp_call.status_code, 200)
            self.assertIn("mensaje sms enviado", resp_call.text)

    def test_authorization_bearer_header_support(self):
        with TestClient(self.app) as client:
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "CopilotStudio", "version": "1.0"},
                },
            }
            resp = client.post(
                "/mcp",
                json=init_payload,
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
