# Ejecuta pruebas + cobertura de todos los servicios y publica el analisis en SonarQube local.
# Uso (desde la raiz del repo):  .\scripts\quality.ps1
# Requisitos: Docker Desktop abierto y Python con requirements-dev.txt + requirements de cada servicio.
# Panel: http://localhost:9000  (usuario admin / contrasena admin la primera vez)

param(
    [string]$Python = "python",
    [string]$SonarUrl = "http://localhost:9000",
    [string]$AdminUser = "admin",
    [string]$AdminPassword = "admin",
    [switch]$SkipSonar
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (Test-Path ".venv\Scripts\python.exe") { $Python = (Resolve-Path ".venv\Scripts\python.exe").Path }

$services = @("airport-service", "itinerary-service", "api-gateway", "notification-function", "report-function")
$covConfig = Join-Path $root "scripts\coverage-relative.ini"
$summary = @()
$failed = $false

Write-Host "`n=== 1. Pruebas unitarias e integracion con cobertura ===" -ForegroundColor Cyan
foreach ($service in $services) {
    Push-Location "services\$service"
    Write-Host "`n--- $service" -ForegroundColor Yellow
    $out = Join-Path $root "reports\$service"
    New-Item -ItemType Directory -Force $out | Out-Null
    & $Python -m pytest -q -p no:cacheprovider --cov=app --cov-config="$covConfig" `
        --cov-report=xml:"$out\coverage.xml" --cov-report=html:"$out\htmlcov" --cov-report=term `
        --junitxml="$out\test-results.xml"
    if ($LASTEXITCODE -ne 0) { $failed = $true }
    # Ruta de fuentes tal como la ve el scanner dentro de su contenedor.
    $xmlPath = "$out\coverage.xml"
    (Get-Content $xmlPath -Raw) -replace "<source>[^<]*</source>", "<source>/usr/src/services/$service/app</source>" |
        Set-Content $xmlPath -Encoding utf8
    [xml]$junit = Get-Content "$out\test-results.xml"
    [xml]$cov = Get-Content "$out\coverage.xml"
    $suite = if ($junit.testsuites) { $junit.testsuites.testsuite } else { $junit.testsuite }
    $summary += [pscustomobject]@{
        Servicio  = $service
        Pruebas   = [int]$suite.tests
        Fallidas  = [int]$suite.failures + [int]$suite.errors
        Cobertura = "{0:P1}" -f [double]$cov.coverage.'line-rate'
    }
    Pop-Location
}

Write-Host "`n=== Resumen ===" -ForegroundColor Cyan
$summary | Format-Table -AutoSize
Write-Host "Reportes HTML de cobertura: reports\<servicio>\htmlcov\index.html"
if ($failed) { Write-Host "Hay pruebas fallidas." -ForegroundColor Red }

if ($SkipSonar) { exit [int]$failed }

Write-Host "`n=== 2. SonarQube ===" -ForegroundColor Cyan
docker compose -f infra/docker-compose.sonar.yml up -d | Out-Null
Write-Host "Esperando a que SonarQube este listo (la primera vez tarda 1-2 minutos)..."
$auth = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${AdminUser}:${AdminPassword}"))
do {
    Start-Sleep -Seconds 5
    try { $status = (Invoke-RestMethod "$SonarUrl/api/system/status").status } catch { $status = "STARTING" }
} while ($status -ne "UP")

$tokenName = "local-scan-" + (Get-Date -Format "yyyyMMddHHmmss")
try {
    $token = (Invoke-RestMethod -Method Post -Headers @{ Authorization = $auth } `
        "$SonarUrl/api/user_tokens/generate?name=$tokenName").token
} catch {
    Write-Host "No se pudo crear el token. Si cambiaste la contrasena de admin, ejecuta:" -ForegroundColor Red
    Write-Host "  .\scripts\quality.ps1 -AdminPassword <tu_contrasena>" -ForegroundColor Red
    exit 1
}

# Los .pytest_cache creados desde contenedores pueden quedar sin permisos en Windows;
# se ocultan con volumenes vacios para que el scanner pueda recorrer cada modulo.
$hide = foreach ($service in $services) { "-v"; "/usr/src/services/$service/.pytest_cache" }
docker run --rm -e SONAR_HOST_URL="http://host.docker.internal:9000" -e SONAR_TOKEN="$token" `
    -v "${root}:/usr/src" @hide sonarsource/sonar-scanner-cli:11.1
$scanExit = $LASTEXITCODE

Invoke-RestMethod -Method Post -Headers @{ Authorization = $auth } `
    "$SonarUrl/api/user_tokens/revoke?name=$tokenName" | Out-Null

if ($scanExit -eq 0) {
    Write-Host "`nAnalisis publicado: $SonarUrl/dashboard?id=sistema-itinerarios" -ForegroundColor Green
}
exit ([int]$failed -bor [int]($scanExit -ne 0))
