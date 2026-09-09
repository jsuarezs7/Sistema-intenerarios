# Verificación local

Fecha: 9 de septiembre de 2026. Rama: `Develop`. Entorno de pruebas: Windows, Python 3.14.7. Las imágenes usan Python 3.12 y CI está configurado para 3.11/3.12.

| Servicio | Pruebas aprobadas | Cobertura |
| --- | ---: | ---: |
| Airport Service | 16 | 93 % |
| API Gateway | 5 | 93 % |
| Itinerary Service | 10 | 90 % |
| Notification Function | 5 | 87 % |
| Report Function | 4 | 90 % |
| Total | 40 | — |

También aprobados:

- Ruff y formato de los archivos Python.
- Compatibilidad de dependencias mediante `pip check`.
- Alembic upgrade → downgrade → upgrade para las dos bases, sobre SQLite temporal.
- Validación de esquema/ejemplo AsyncAPI y referencias locales del Blueprint.
- Validación de Compose principal y override de pruebas.
- `node --check frontend/app.js`.
- Consulta real a API Colombia para verificar el formato y la inversión de coordenadas.

Docker verificado: todas las imágenes se construyeron y los servicios quedaron en ejecución. Las migraciones finalizaron correctamente sobre PostgreSQL 17. La prueba `scripts/smoke.py` pasó tanto con el catálogo de prueba como con API Colombia real: login, aeropuertos, CRUD, reporte, outbox confirmado y notificación persistida. Se retiró el contenedor temporal del catálogo y se dejó el entorno principal funcionando en http://localhost:8000. Jaeger recibió trazas de los seis procesos instrumentados y el frontend respondió HTTP 200.

La herramienta del navegador no pudo conectarse por un error de su entorno. No se afirma verificación visual ni ejecución de las interacciones JavaScript en un navegador.

No se realizó despliegue en Render ni ejecución de GitHub Actions. Los hooks requieren secrets del repositorio y el Blueprint requiere configurar el broker/exportador externos.
