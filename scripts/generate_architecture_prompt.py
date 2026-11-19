"""Generate a source-grounded prompt for an architecture diagram assistant."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    ".coverage",
}
INCLUDED_DIRS = {"docs", "services", "shared", "infra", "frontend", ".github", "scripts"}
ROOT_FILES = {
    ".dockerignore",
    ".env.example",
    "README.md",
    "pyproject.toml",
    "render.yaml",
    "docker-compose.yml",
}
TEXT_EXTENSIONS = {
    ".cfg",
    ".conf",
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".ts",
    ".txt",
    ".yml",
    ".yaml",
}
SECRET_PATTERNS = (
    re.compile(r"(?im)^(\s*(?:[A-Z][A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|KEY)[A-Z0-9_]*)\s*=).*$"),
    re.compile(r"(?i)(password|secret|token|private[_-]?key)\s*[:=]\s*[^,\s]+"),
)


def files_to_collect(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in root.iterdir():
        if path.name in ROOT_FILES and path.is_file():
            candidates.append(path)
        if path.is_dir() and path.name in INCLUDED_DIRS:
            for child in path.rglob("*"):
                if child.is_file() and child.suffix.lower() in TEXT_EXTENSIONS:
                    if not any(part in EXCLUDED_DIRS for part in child.relative_to(root).parts):
                        candidates.append(child)
    return sorted(set(candidates), key=lambda path: path.relative_to(root).as_posix())


def redact(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)} [REDACTED]", text)
    return text


def classify(path: Path) -> str:
    relative = path.as_posix()
    if relative.startswith(".github/"):
        return "CI/CD"
    if relative.startswith("docs/"):
        return "Documentación y contratos"
    if relative.startswith("infra/") or path.name.endswith("compose.yml"):
        return "Infraestructura y despliegue"
    if relative.startswith("frontend/"):
        return "Frontend"
    if relative.startswith("shared/"):
        return "Contratos y librería compartida"
    if relative.startswith("services/"):
        return "Microservicios"
    return "Configuración y utilidades"


def build_prompt(root: Path, max_file_bytes: int) -> str:
    sections: dict[str, list[str]] = {}
    skipped: list[str] = []
    for path in files_to_collect(root):
        relative = path.relative_to(root).as_posix()
        try:
            if path.stat().st_size > max_file_bytes:
                skipped.append(f"{relative} (supera {max_file_bytes} bytes)")
                continue
            content = redact(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            skipped.append(f"{relative} ({exc})")
            continue
        sections.setdefault(classify(path), []).append(
            f"### `{relative}`\n\n```{path.suffix.lstrip('.')}\n{content.rstrip()}\n```"
        )

    inventory = "\n".join(
        f"- `{path.relative_to(root).as_posix()}` ({classify(path)})"
        for path in files_to_collect(root)
    )
    skipped_text = "\n".join(f"- {item}" for item in skipped) or "- Ninguno"
    evidence = "\n\n".join(
        f"## {category}\n\n" + "\n\n".join(items) for category, items in sections.items()
    )
    return f"""# Prompt para diagrama de arquitectura: Sistema de Itinerarios

Actúa como arquitecto de software senior. Construye una representación fiel de este
repositorio. El código y los documentos adjuntos son la fuente de verdad: no inventes
componentes, puertos, protocolos, bases de datos, relaciones ni flujos que no estén
respaldados por la evidencia. Si encuentras una contradicción, repórtala en una sección
de discrepancias indicando archivo y línea aproximada.

## Objetivo

Genera un documento de arquitectura en español con estos diagramas Mermaid:

1. **Contexto**: usuario, frontend, gateway y dependencias externas.
2. **Contenedores/despliegue**: cada microservicio, frontend, PostgreSQL, Redis,
   RabbitMQ, Jaeger, volúmenes, red y puertos publicados.
3. **Componentes por microservicio**: domain, application, infrastructure y api,
   mostrando puertos/adaptadores y la regla de que domain no depende de infrastructure.
4. **Flujo síncrono HTTP**: login y una operación principal completa, incluyendo
   gateway, servicios internos, autenticación y propagación del JWT.
5. **Flujo asíncrono**: creación de itinerario, transacción/outbox, worker,
   exchange/routing key/queue, consumidor, ACK, idempotencia y dead-letter queue.
6. **Persistencia y caché**: qué servicio accede a cada base de datos o Redis.
7. **Observabilidad**: spans, correlation ID, W3C trace context, OTLP y Jaeger.
8. **CI/CD**: pull request, pruebas, lint, Sonar, build de imágenes, GHCR y
   despliegue SSH con Docker Compose.

Para cada flecha indica protocolo, dirección y propósito. Diferencia líneas síncronas
HTTP de eventos RabbitMQ. Incluye una leyenda. Después de cada diagrama agrega una
explicación breve y una tabla de evidencia con `archivo:línea o símbolo`.

## Reglas de precisión

- Usa los nombres exactos del código para servicios, clases, exchanges, queues y rutas.
- Marca como `simulado`, `conceptual` o `no implementado` todo lo que los documentos
  indiquen que no es real (por ejemplo, envío de notificaciones o FaaS).
- No muestres valores secretos; conserva solamente nombres de variables de entorno.
- No confundas puertos internos de Docker con puertos publicados al host.
- Incluye advertencias sobre healthchecks que solo verifican vida y sobre entrega
  RabbitMQ al menos una vez cuando estén respaldadas por la documentación.
- Si un archivo generado o una configuración reciente contradice la documentación,
  muestra ambas versiones y explica cuál parece ser la configuración activa.

## Inventario de archivos analizados

{inventory}

## Archivos omitidos

{skipped_text}

## Evidencia completa del repositorio

{evidence}

## Formato final obligatorio

Entrega, en este orden:
1. Resumen ejecutivo.
2. Supuestos y discrepancias.
3. Los ocho diagramas Mermaid solicitados.
4. Flujos narrados paso a paso.
5. Tabla de componentes y responsabilidades.
6. Tabla de endpoints, eventos y dependencias.
7. Riesgos o límites arquitectónicos observados, sin proponer cambios no solicitados.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("architecture_prompt.md"),
        help="Archivo de salida. Se resuelve relativo al directorio actual.",
    )
    parser.add_argument("--max-file-bytes", type=int, default=250_000)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_prompt(root, args.max_file_bytes), encoding="utf-8")
    print(f"Prompt generado: {output}")


if __name__ == "__main__":
    main()
