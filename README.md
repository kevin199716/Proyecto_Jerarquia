# Proyecto Jerarquía WOW

Archivos listos para subir a GitHub y desplegar en Render.

## Archivos principales
- `app_maestra_vendedores.py`: app principal Streamlit.
- `formulario.py`: módulo Alta optimizado, sin insertar/mover columnas para evitar límite de 10M de celdas.
- `asistencia.py`: Presencialidad Dealer con caché, estados, motivos y sustentos históricos.
- `registro_mod.py`: bajas y matriz con filtros rápidos.
- `sheets.py`: conexión Google Sheets/Drive.
- `auth.py`: login por `usuarios.json` local o secret `/etc/secrets/USUARIOS_CONTRASENAS` en Render.

## Importante para GitHub
No subir credenciales reales. Este paquete ignora:
- `credenciales.json`
- `usuarios.json`
- `.streamlit/secrets.toml`

Para local, copia `usuarios.json.example` como `usuarios.json` y cambia las claves.
Para Render, configura:
- `GOOGLE_CREDENTIALS` con el JSON de la cuenta de servicio.
- `USUARIOS_CONTRASENAS` como secret file si usas el flujo actual de `auth.py`.

## Orden de columnas
Revisa `ORDEN_COLUMNAS_COLABORADORES.txt` antes de probar altas nuevas.
