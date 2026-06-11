import re
import streamlit as st
from src.db import run_query_df, get_schema_context
from src.cortex import cortex_complete

SYSTEM_PROMPT = """You are an expert SQL analyst for a B2B SaaS company called Tundra.
You answer questions by writing PostgreSQL queries against the Tundra database.

SCHEMA:
{schema}

IMPORTANT ALLOWED VALUES (use ONLY these exact values in filters):
- subscriptions.status: 'active', 'trial', 'churned' (NOT 'cancelled')
- invoices.status: 'paid', 'pending', 'overdue'
- customers.industry: 'SaaS', 'Finance', 'Healthcare', 'Retail', 'Manufacturing', 'Media'
- plans.plan_name: 'Starter', 'Pro', 'Enterprise'
- usage_events.event_type: 'login', 'api_call', 'report_run', 'export'

JOIN KEYS:
- subscriptions.plan_id = plans.plan_id (NOT plans.id)
- subscriptions.customer_id = customers.customer_id
- customers.country_code = countries.country_code
- country_name lives ONLY on the countries table

RULES:
- Return SQL in a ```sql code block
- Use round((expr)::numeric, 2) for rounding (not round(double, int))
- Always parameterize user values, but for analytical queries use literals for allowed values
- For plans.features (TEXT[]), use: feature = ANY(p.features) or CROSS JOIN LATERAL unnest(p.features)

EXAMPLE:
Q: What is the total MRR by country?
```sql
SELECT co.country_name, round(sum(s.mrr)::numeric, 2) AS total_mrr
FROM subscriptions s
JOIN customers cu ON cu.customer_id = s.customer_id
JOIN countries co ON co.country_code = cu.country_code
WHERE s.status = 'active'
GROUP BY co.country_name
ORDER BY total_mrr DESC
LIMIT 20;
```
"""

WRITE_KEYWORDS = re.compile(r"\b(UPDATE|INSERT|DELETE|ALTER|DROP|TRUNCATE)\b", re.IGNORECASE)


def show():
    st.header("AI Agent")
    st.caption("Ask natural language questions about your SaaS data")

    schema_ctx = get_schema_context()

    # Model selector
    model = st.selectbox("Model", ["mistral-large2", "llama3.1-70b"], key="agent_model")

    # Initialize chat history
    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = []

    # Example buttons (rendered unconditionally)
    examples = [
        "What is the total MRR?",
        "How many churned customers are there?",
        "Top 5 countries by active MRR",
        "Average seats per plan",
    ]
    clicked_example = None
    cols = st.columns(len(examples))
    for i, ex in enumerate(examples):
        if cols[i].button(ex, key=f"agent_ex_{i}"):
            clicked_example = ex

    # Chat input
    question = st.chat_input("Ask about your data...") or clicked_example

    # Clear chat
    if st.button("Clear Chat", key="agent_clear"):
        st.session_state.agent_messages = []
        st.rerun()

    # Display history
    for msg in st.session_state.agent_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "dataframe" in msg:
                st.dataframe(msg["dataframe"], width="stretch")

    if question:
        st.session_state.agent_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        # Build prompt with history
        history = st.session_state.agent_messages[-6:]
        history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history)
        full_prompt = (
            SYSTEM_PROMPT.format(schema=schema_ctx)
            + "\n\nConversation:\n"
            + history_text
            + "\n\nassistant:"
        )

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = cortex_complete(full_prompt, model=model)
            st.markdown(response)

            # Extract and run SQL
            sql_blocks = re.findall(r"```sql\s*(.*?)```", response, re.DOTALL)
            msg_data = {"role": "assistant", "content": response}

            for sql in sql_blocks:
                sql = sql.strip()
                if WRITE_KEYWORDS.search(sql):
                    st.warning("This is a write query. Review before executing.")
                    if st.button("Confirm & Execute", key=f"confirm_{hash(sql)}"):
                        df = run_query_df(sql)
                        if df.empty:
                            st.info("Query executed but returned no rows.")
                        else:
                            st.dataframe(df, width="stretch")
                else:
                    try:
                        df = run_query_df(sql)
                        if df.empty:
                            st.info("Query returned no rows.")
                        else:
                            st.dataframe(df, width="stretch")
                            msg_data["dataframe"] = df
                    except Exception as e:
                        st.error(f"SQL Error: {e}")

            st.session_state.agent_messages.append(msg_data)
