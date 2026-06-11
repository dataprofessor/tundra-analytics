import json
import streamlit as st
from snowflake.snowpark import Session


@st.cache_resource
def get_snowpark_session():
    try:
        return Session.builder.getOrCreate()
    except Exception:
        pass
    sf = st.secrets.get("snowflake", {})
    if not sf:
        st.error("Missing [snowflake] section in secrets.toml. Add account, user, and auth credentials.")
        st.stop()
    configs = {
        "account": sf["account"],
        "user": sf["user"],
        "warehouse": sf.get("warehouse", "CHANIN_XS"),
    }
    if sf.get("role"):
        configs["role"] = sf["role"]
    if sf.get("authenticator") == "PROGRAMMATIC_ACCESS_TOKEN":
        configs["authenticator"] = "PROGRAMMATIC_ACCESS_TOKEN"
        configs["token"] = sf["token"]
    elif sf.get("password"):
        configs["password"] = sf["password"]
    else:
        st.error("No valid auth method in [snowflake] secrets. Provide password or token.")
        st.stop()
    try:
        return Session.builder.configs(configs).create()
    except Exception as e:
        st.error(f"Failed to connect to Snowflake: {e}. Check [snowflake] in secrets.toml.")
        st.stop()


def cortex_complete(prompt, model="mistral-large2"):
    session = get_snowpark_session()
    prompt_escaped = prompt.replace("\\", "\\\\").replace("'", "\\'")
    sql = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', '{prompt_escaped}') AS response"
    result = session.sql(sql).collect()
    return result[0]["RESPONSE"]


def cortex_embed(text, model="snowflake-arctic-embed-l-v2.0"):
    session = get_snowpark_session()
    text_escaped = text.replace("\\", "\\\\").replace("'", "\\'")
    sql = f"SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_1024('{model}', '{text_escaped}') AS embedding"
    result = session.sql(sql).collect()
    embedding = result[0]["EMBEDDING"]
    if isinstance(embedding, str):
        return json.loads(embedding)
    return embedding
