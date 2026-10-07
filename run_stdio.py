"""
Script de entrada directo para clientes MCP locales (stdio).
Ideal para MCP Inspector, Claude Desktop, Antigravity y Cursor.
Evita problemas con argumentos de línea de comandos en interfaces gráficas.
"""
from server import mcp_server

if __name__ == "__main__":
    mcp_server.run(transport="stdio")
