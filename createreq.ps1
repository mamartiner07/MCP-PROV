param(
    [string]$UserEmail          = "dulce.mejia@provident.com.mx",
    [string]$ShortDescription   = "EVA | INICIO DE SESION | RESET DE CONTRASEÑA",
    [string]$Description        = "Usuario solicita reinicio de clave de red",
    [string]$Category           = "Active Directory",
    [string]$Subcategory        = "Reset Password",
    [string]$Priority           = "4", # 4 - Low
    [string]$AdditionalComments = "Hola, tu solicitud ha sido atendida y completada con éxito.",
    [string]$WorkNotes          = "Ticket gestionado y completado automáticamente por la integración.",
    [switch]$JsonOnly
)

# Si se indica -JsonOnly se silencian los mensajes informativos de Write-Host para dejar stdout limpio
if ($JsonOnly) {
    $InformationPreference = 'SilentlyContinue'
}

# ---------------------------------------------------------
# Configuración y Constantes Fijas
# ---------------------------------------------------------
$headers = @{
    "Authorization" = "Basic c3lzX3phYmJpeF9pbnRlZ3JhdGlvbjptPkozbjFBOzdhQjBpPHt9LSNNcFQ/ZHglOz42cEp9VmFOLWFpZExQ"
    "Accept"        = "application/json"
    "Content-Type"  = "application/json"
}

$baseUrl              = "https://ipfintest.service-now.com"
$catalogItemId        = "f0e2903c0f49310034dedd44e2050ec8" # Generic Request
$assignmentGroupSysId = "64bb9f64378fe200d8a8579543990eee" # MX.MIS.EUS.MX.SN.PME.SD.LBU
$businessServiceSysId = "0f873c450f5802003e6c85ece1050e4f" # Active Directory_MEX
$requestorSysId       = "0e966fba838ff6d063a134326daad374"
$defaultManagerSysId  = "d8423b640fd402003e6c85ece1050e1e" # Fallback si el usuario no tiene manager

# ---------------------------------------------------------
# Función Auxiliar para Ejecutar Llamadas HTTP y emitir JSON a stdout
# ---------------------------------------------------------
function Invoke-ApiCall {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Method,

        [Parameter(Mandatory = $true)]
        [string]$Uri,

        [Parameter(Mandatory = $false)]
        [hashtable]$Headers,

        [Parameter(Mandatory = $false)]
        [object]$Body = $null,

        [Parameter(Mandatory = $false)]
        [int]$Step = 0,

        [Parameter(Mandatory = $false)]
        [string]$Description = ""
    )

    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    
    $bodyToSend = $null
    $parsedBody = $null

    if ($null -ne $Body) {
        if ($Body -is [string]) {
            if (-not [string]::IsNullOrWhiteSpace($Body)) {
                $bodyToSend = $Body
                try {
                    $parsedBody = $Body | ConvertFrom-Json
                } catch {
                    $parsedBody = $Body
                }
            }
        } else {
            $parsedBody = $Body
            $bodyToSend = $Body | ConvertTo-Json -Depth 10
        }
    }

    $restParams = @{
        Uri     = $Uri
        Method  = $Method
        Headers = $Headers
    }
    if ($null -ne $bodyToSend) {
        $restParams["Body"] = $bodyToSend
    }

    $supportsStatusCode = (Get-Command Invoke-RestMethod).Parameters.ContainsKey('StatusCodeVariable')
    $statusCode = 200
    $responseObj = $null

    try {
        if ($supportsStatusCode) {
            $responseObj = Invoke-RestMethod @restParams -StatusCodeVariable httpCode
            if ($httpCode) {
                $statusCode = [int]$httpCode
            }
        } else {
            $responseObj = Invoke-RestMethod @restParams
            $statusCode = 200
        }
    } catch {
        $errorMessage = $_.Exception.Message
        $errorDetails = $null
        
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        } elseif ($_.Exception -and $_.Exception.StatusCode) {
            $statusCode = [int]$_.Exception.StatusCode
        } else {
            $statusCode = 500
        }

        if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
            try {
                $errorDetails = $_.ErrorDetails.Message | ConvertFrom-Json
            } catch {
                $errorDetails = $_.ErrorDetails.Message
            }
        }

        $responseObj = [ordered]@{
            error   = $errorMessage
            details = $errorDetails
        }

        # Imprimir JSON de la llamada a stdout aún en caso de error
        $logEntry = [ordered]@{
            timestamp   = $timestamp
            step        = $Step
            description = $Description
            method      = $Method.ToUpper()
            url         = $Uri
            status_code = $statusCode
            request     = [ordered]@{
                method  = $Method.ToUpper()
                url     = $Uri
                headers = $Headers
                body    = $parsedBody
            }
            response    = [ordered]@{
                status_code = $statusCode
                body        = $responseObj
            }
        }

        $jsonOutput = $logEntry | ConvertTo-Json -Depth 10
        [Console]::Out.WriteLine($jsonOutput)

        throw $_
    }

    # Imprimir a stdout el JSON con los detalles de la llamada HTTP y su respuesta
    $logEntry = [ordered]@{
        timestamp   = $timestamp
        step        = $Step
        description = $Description
        method      = $Method.ToUpper()
        url         = $Uri
        status_code = $statusCode
        request     = [ordered]@{
            method  = $Method.ToUpper()
            url     = $Uri
            headers = $Headers
            body    = $parsedBody
        }
        response    = [ordered]@{
            status_code = $statusCode
            body        = $responseObj
        }
    }

    $jsonOutput = $logEntry | ConvertTo-Json -Depth 10
    [Console]::Out.WriteLine($jsonOutput)

    return $responseObj
}

