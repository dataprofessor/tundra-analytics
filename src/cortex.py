import streamlit as st


def _get_snowpark_session():
    """Get a Snowpark session - works in both SiS and Community Cloud."""
    from snowflake.snowpark import Session

    # In SiS container runtime, use ambient session
    try:
        session = Session.builder.getOrCreate()
        return session
    except Exception:
        pass

    # Community Cloud / local: use explicit credentials from secrets
    creds = st.secrets["snowflake"]
    connection_params = {
        "account": creds["account"],
        "user": creds["user"],
        "warehouse": creds.get("warehouse", "COMPUTE_WH"),
    }
    if creds.get("role"):
        connection_params["role"] = creds["role"]
    # Auth: programmatic access token (OAuth/enterprise accounts) or password
    if creds.get("authenticator") == "PROGRAMMATIC_ACCESS_TOKEN":
        connection_params["authenticator"] = "PROGRAMMATIC_ACCESS_TOKEN"
        connection_params["token"] = creds["token"]
    elif creds.get("password"):
        connection_params["password"] = creds["password"]
    try:
        return Session.builder.configs(connection_params).create()
    except Exception as e:
        st.error(
            "Could not connect to Snowflake for Cortex AI. Check the "
            "[snowflake] section of your secrets (account, user, warehouse, "
            f"and either password or token) — it needs real, working "
            f"credentials.\n\nDetails: {e}"
        )
        st.stop()


def cortex_complete(prompt, model="mistral-large2"):
    """Call Snowflake Cortex COMPLETE for text generation."""
    session = _get_snowpark_session()
    prompt_escaped = prompt.replace("'", "''")
    sql = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', '{prompt_escaped}') AS response"
    result = session.sql(sql).collect()
    if result:
        return result[0]["RESPONSE"]
    return ""


def cortex_embed(text, model="snowflake-arctic-embed-l-v2.0"):
    """Generate embeddings using Snowflake Cortex EMBED_TEXT_1024."""
    session = _get_snowpark_session()
    text_escaped = text.replace("'", "''")
    sql = f"SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_1024('{model}', '{text_escaped}') AS embedding"
    result = session.sql(sql).collect()
    if result:
        embedding = result[0]["EMBEDDING"]
        # The connector may return the vector as a Python list already,
        # or as a JSON string depending on the driver version.
        if isinstance(embedding, str):
            import json
            return json.loads(embedding)
        return list(embedding)
    return []
