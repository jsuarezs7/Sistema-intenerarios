# Sistema de Itinerarios Personales

Proyecto universitario de Arquitectura de Software Emergente: FastAPI, microservicios, eventos y funciones serverless simuladas. Desarrollo en la rama `develop`.

## Ejecutar

Con Python 3.11+ y Docker Desktop/Engine en ejecución, desde la raíz:

```sh
python scripts/init_env.py
docker compose --env-file .env up --build -d
```

Abre **http://localhost:8000**. El usuario y la contraseña estén en `DEMO_USERNAME` y `DEMO_PASSWORD` del archivo local `.env`, creado con secretos aleatorios.

- [Guía de arquitectura, ejecución, pruebas y Render](docs/README.md)
- [Resultados y límites de verificación local](docs/VERIFICATION.md)
- [Contrato AsyncAPI](docs/asyncapi.yaml)
- Swagger del gateway: http://localhost:8000/docs
- Jaeger: http://localhost:16686
- Frontend: http://localhost:8080
- RabbitMQ management: http://localhost:15672
- k6: `k6 run load/k6.js`
- Prompt completo para Claude/ChatGPT: `python scripts/generate_architecture_prompt.py --output architecture_prompt.md`
- Registro: nombre, usuario, correo, teléfono y contraseña desde la pestaña **Crear cuenta**.
- Las confirmaciones SMS locales se simulan en los logs de `notification-function`; no se
  envía ningún mensaje externo.

Cada servicio y el frontend incluye un `Dockerfile` y un `docker-compose.yml`
independiente. Los servicios HTTP exponen Swagger en `/docs` y OpenAPI en
`/openapi.json`. El itinerario se publica mediante el outbox y el adaptador
`RabbitMQEventPublisher`; la función de notificaciones consume ese evento.
Las variables requeridas para CI/CD son `SONAR_TOKEN`, `SONAR_HOST_URL`,
`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` y `DEPLOY_PATH` en GitHub Secrets.

Los comandos no publican el proyecto ni despliegan recursos en Render.
