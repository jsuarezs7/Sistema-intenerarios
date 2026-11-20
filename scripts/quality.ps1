# Ejecuta pruebas + cobertura de todos los modulos y publica el analisis en SonarQube local.
# Uso (desde la raiz del repo):  .\scripts\quality.ps1
# Requisitos: Docker Desktop abierto. Si hay Python con requirements-dev.txt + requirements de
# cada servicio se usa; si no, las pruebas se ejecutan dentro de Docker (o fuerzalo con -Docker).
# Panel: http://localhost:9000  (usuario admin / contrasena admin la primera vez)

param(
    [string]$Python = "python",
    [string]$SonarUrl = "http://localhost:9000",
    [string]$AdminUser = "admin",
    [string]$AdminPassword = "admin",
    [int]$MinCoverage = 90,
    [switch]$Docker,
    [switch]$SkipSonar
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (Test-Path ".venv\Scripts\python.exe") { $Python = (Resolve-Path ".venv\Scripts\python.exe").Path }

if (-not $Docker) {
    $hasPython = $false
    try { & $Python -c "import pytest, pytest_cov" 2>$null; $hasPython = ($LASTEXITCODE -eq 0) } catch { }
    if (-not $hasPython) {
        Write-Host "Python con pytest no disponible: las pruebas se ejecutaran en Docker." -ForegroundColor Yellow
        $Docker = $true
    }
}

$testImage = "sistema-itinerarios-tests"
if ($Docker) {
    Write-Host "Construyendo imagen de pruebas ($testImage)..."
    docker build -q -t $testImage -f infra/tests.Dockerfile . | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "No se pudo construir la imagen de pruebas." }
}

# Nombre -> carpeta, paquete medido y ruta de fuentes tal como la ve el scanner en su contenedor.
$modules = @(
    @{ Name = "airport-service";       Dir = "services/airport-service";       Cov = "app" },
    @{ Name = "itinerary-service";     Dir = "services/itinerary-service";     Cov = "app" },
    @{ Name = "api-gateway";           Dir = "services/api-gateway";           Cov = "app" },
    @{ Name = "notification-function"; Dir = "services/notification-function"; Cov = "app" },
    @{ Name = "report-function";       Dir = "services/report-function";       Cov = "app" },
    @{ Name = "shared";                Dir = "shared";                         Cov = "itinerary_shared" }
)
$summary = @()
$failed = $false

Write-Host "`n=== 1. Pruebas unitarias e integracion con cobertura ===" -ForegroundColor Cyan
foreach ($m in $modules) {
    Write-Host "`n--- $($m.Name)" -ForegroundColor Yellow
    $out = Join-Path $root "reports\$($m.Name)"
    New-Item -ItemType Directory -Force $out | Out-Null
    if ($Docker) {
        $r = "/src/reports/$($m.Name)"
        docker run --rm -v "${root}:/src" -w "/src/$($m.Dir)" $testImage `
            python -m pytest -q -p no:cacheprovider --cov=$($m.Cov) `
            --cov-config=/src/scripts/coverage-relative.ini `
            --cov-report=xml:"$r/coverage.xml" --cov-report=html:"$r/htmlcov" --cov-report=term `
            --junitxml="$r/test-results.xml"
    } else {
        Push-Location $m.Dir
        & $Python -m pytest -q -p no:cacheprovider --cov=$($m.Cov) `
            --cov-config="$root\scripts\coverage-relative.ini" `
            --cov-report=xml:"$out\coverage.xml" --cov-report=html:"$out\htmlcov" --cov-report=term `
            --junitxml="$out\test-results.xml"
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) { $failed = $true }
    $xmlPath = "$out\coverage.xml"
    (Get-Content $xmlPath -Raw) -replace "<source>[^<]*</source>", "<source>/usr/src/$($m.Dir)/$($m.Cov)</source>" |
        Set-Content $xmlPath -Encoding utf8
    [xml]$junit = Get-Content "$out\test-results.xml"
    [xml]$cov = Get-Content $xmlPath
    $suite = if ($junit.testsuites) { $junit.testsuites.testsuite } else { $junit.testsuite }
    $rate = [double]$cov.coverage.'line-rate'
    if ($rate * 100 -lt $MinCoverage) { $failed = $true }
    $summary += [pscustomobject]@{
        Modulo    = $m.Name
        Pruebas   = [int]$suite.tests
        Fallidas  = [int]$suite.failures + [int]$suite.errors
        Cobertura = "{0:P1}" -f $rate
    }
}

Write-Host "`n=== Resumen (minimo $MinCoverage%) ===" -ForegroundColor Cyan
$summary | Format-Table -AutoSize
Write-Host "Reportes HTML de cobertura: reports\<modulo>\htmlcov\index.html"
if ($failed) { Write-Host "Hay pruebas fallidas o cobertura por debajo del $MinCoverage%." -ForegroundColor Red }

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
$hide = foreach ($m in $modules) { "-v"; "/usr/src/$($m.Dir)/.pytest_cache" }
docker run --rm -e SONAR_HOST_URL="http://host.docker.internal:9000" -e SONAR_TOKEN="$token" `
    -v "${root}:/usr/src" @hide sonarsource/sonar-scanner-cli:11.1
$scanExit = $LASTEXITCODE

Invoke-RestMethod -Method Post -Headers @{ Authorization = $auth } `
    "$SonarUrl/api/user_tokens/revoke?name=$tokenName" | Out-Null

if ($scanExit -eq 0) {
    Write-Host "`nAnalisis publicado: $SonarUrl/dashboard?id=sistema-itinerarios" -ForegroundColor Green
}
exit ([int]$failed -bor [int]($scanExit -ne 0))
