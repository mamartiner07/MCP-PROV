# Especificación Técnica: Integración ServiceNow (Creación y Cierre de Tickets)

**Para:** Equipo de Desarrollo / Integraciones  
**Asunto:** Especificación Técnica de Integración ServiceNow – Flujo Automatizado de Creación y Cierre de Tickets  

---

Estimado equipo,

A partir de las pruebas de integración realizadas con la API de ServiceNow, les compartimos la especificación técnica de los **5 endpoints requeridos** para implementar el flujo automatizado de punta a punta (búsqueda de usuario, generación del ticket, asignación y cierre).

Se incluyen las plantillas con los parámetros y cuerpos en blanco (*placeholders*) para facilitar su parametrización dinámica en el servicio.

---

## Diagrama del Flujo

```text
[1. GET User] ──► [2. POST Order] ──► [Espera 3s] ──► [3. GET Task IDs] ──► [4. PATCH Assign] ──► [5. PATCH Close + Notes]
  (sys_user)        (order_now)                             (sc_task)            (sc_task)               (sc_task)
```

---

## Especificación Detallada de los 5 Endpoints

### 1. Búsqueda de Usuario por Correo (GET)
**Propósito:** Obtener el identificador (`sys_id`) del usuario final y de su responsable directo (`manager`) para cumplir con las reglas de auto-aprobación del catálogo.

* **Método:** `GET`
* **URL:**  
  `https://<INSTANCIA_SERVICENOW>/api/now/table/sys_user?sysparm_query=email=<CORREO_USUARIO>&sysparm_fields=sys_id,name,manager`
* **Headers:**
  ```http
  Authorization: Basic <CREDENCIALES_BASE64>
  Accept: application/json
  ```
* **Variables a extraer de la respuesta:**
  * `USER_SYS_ID`: `result[0].sys_id`
  * `MANAGER_SYS_ID`: `result[0].manager.value` *(En caso de venir nulo o vacío, utilizar el ID de fallback: `d8423b640fd402003e6c85ece1050e1e`)*.

---

### 2. Creación de Solicitud en el Catálogo (POST)
**Propósito:** Invocar el catálogo *Generic Request* vía `order_now` para generar de manera simultánea el `REQ`, el `RITM` y la `SCTASK`.

* **Método:** `POST`
* **URL:**  
  `https://<INSTANCIA_SERVICENOW>/api/sn_sc/servicecatalog/items/<CATALOG_ITEM_SYS_ID>/order_now`
* **Headers:**
  ```http
  Authorization: Basic <CREDENCIALES_BASE64>
  Content-Type: application/json
  Accept: application/json
  ```
* **Body (Plantilla en Blanco):**
  ```json
  {
    "sysparm_quantity": 1,
    "variables": {
      "vs_requestor": "<SOLICITANTE_TECNICO_SYS_ID>",
      "vs_requested_for": true,
      "vs_requested_for_user": "<USER_SYS_ID>",
      "vs_requestor_manager": "<MANAGER_SYS_ID>",
      "u_business_service": "<BUSINESS_SERVICE_SYS_ID>",
      "generic_short_description": "<TITULO_SOLICITUD>",
      "generic_description": "<DESCRIPCION_DETALLADA>"
    }
  }
  ```
* **Variables a extraer de la respuesta:**
  * `REQUEST_ID`: `result.request_id` (sys_id del REQ)
  * `REQUEST_NUMBER`: `result.request_number`

> ⏱ **Nota de temporización:** Se requiere una pausa de **2 a 3 segundos** antes del siguiente paso, mientras ServiceNow concluye la instanciación de la tarea técnica (`sc_task`).

---

### 3. Consulta de SCTASK y RITM (GET)
**Propósito:** Recuperar el identificador técnico (`sys_id`) de la tarea generada para proceder a su actualización y cierre en una sola consulta vía *dot-walking*.

* **Método:** `GET`
* **URL:**  
  `https://<INSTANCIA_SERVICENOW>/api/now/table/sc_task?sysparm_query=request_item.request=<REQUEST_ID>&sysparm_fields=sys_id,number,request_item.number`
* **Headers:**
  ```http
  Authorization: Basic <CREDENCIALES_BASE64>
  Accept: application/json
  ```
* **Variables a extraer de la respuesta:**
  * `TASK_SYS_ID`: `result[0].sys_id`
  * `TASK_NUMBER`: `result[0].number`
  * `RITM_NUMBER`: `result[0]['request_item.number']`

---

### 4. Asignación, Priorización y Categorización de la SCTASK (PATCH)
**Propósito:** Asignar el grupo resolutor, la prioridad de atención y la clasificación de soporte en la tarea.

* **Método:** `PATCH`
* **URL:**  
  `https://<INSTANCIA_SERVICENOW>/api/now/table/sc_task/<TASK_SYS_ID>`
* **Headers:**
  ```http
  Authorization: Basic <CREDENCIALES_BASE64>
  Content-Type: application/json
  Accept: application/json
  ```
* **Body (Plantilla en Blanco):**
  ```json
  {
    "assignment_group": "<ASSIGNMENT_GROUP_SYS_ID>",
    "priority": "<NIVEL_PRIORIDAD>",
    "u_category": "<CATEGORIA>",
    "u_subcategory": "<SUBCATEGORIA>"
  }
  ```

---

### 5. Cierre y Documentación de la SCTASK (PATCH)
**Propósito:** Marcar la tarea en estado *Closed Complete*, registrar notas técnicas internas (*work_notes*) y notificar al usuario final (*comments*).

* **Método:** `PATCH`
* **URL:**  
  `https://<INSTANCIA_SERVICENOW>/api/now/table/sc_task/<TASK_SYS_ID>`
* **Headers:**
  ```http
  Authorization: Basic <CREDENCIALES_BASE64>
  Content-Type: application/json
  Accept: application/json
  ```
* **Body (Plantilla en Blanco):**
  ```json
  {
    "state": "3",
    "comments": "<COMENTARIO_VISIBLE_AL_USUARIO>",
    "work_notes": "<NOTAS_TECNICAS_INTERNAS>"
  }
  ```

---

## Catálogo de Identificadores Fijos para el Entorno

Para agilizar su parametrización en variables de entorno o archivos de configuración, les compartimos los valores técnicos validados:

| Variable / Parámetro | Valor Técnico | Descripción |
| :--- | :--- | :--- |
| `CATALOG_ITEM_SYS_ID` | `f0e2903c0f49310034dedd44e2050ec8` | Catálogo: Generic Request |
| `BUSINESS_SERVICE_SYS_ID` | `0f873c450f5802003e6c85ece1050e4f` | Servicio: Active Directory_MEX |
| `ASSIGNMENT_GROUP_SYS_ID` | `64bb9f64378fe200d8a8579543990eee` | Grupo: MX.MIS.EUS.MX.SN.PME.SD.LBU |
| `SOLICITANTE_TECNICO_SYS_ID` | `0e966fba838ff6d063a134326daad374` | Solicitante base (`vs_requestor`) |
| `MANAGER_FALLBACK_SYS_ID` | `d8423b640fd402003e6c85ece1050e1e` | Manager por defecto para auto-aprobación |
| `NIVEL_PRIORIDAD` | `"4"` | Prioridad 4 - Low |
| `CATEGORIA` | `"Active Directory"` | Campo `u_category` |
| `SUBCATEGORIA` | `"Reset Password"` | Campo `u_subcategory` |
