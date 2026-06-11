import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd


@st.cache_resource
def get_connection():
    pg = st.secrets["postgres"]
    conn = psycopg2.connect(
        host=pg["host"],
        port=pg["port"],
        dbname=pg["dbname"],
        user=pg["user"],
        password=pg["password"],
        sslmode="require",
    )
    conn.autocommit = True
    return conn


def _ensure_conn():
    conn = get_connection()
    try:
        conn.cursor().execute("SELECT 1")
    except Exception:
        get_connection.clear()
        conn = get_connection()
    return conn


def run_query(sql, params=None):
    conn = _ensure_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def run_query_df(sql, params=None):
    rows = run_query(sql, params)
    return pd.DataFrame(rows)


def get_tables():
    sql = """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """
    return [r["table_name"] for r in run_query(sql)]


def get_schema_context():
    sql = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """
    rows = run_query(sql)
    lines = []
    current_table = None
    for r in rows:
        if r["table_name"] != current_table:
            current_table = r["table_name"]
            lines.append(f"\nTable: {current_table}")
        lines.append(f"  - {r['column_name']} ({r['data_type']})")
    return "\n".join(lines)
