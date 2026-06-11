import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd


@st.cache_resource
def get_connection():
    """Get a Postgres connection with auto-reconnect."""
    creds = st.secrets["postgres"]
    conn = psycopg2.connect(
        host=creds["host"],
        port=creds["port"],
        dbname=creds["dbname"],
        user=creds["user"],
        password=creds["password"],
        sslmode="require",
    )
    conn.autocommit = True
    return conn


def _ensure_connection():
    """Ensure the connection is alive, reconnect if needed."""
    conn = get_connection()
    try:
        conn.cursor().execute("SELECT 1")
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        st.cache_resource.clear()
        conn = get_connection()
    return conn


def run_query(sql, params=None):
    """Run a query and return results as list of dicts."""
    conn = _ensure_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        if cur.description:
            return cur.fetchall()
        return []


def run_query_df(sql, params=None):
    """Run a query and return results as a DataFrame."""
    conn = _ensure_connection()
    return pd.read_sql(sql, conn, params=params)


def get_tables():
    """Get list of tables in public schema."""
    sql = """
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    ORDER BY table_name;
    """
    rows = run_query(sql)
    return [r["table_name"] for r in rows]


def get_schema_context():
    """Build a text description of all tables/columns for LLM prompts."""
    sql = """
    SELECT table_name, column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position;
    """
    rows = run_query(sql)
    context_parts = []
    current_table = None
    for row in rows:
        if row["table_name"] != current_table:
            current_table = row["table_name"]
            context_parts.append(f"\nTable: {current_table}")
        nullable = "NULL" if row["is_nullable"] == "YES" else "NOT NULL"
        context_parts.append(
            f"  - {row['column_name']} ({row['data_type']}, {nullable})"
        )
    return "\n".join(context_parts)
