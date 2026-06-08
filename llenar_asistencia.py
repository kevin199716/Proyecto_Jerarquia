#!/usr/bin/env python3
"""
llenar_asistencia.py
Script para llenar automáticamente la hoja "Asistencia" desde "colaboradores"
Uso: python llenar_asistencia.py
"""

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import os

# =====================================================
# CONFIGURACIÓN
# =====================================================

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
SPREADSHEET_ID = "1S61RQQXonoVfOl-skC0lksC_q0iNOh4yvAjHf2Qq2o"  # Cambia esto

# Archivo de credenciales (debe estar en el mismo directorio)
CREDENTIALS_FILE = "service_account.json"

# =====================================================
# FUNCIONES
# =====================================================

def autenticar():
    """Autentica con Google Sheets API"""
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client

def obtener_hoja(client, hoja_nombre):
    """Obtiene una hoja por nombre"""
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    try:
        return spreadsheet.worksheet(hoja_nombre)
    except:
        return None

def limpiar_texto(valor):
    """Limpia texto"""
    if pd.isna(valor):
        return ""
    s = str(valor).strip()
    return "" if s.upper() in ("NONE", "NAN", "NULL") else s

def llenar_asistencia():
    """Llena la hoja Asistencia desde colaboradores"""
    
    print("🔄 Autenticando...")
    client = autenticar()
    
    print("📖 Leyendo hoja 'colaboradores'...")
    hoja_colab = obtener_hoja(client, "colaboradores")
    if not hoja_colab:
        print("❌ No se encontró hoja 'colaboradores'")
        return
    
    # Leer datos
    datos_colab = hoja_colab.get_all_values()
    if not datos_colab:
        print("❌ Hoja 'colaboradores' vacía")
        return
    
    headers = [h.strip().upper() for h in datos_colab[0]]
    
    # Crear DataFrame
    df = pd.DataFrame(datos_colab[1:], columns=headers)
    
    print(f"📊 Encontrados {len(df)} colaboradores")
    
    print("🧹 Preparando hoja 'Asistencia'...")
    hoja_asist = obtener_hoja(client, "Asistencia")
    
    # Si existe, limpiar
    if hoja_asist:
        print("  ⚠️ Limpiando hoja existente...")
        hoja_asist.clear()
    else:
        print("  ✅ Creando hoja 'Asistencia'...")
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        hoja_asist = spreadsheet.add_worksheet("Asistencia", rows=len(df)+100, cols=50)
    
    # Crear encabezados
    print("📝 Escribiendo encabezados...")
    encabezados = [
        "RAZON SOCIAL",
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DISTRITO",
        "DNI",
        "NOMBRE",
        "ESTADO",
        "FECHA_ALTA",
        "FECHA_CESE",
        "MES",
        "PERIODO",
    ]
    
    # Agregar columnas de días
    for i in range(1, 32):
        encabezados.append(f"DIA_{i}")
    
    hoja_asist.append_row(encabezados, value_input_option="USER_ENTERED")
    
    # Llenar datos
    print("📥 Llenando datos de colaboradores...")
    periodo_actual = datetime.now().strftime("%Y-%m")
    
    filas_nuevas = []
    for idx, row in df.iterrows():
        fila = [
            limpiar_texto(row.get("RAZON SOCIAL", "")),
            limpiar_texto(row.get("SUPERVISOR A CARGO FINAL", "")),
            limpiar_texto(row.get("COORDINADOR FINAL", "")),
            limpiar_texto(row.get("DEPARTAMENTO", "")),
            limpiar_texto(row.get("PROVINCIA", "")),
            limpiar_texto(row.get("DISTRITO", "")),
            limpiar_texto(row.get("DNI", "")),
            limpiar_texto(row.get("NOMBRES", "")),
            limpiar_texto(row.get("ESTADO", "")),
            limpiar_texto(row.get("FECHA DE CREACION USUARIO", "")),
            limpiar_texto(row.get("FECHA DE CESE", "")),
            periodo_actual,
            periodo_actual,
        ]
        
        # Agregar 31 días vacíos
        for _ in range(31):
            fila.append("")
        
        filas_nuevas.append(fila)
        
        if (idx + 1) % 100 == 0:
            print(f"  ... {idx + 1}/{len(df)}")
    
    # Escribir en lotes de 100
    print("💾 Escribiendo en Google Sheets...")
    for i in range(0, len(filas_nuevas), 100):
        lote = filas_nuevas[i:i+100]
        hoja_asist.append_rows(lote, value_input_option="USER_ENTERED")
        print(f"  ✓ Escritas filas {i+1}-{min(i+100, len(filas_nuevas))}")
    
    print(f"\n✅ ¡LISTO! Hoja 'Asistencia' llena con {len(filas_nuevas)} registros")
    print(f"   Período: {periodo_actual}")
    print(f"   Columnas: Datos + DIA_1 a DIA_31 (vacíos para llenar)")

# =====================================================
# EJECUTAR
# =====================================================

if __name__ == "__main__":
    try:
        llenar_asistencia()
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("\nAsegúrate de:")
        print("1. Tener service_account.json en el mismo directorio")
        print("2. Que el SPREADSHEET_ID sea correcto")
        print("3. Tener conexión a Internet")
