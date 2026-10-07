import json
import unittest
from unittest.mock import patch, MagicMock

from starlette.testclient import TestClient
from mcp.server.transport_security import TransportSecuritySettings
from server import mcp_server


class TestStreamableHTTP(unittest.TestCase):
    def setUp(self):
        security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
        self.app = mcp_server.streamable_http_app(
            streamable_http_path="/mcp",
            transport_security=security,
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

    @patch("httpx.AsyncClient.post")
    def test_copilot_studio_flow(self, mock_post):
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
            # 1. MCP Handshake / Initialize (Lo que envía Copilot Studio al conectarse)
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
                headers={"Accept": "application/json, text/event-stream"},
            )
            self.assertEqual(resp_init.status_code, 200)

            # Obtener Session ID de la cabecera
            session_id = resp_init.headers.get("mcp-session-id")
            headers = {"Accept": "application/json, text/event-stream"}
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


if __name__ == "__main__":
    unittest.main()
