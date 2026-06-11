import re
import streamlit as st
import plotly.express as px
from src.db import run_query_df, get_schema_context
from src.cortex import cortex_complete

SYSTEM_PROMPT = """You are an expert SQL analyst. Generate a PostgreSQL query that answers the user's business question.
Return ONLY a SQL query in a ```sql code block. The query must:
- Have a label/category column FIRST, then numeric column(s)
- LIMIT to 20 rows max
- Use round((expr)::numeric, 2) for rounding

SCHEMA:
{schema}

ALLOWED VALUES:
- subscriptions.status: 'active', 'trial', 'churned'
- invoices.status: 'paid', 'pending', 'overdue'
- customers.industry: 'SaaS', 'Finance', 'Healthcare', 'Retail', 'Manufacturing', 'Media'
- plans.plan_name: 'Starter', 'Pro', 'Enterprise'
- usage_events.event_type: 'login', 'api_call', 'report_run', 'export'

JOIN KEYS:
- subscriptions.plan_id = plans.plan_id
- subscriptions.customer_id = customers.customer_id
- customers.country_code = countries.country_code
- country_name is on the countries table only

EXAMPLE:
Q: MRR by country
```sql
SELECT co.country_name AS country, round(sum(s.mrr)::numeric, 2) AS total_mrr
FROM subscriptions s
JOIN customers cu ON cu.customer_id = s.customer_id
JOIN countries co ON co.country_code = cu.country_code
WHERE s.status = 'active'
GROUP BY co.country_name
ORDER BY total_mrr DESC
LIMIT 20;
```
"""

TEMPORAL_KEYWORDS = ["month", "year", "date", "week", "quarter", "day"]


def show():
    st.header("Charts on Demand")
    st.caption("Ask a business question and get an auto-generated chart")

    schema_ctx = get_schema_context()
    model = st.selectbox("Model", ["mistral-large2", "llama3.1-70b"], key="chart_model")

    # Example buttons
    examples = [
        "MRR by country",
        "Churn rate by plan",
        "New signups per month",
        "Top industries by customer count",
        "Active vs trial subscriptions",
    ]

    if "chart_question" not in st.session_state:
        st.session_state.chart_question = ""

    cols = st.columns(len(examples))
    for i, ex in enumerate(examples):
        if cols[i].button(ex, key=f"chart_ex_{i}"):
            st.session_state.chart_question = ex
            st.rerun()

    question = st.text_input("What would you like to visualize?", key="chart_question")

    if question:
        prompt = SYSTEM_PROMPT.format(schema=schema_ctx) + f"\n\nQ: {question}\n"
        with st.spinner("Generating chart..."):
            response = cortex_complete(prompt, model=model)

        sql_blocks = re.findall(r"```sql\s*(.*?)```", response, re.DOTALL)
        if not sql_blocks:
            st.error("Could not generate SQL. Try rephrasing your question.")
            st.code(response)
            return

        sql = sql_blocks[0].strip()
        st.code(sql, language="sql")

        try:
            df = run_query_df(sql)
        except Exception as e:
            st.error(f"SQL Error: {e}")
            return

        if df.empty:
            st.info("Query returned no rows.")
            return

        # Auto-detect chart type
        cols_list = df.columns.tolist()
        x_col = cols_list[0]
        y_col = cols_list[1] if len(cols_list) > 1 else cols_list[0]

        is_temporal = any(kw in x_col.lower() for kw in TEMPORAL_KEYWORDS)

        if is_temporal:
            fig = px.line(df, x=x_col, y=y_col, markers=True)
        else:
            fig = px.bar(df, x=x_col, y=y_col)

        fig.update_layout(margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, width="stretch")

        st.subheader("Raw Data")
        st.dataframe(df, width="stretch")
