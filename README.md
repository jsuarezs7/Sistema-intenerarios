# Sistema de Itinerarios Personales

Proyecto universitario de Arquitectura de Software Emergente: FastAPI, microservicios, eventos y funciones serverless simuladas. Desarrollo en la rama `Develop`.

## Ejecutar

Con Python 3.11+ y Docker Desktop/Engine en ejecución, desde la raíz:

```sh
python scripts/init_env.py
docker compose --env-file .env -f infra/docker-compose.yml up --build -d
```

Abre **http://localhost:8000**. El usuario y la contraseña estén en `DEMO_USERNAME` y `DEMO_PASSWORD` del archivo local `.env`, creado con secretos aleatorios.

- [Guía de arquitectura, ejecución, pruebas y Render](docs/README.md)
- [Resultados y límites de verificación local](docs/VERIFICATION.md)
- [Contrato AsyncAPI](docs/asyncapi.yaml)
- Swagger del gateway: http://localhost:8000/docs
- Jaeger: http://localhost:16686

Los comandos no publican el proyecto ni despliegan recursos en Render.
