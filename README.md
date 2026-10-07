# Provident MCP Server (Model Context Protocol)

Servidor MCP implementado en **Python** para interactuar con los servicios de autenticación y gestión de Active Directory de Provident.

Este servidor está optimizado y preparado para su integración con **Microsoft Copilot Studio** (a través del transporte estándar **Streamable HTTP**), además de soportar clientes locales (**stdio**) como Antigravity, Claude Desktop o Cursor.

---

## 🛠️ Herramientas Disponibles (Tools)

El servidor expone **3 herramientas principales**:

### 1. `send_totp_provident`
Envía un código de seguridad TOTP / SMS al teléfono registrado del empleado.
* **Parámetros:**
  * `numero_empleado` *(string, obligatorio)*: Identificador del empleado (ejemplo: `"10005"`).
  * `token` *(string, opcional)*: Token Bearer JWT personalizado si se desea sobreescribir el configurado en `.env`.
* **Endpoint subyacente:** `POST https://api.supporttsmx.com.mx/RA/PROVIDENT/sendTOTPProvident`

### 2. `validate_totp_provident`
Valida el código de verificación TOTP / OTP ingresado por el empleado.
* **Parámetros:**
  * `numero_empleado` *(string, obligatorio)*: Identificador del empleado (ejemplo: `"10005"`).
  * `otp` *(string, obligatorio)*: Código TOTP de 6 dígitos que el empleado recibió por SMS (ejemplo: `"493927"`).
  * `token` *(string, opcional)*: Token Bearer JWT personalizado.
* **Endpoint subyacente:** `POST https://api.supporttsmx.com.mx/RA/PROVIDENT/validateTOTPProvident`

### 3. `reset_user_ad_sa`
Restablece la contraseña de una cuenta en el Active Directory de Provident.
> **Codificación automática:** Recibe la nueva contraseña en **texto plano** (ej. `"NuevaPswSETXX.."`) y el servidor la codifica automáticamente en **Base64** antes de enviar la petición.
* **Parámetros:**
  * `sam_account_name` *(string, obligatorio)*: Cuenta de usuario a resetear (ejemplo: `"ramiroha"`).
  * `new_password` *(string, obligatorio)*: Nueva contraseña en texto plano.
  * `ad_user` *(string, opcional)*: Usuario de servicio del AD (por defecto toma el configurado en `.env`: `chatbot.connect`).
  * `ad_server` *(string, opcional)*: Servidor de Active Directory (por defecto toma el de `.env`: `ADProviTest01.ProvidentMX.Test`).
  * `token` *(string, opcional)*: Token Bearer JWT personalizado.
* **Endpoint subyacente:** `PUT https://api.supporttsmx.com.mx:6443/Active Directory/SA/resetUserADSA`

---

## 🚀 Requisitos e Instalación

### Requisitos previos
- Python 3.10 o superior (probado en Python 3.12).
- Gestor de paquetes `pip` o `uv`.

### 1. Clonar / Acceder al proyecto
```bash
cd /home/a200238569@tslab.mx/Documents/MCP_Provident
```

### 2. Crear y activar entorno virtual
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno (`.env`)
Copia la plantilla `.env.example` a `.env` y configura tus credenciales:

```bash
cp .env.example .env
```

Ejemplo de configuración en `.env`:
```env
# Token JWT Bearer para autorizar las peticiones
PROVIDENT_BEARER_TOKEN=tu_token_jwt_aqui

# Endpoints base
PROVIDENT_BASE_URL=https://api.supporttsmx.com.mx
PROVIDENT_AD_URL=https://api.supporttsmx.com.mx:6443

# Credenciales de Active Directory por defecto
AD_DEFAULT_USER=chatbot.connect
AD_DEFAULT_PSW=tu_contraseña_ad_en_base64
AD_DEFAULT_SERVER=ADProviTest01.ProvidentMX.Test

# Configuración del servidor MCP
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_PATH=/mcp
```

---

## 🌐 Conexión con Microsoft Copilot Studio

Microsoft Copilot Studio requiere conectarse a un servidor MCP mediante el protocolo **Streamable HTTP**.

### 1. Iniciar el servidor
Por defecto, el servidor se ejecuta en modo **Streamable HTTP**:
```bash
source .venv/bin/activate
python server.py
```
El servidor quedará escuchando en `http://0.0.0.0:8000/mcp`.

> **Nota:** Puedes comprobar que el servicio está activo visitando `http://localhost:8000/health`.

### 2. Exponer el servidor con una URL pública HTTPS
Copilot Studio se ejecuta en la nube de Microsoft (Power Platform), por lo que necesita un endpoint HTTPS accesible por internet. Puedes usar:

- **ngrok** (para pruebas rápidas y desarrollo local):
  ```bash
  ngrok http 8000
  ```
  Obtendrás una URL como: `https://xxxx-xx-xx.ngrok-free.app`
- **Despliegue en la nube** (para producción): Azure App Service, Azure Container Apps, Cloud Run, etc.

### 3. Configuración en Microsoft Copilot Studio
1. Abre tu agente en **Microsoft Copilot Studio**.
2. Asegúrate de tener activada la **Orquestación generativa** (*Generative orchestration*) en la configuración del agente.
3. Ve a la pestaña **Herramientas (Tools)** > **Agregar una herramienta (Add a tool)**.
4. Selecciona **Model Context Protocol (MCP)**.
5. Completa los datos:
   * **Nombre:** `Provident MCP`
   * **Descripción:** `Herramientas para autenticación TOTP y reseteo de Active Directory en Provident.`
   * **URL del servidor (Server URL):** `https://<tu-url-publica>/mcp`
   * **Tipo de autenticación:** `None` (o API Key si configuras un reverse proxy intermedio).
6. Haz clic en **Guardar/Conectar**. Copilot Studio descubrirá automáticamente las 3 herramientas (`send_totp_provident`, `validate_totp_provident`, `reset_user_ad_sa`).

---

## 💻 Uso Local con Clientes MCP (stdio)

Si deseas utilizar este servidor en clientes locales como **Antigravity**, **Claude Desktop** o **Cursor**, ejecútalo en modo `stdio`:

### Configuración en `mcp_config.json` / `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "provident-mcp": {
      "command": "/home/a200238569@tslab.mx/Documents/MCP_Provident/.venv/bin/python",
      "args": [
        "/home/a200238569@tslab.mx/Documents/MCP_Provident/server.py",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

---

## 🧪 Ejecución de Pruebas Unitarias

El proyecto incluye pruebas unitarias que simulan (mockean) las llamadas HTTP sin tocar las APIs productivas:

```bash
source .venv/bin/activate
python -m unittest discover tests
```