# ---------------------------------------------------------
# PETICIÓN 1: Buscar Usuario por Email (GET)
# ---------------------------------------------------------
Write-Host "`n>>> [1/5] Buscando usuario en ServiceNow ($UserEmail)..." -ForegroundColor Yellow
$userUrl = "$baseUrl/api/now/table/sys_user?sysparm_query=email=$UserEmail&sysparm_fields=sys_id,name,manager"
$userRes = Invoke-ApiCall -Method "Get" -Uri $userUrl -Headers $headers -Step 1 -Description "Buscar Usuario por Email (sys_user)"

if (-not $userRes.result -or $userRes.result.Count -eq 0) {
    Write-Host "ERROR: No se encontró usuario con el correo: $UserEmail" -ForegroundColor Red
    return
}

$userSysId    = $userRes.result[0].sys_id
$userName     = $userRes.result[0].name
$managerSysId = if ($userRes.result[0].manager -and $userRes.result[0].manager.value) { 
                    $userRes.result[0].manager.value 
                } else { 
                    $defaultManagerSysId 
                }

Write-Host "Usuario : $userName (sys_id: $userSysId)" -ForegroundColor Green
Write-Host "Manager : $managerSysId" -ForegroundColor Green

# ---------------------------------------------------------
# PETICIÓN 2: Crear el Ticket via Catalogo (POST)
# ---------------------------------------------------------
Write-Host "`n>>> [2/5] Creando solicitud en el catalogo (order_now)..." -ForegroundColor Yellow
$payload = @{
    "sysparm_quantity" = 1
    "variables" = @{
        "vs_requestor"              = $requestorSysId
        "vs_requested_for"          = $true
        "vs_requested_for_user"     = $userSysId
        "vs_requestor_manager"      = $managerSysId
        "u_business_service"        = $businessServiceSysId
        "generic_short_description" = $ShortDescription
        "generic_description"       = $Description
    }
} | ConvertTo-Json -Depth 5

$orderUrl = "$baseUrl/api/sn_sc/servicecatalog/items/$catalogItemId/order_now"
$orderRes = Invoke-ApiCall -Method "Post" -Uri $orderUrl -Headers $headers -Body $payload -Step 2 -Description "Crear Solicitud en Catalogo (order_now)"
$reqNumber = $orderRes.result.request_number
$reqSysId  = $orderRes.result.request_id

