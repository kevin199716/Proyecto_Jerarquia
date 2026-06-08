# WAP VENTAS DOOR TO DOOR - Portal de Gestión de Vendedores

**v2.5.0** | Portal web Streamlit para gestión de fuerza de ventas D2D en Perú

## 📋 Descripción

Portal de gestión de vendedores con:
- ✅ **Módulo Alta** - Registro de nuevos vendedores
- ✅ **Módulo Bajas** - Baja de vendedores
- ✅ **Módulo Presencialidad Dealer** - Gestión de descansos médicos y vacaciones

Backend: Python + Google Sheets | Deploy: VPS Linux + Systemctl

---

## 🚀 Instalación LOCAL

### Requisitos
- Python 3.10+
- pip3
- Git

### Pasos

```bash
# 1. Clonar repositorio
git clone https://github.com/kevin199716/Proyecto_Jerarquia.git
cd Proyecto_Jerarquia

# 2. Crear virtual environment
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Crear carpeta de secrets (si no existe)
mkdir -p ~/.streamlit

# 5. Agregar credenciales
# Copiar credenciales.json a la carpeta del proyecto

# 6. Crear usuarios.json
# Copiar usuarios.json con estructura:
{
  "admin": {
    "password": "tu_contraseña",
    "rol": "backoffice",
    "razon": "",
    "estado": "activo"
  }
}

# 7. Ejecutar
streamlit run app_maestra_vendedores.py
```

---

## 🖥️ Deploy en VPS Linux

### Estructura en VPS
```
/opt/Proyecto_Jerarquia/
├── app_maestra_vendedores.py
├── auth.py
├── asistencia.py
├── formulario.py
├── registro_mod.py
├── sheets.py
├── ui_inicio.py
├── wow_theme.py
├── usuarios.json
├── requirements.txt
├── credenciales.json
└── venv/
```

### Instalación en VPS

```bash
# 1. Conectar a VPS
ssh root@tu_vps

# 2. Descargar proyecto
cd /opt
git clone https://github.com/kevin199716/Proyecto_Jerarquia.git
cd Proyecto_Jerarquia

# 3. Crear virtual environment
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

# 4. Agregar credenciales
# Copiar credenciales.json a /opt/Proyecto_Jerarquia/

# 5. Crear usuario systemd
sudo nano /etc/systemd/system/proyecto_jerarquia.service
```

### Contenido de `proyecto_jerarquia.service`

```ini
[Unit]
Description=Streamlit Proyecto Jerarquia
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/Proyecto_Jerarquia
ExecStart=/opt/Proyecto_Jerarquia/venv/bin/python -m streamlit run app_maestra_vendedores.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Activar servicio

```bash
# Recargar configuración
sudo systemctl daemon-reload

# Habilitar servicio
sudo systemctl enable proyecto_jerarquia

# Iniciar servicio
sudo systemctl start proyecto_jerarquia

# Ver estado
sudo systemctl status proyecto_jerarquia

# Ver logs
sudo journalctl -u proyecto_jerarquia -f
```

---

## 🔄 Actualizar código en VPS

```bash
ssh root@tu_vps

cd /opt/Proyecto_Jerarquia

# Descartar cambios locales
git checkout .

# Traer nuevos cambios
git pull origin main

# Reiniciar servicio
systemctl restart proyecto_jerarquia

# Verificar
systemctl status proyecto_jerarquia
```

---

## 📊 Google Sheets - Configuración

### Spreadsheet ID
```
1S61RQQXonoVfOl-skC0lksC_q0iNOh44yvAjHf2Qq2o
```

### Hojas requeridas
1. **colaboradores** - Datos de vendedores
2. **ubicaciones** - Localizaciones (DEPARTAMENTO, PROVINCIA, DISTRITO)
3. **Asistencia** - Registro de descansos médicos y vacaciones

---

## 🔐 Variables de Sesión

- `autenticado` - Boolean de login
- `usuario` - Nombre de usuario
- `rol` - Rol del usuario (backoffice, dealer, presencialidad, editor)
- `razon` - Razón social del dealer

---

## 📝 Estructura de usuarios.json

```json
{
  "admin": {
    "password": "contraseña",
    "rol": "backoffice",
    "razon": "RAZÓN SOCIAL",
    "estado": "activo"
  },
  "vendedor": {
    "password": "contraseña",
    "rol": "dealer",
    "razon": "EMPRESA DEL DEALER",
    "estado": "activo"
  }
}
```

---

## ⚠️ Troubleshooting

### Servicio no inicia
```bash
# Ver error
journalctl -u proyecto_jerarquia -n 50

# Si falta venv
cd /opt/Proyecto_Jerarquia
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# Reintentar
systemctl restart proyecto_jerarquia
```

### Google Sheets sin conexión
- Verificar `credenciales.json` en la carpeta
- Verificar permisos en Google Cloud
- Reintentar autenticación

---

## 📞 Soporte

**Email**: ksa@wowperu.pe  
**Repositorio**: https://github.com/kevin199716/Proyecto_Jerarquia

---

## 📄 Licencia

Privado - WAP Perú 2026
