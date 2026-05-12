import os

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text


def _connection_string() -> str:
    user = os.environ["PIPELINE_DB_USER"]
    password = os.environ["PIPELINE_DB_PASSWORD"]
    host = os.environ.get("PIPELINE_DB_HOST", "postgresql")
    port = os.environ.get("PIPELINE_DB_PORT", "5432")
    name = os.environ["PIPELINE_DB_NAME"]
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


@st.cache_resource
def _engine():
    return create_engine(_connection_string(), pool_pre_ping=True)


def query(sql: str, params: dict | None = None) -> pd.DataFrame:
    try:
        with _engine().connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})
    except Exception:
        return pd.DataFrame()
