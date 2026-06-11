import streamlit as st
import re
from src.db import run_query_df, get_connection, get_schema_context
from src.cortex import cortex_complete


SYSTEM_PROMPT = """You are a helpful data analyst assistant for a B2B SaaS company called Tundra.
You have access to a Postgres database with the following schema:

{schema}

Important notes:
- subscription_period is a TSTZRANGE column (Postgres range type)
- features on plans is a TEXT[] array, join with: feature = ANY(p.features) or use unnest
- metadata on usage_events is JSONB
- country_code is ISO-3166 alpha-3 (3 chars, e.g. USA, GBR, DEU)
- subscriptions.status values are EXACTLY 'active', 'trial', 'churned'.
  There is NO 'cancelled' value — for churn use status = 'churned'.
  Churn rate = count(status='churned') / count(*).
- plans primary key is plan_id (NOT id); the name column is plan_name
  (NOT name); join subscriptions with s.plan_id = p.plan_id.
- country_name lives ONLY on the countries table; customers has just
  country_code. Join customers.country_code = countries.country_code
  to show a country name.
- Use standard PostgreSQL syntax

When asked a question, write a SQL query to answer it. Return the SQL in a ```sql code block.
If the question doesn't require SQL, just answer directly.
"""


WRITE_KEYWORDS = re.compile(
    r"\b(UPDATE|INSERT|DELETE|ALTER|DROP|TRUNCATE)\b", re.IGNORECASE
)

EXAMPLE_QUESTIONS = [
    "What is the total MRR?",
    "How many churned customers are there?",
    "Top 5 countries by active MRR",
    "Average seats per plan",
]


def show():
    st.header("AI Agent")

    # Model selector
    model = st.selectbox("Model", ["mistral-large2", "llama3.1-70b"], key="ai_model")

    # Initialize conversation
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []

    # Clear chat button
    if st.button("Clear Chat"):
        st.session_state.ai_messages = []
        st.rerun()

    # Display conversation history
    for msg in st.session_state.ai_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "dataframe" in msg:
                st.dataframe(msg["dataframe"])

    # Example question buttons (always available as quick prompts).
    # Render unconditionally: if they only showed while the conversation
    # was empty, a click after the first exchange would hit a widget that
    # is no longer created that run, and nothing would happen.
    example_click = None
    st.caption("Example questions:")
    cols = st.columns(len(EXAMPLE_QUESTIONS))
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        if cols[i].button(q, key=f"ai_example_{i}"):
            example_click = q

    # User input (typed in the chat box or chosen from an example button)
    user_input = st.chat_input("Ask about your data...") or example_click
    if user_input:
        st.session_state.ai_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Build prompt with schema and conversation history
        schema = get_schema_context()
        system = SYSTEM_PROMPT.format(schema=schema)

        # Include last 6 messages for context
        history = st.session_state.ai_messages[-6:]
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in history
        )
        full_prompt = f"{system}\n\nConversation:\n{history_text}\n\nASSISTANT:"

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = cortex_complete(full_prompt, model=model)

            st.markdown(response)

            # Check for SQL blocks
            sql_blocks = re.findall(r"```sql\s*(.*?)\s*```", response, re.DOTALL)

            msg_data = {"role": "assistant", "content": response}

            for sql in sql_blocks:
                sql = sql.strip()
                if WRITE_KEYWORDS.search(sql):
                    st.warning("⚠️ This query modifies data:")
                    st.code(sql, language="sql")
                    if st.button("Confirm & Execute", key=f"confirm_{hash(sql)}"):
                        try:
                            df = run_query_df(sql)
                            st.dataframe(df)
                            msg_data["dataframe"] = df
                        except Exception as e:
                            st.error(f"Error: {e}")
                else:
                    try:
                        df = run_query_df(sql)
                        if df.empty:
                            st.info("Query ran successfully but returned no rows.")
                        else:
                            st.dataframe(df)
                            msg_data["dataframe"] = df
                    except Exception as e:
                        st.error(f"Error executing SQL: {e}")

            st.session_state.ai_messages.append(msg_data)
