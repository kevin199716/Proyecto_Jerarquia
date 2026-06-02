# Proyecto Jerarquía - Presencialidad conectada a PostgreSQL

## Qué cambia en esta versión

- El módulo **Presencialidad Dealer** ya no lee ni guarda asistencia en Google Sheets.
- Presencialidad lee colaboradores desde `sales.vw_colaboradores_presencialidad`.
- Presencialidad guarda marcas en `sales.asistencia_presencialidad`.
- Los sustentos de baja médica se registran en `sales.sustentos_bajas_medicas`.
- Alta/Bajas siguen usando Google Sheets hasta que se migren también a BD.
- La app ya no conecta Google Sheets al abrir si el usuario entra directo a Presencialidad.

## Archivos nuevos / modificados

- `db.py`: conexión a PostgreSQL usando variables de entorno.
- `asistencia.py`: versión SQL del módulo de presencialidad.
- `app_maestra_vendedores.py`: carga Google Sheets de forma lazy; Presencialidad usa SQL.
- `01_db_setup_presencialidad.sql`: vista, tablas e índices recomendados.

## Variables de entorno en Render

Agregar en el servicio web:

```text
DATABASE_URL=postgresql://usuario:clave@host:puerto/base
```

También puedes usar variables separadas:

```text
DB_HOST=host
DB_PORT=5432
DB_NAME=base
DB_USER=usuario
DB_PASSWORD=clave
```

Para subir sustentos A-BM con el uploader actual, mantener también las credenciales actuales de Google/Catbox según tu `sheets.py`.

## Requirements

Asegúrate de que `requirements.txt` tenga:

```text
sqlalchemy
psycopg2-binary
```

## SQL a ejecutar

Ejecutar el archivo:

```text
01_db_setup_presencialidad.sql
```

Ese archivo crea/actualiza:

- `sales.vw_colaboradores_presencialidad`
- `sales.asistencia_presencialidad`
- `sales.sustentos_bajas_medicas`
- índices para filtros y guardado rápido

## Flujo final

```text
ETL: Google Drive -> sales.ventas_unificada
App: sales.vw_colaboradores_presencialidad -> pantalla de presencialidad
App: Guardar Presencialidad -> sales.asistencia_presencialidad
App: A-BM -> storage externo + sales.sustentos_bajas_medicas
```