Write-Host "REQ Creado: $reqNumber (sys_id: $reqSysId)" -ForegroundColor Green

# ---------------------------------------------------------
# PETICIÓN 3: Obtener SCTASK y RITM en una sola consulta (GET)
# ---------------------------------------------------------
Write-Host "`n>>> [3/5] Obteniendo SCTASK y RITM generados..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

$taskUrl = "$baseUrl/api/now/table/sc_task?sysparm_query=request_item.request=$reqSysId&sysparm_fields=sys_id,number,request_item.number"
$taskRes = Invoke-ApiCall -Method "Get" -Uri $taskUrl -Headers $headers -Step 3 -Description "Consultar SCTASK y RITM generados (sc_task)"

if (-not $taskRes.result -or $taskRes.result.Count -eq 0) {
    Write-Host "ERROR: No se encontró SCTASK para el request $reqNumber." -ForegroundColor Red
    return
}

$taskSysId  = $taskRes.result[0].sys_id
$taskNumber = $taskRes.result[0].number
$ritmNumber = $taskRes.result[0].'request_item.number'

Write-Host "SCTASK: $taskNumber | RITM: $ritmNumber" -ForegroundColor Cyan

# ---------------------------------------------------------
# PETICIÓN 4: Asignar Grupo, Prioridad y Categorías (PATCH)
# ---------------------------------------------------------
Write-Host "`n>>> [4/5] Asignando Grupo, Prioridad y Categorias en la SCTASK..." -ForegroundColor Yellow
$assignBody = @{
    "assignment_group" = $assignmentGroupSysId
    "priority"         = $Priority
    "u_category"       = $Category
    "u_subcategory"    = $Subcategory
} | ConvertTo-Json

$assignUrl = "$baseUrl/api/now/table/sc_task/$taskSysId"
$assignRes = Invoke-ApiCall -Method "Patch" -Uri $assignUrl -Headers $headers -Body $assignBody -Step 4 -Description "Asignar Grupo, Prioridad y Categorias en SCTASK"
Write-Host "SCTASK $taskNumber configurada exitosamente" -ForegroundColor Green

# ---------------------------------------------------------
# PETICIÓN 5: Cerrar la SCTASK con Comentarios y Work Notes (PATCH)
# ---------------------------------------------------------
Write-Host "`n>>> [5/5] Pasando SCTASK a Closed Complete con notas..." -ForegroundColor Yellow
$closeBody = @{ 
    "state"      = "3" # Closed Complete
    "comments"   = $AdditionalComments
    "work_notes" = $WorkNotes
} | ConvertTo-Json

$closeUrl = "$baseUrl/api/now/table/sc_task/$taskSysId"
$closeRes = Invoke-ApiCall -Method "Patch" -Uri $closeUrl -Headers $headers -Body $closeBody -Step 5 -Description "Cerrar SCTASK con Comentarios y Work Notes"
Write-Host "SCTASK $taskNumber cerrada exitosamente (State: $($closeRes.result.state))" -ForegroundColor Green

# ---------------------------------------------------------
# Resumen Final
# ---------------------------------------------------------
Write-Host "`n========================================================" -ForegroundColor Magenta
Write-Host " FLUJO COMPLETADO EXITOSAMENTE (5 PETICIONES)" -ForegroundColor Magenta
Write-Host "========================================================" -ForegroundColor Magenta
Write-Host "REQ             : $reqNumber"
Write-Host "RITM            : $ritmNumber"
Write-Host "SCTASK          : $taskNumber"
Write-Host "Estado SCTASK   : Closed Complete (3)"
Write-Host "Usuario         : $userName ($UserEmail)"
Write-Host "Prioridad       : $Priority (Low)"
Write-Host "Grupo Asignado  : MX.MIS.EUS.MX.SN.PME.SD.LBU"
Write-Host "u_category      : $Category"
Write-Host "u_subcategory   : $Subcategory"
Write-Host "Comments        : $AdditionalComments"
Write-Host "Work Notes      : $WorkNotes"
Write-Host "========================================================`n" -ForegroundColor Magenta
