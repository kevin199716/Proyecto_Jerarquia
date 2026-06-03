# db.py
# FIX_DB_POSTGRES_POOL_RENDER_20260602
# Conexión centralizada a PostgreSQL para Proyecto_Jerarquia.

import os
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    """Crea un pool de conexión reutilizable. No abras conexiones por cada celda."""
    database_url = os.getenv("DATABASE_URL", "").strip()

    # Opción 1: DATABASE_URL directo: postgresql+psycopg2://user:pass@host:5432/db
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        return create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=3,
            max_overflow=5,
            future=True,
        )

    # Opción 2: variables separadas.
    host = os.getenv("DB_HOST", "").strip()
    port = os.getenv("DB_PORT", "5432").strip()
    name = os.getenv("DB_NAME", "").strip()
    user = os.getenv("DB_USER", "").strip()
    password = os.getenv("DB_PASSWORD", "").strip()

    if not all([host, name, user, password]):
        raise RuntimeError(
            "Faltan variables de conexión. Define DATABASE_URL o DB_HOST, DB_PORT, DB_NAME, DB_USER y DB_PASSWORD."
        )

    url = f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{name}"
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=3,
        max_overflow=5,
        future=True,
    )


def consultar_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def ejecutar(sql: str, params: dict | None = None) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


def ejecutar_many(sql: str, params_list: list[dict]) -> None:
    if not params_list:
        return
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(sql), params_list)
