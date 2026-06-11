import streamlit as st
import plotly.express as px
from src.db import run_query_df, get_schema_context
from src.cortex import cortex_complete


CHART_SYSTEM_PROMPT = """You are a SQL expert for a PostgreSQL database.
Given a business question, return ONLY a SQL query in a ```sql code block.
The query must:
- Have a label column first (text) and one or more numeric columns
- Be limited to 20 rows max
- Use standard PostgreSQL syntax
- Use ONLY the tables and columns in the schema below. Do NOT invent
  column names; use the exact names shown.

Schema:
{schema}

Important values and join keys:
- subscriptions.status values are exactly 'active', 'trial', 'churned'
  (there is NO 'cancelled' value)
- plans primary key is plan_id (NOT id); the plan name column is
  plan_name (NOT name); join with s.plan_id = p.plan_id
- plans.features is a TEXT[] array; use feature = ANY(p.features) or
  unnest(p.features)
- country_code is ISO-3 alpha-3; usage_events.metadata is JSONB;
  subscription_period is TSTZRANGE
- country_name lives ONLY on the countries table. customers has just
  country_code, so to show a country name join
  customers.country_code = countries.country_code and select
  countries.country_name.

Worked example — question "MRR by country":
```sql
SELECT co.country_name AS label, SUM(s.mrr) AS mrr
FROM subscriptions s
JOIN customers c ON s.customer_id = c.customer_id
JOIN countries co ON c.country_code = co.country_code
WHERE s.status = 'active'
GROUP BY co.country_name
ORDER BY mrr DESC
LIMIT 20;
```

Do NOT include any explanation, just the SQL in a ```sql block."""


@st.cache_data(ttl=600)
def _schema():
    return get_schema_context()


EXAMPLE_QUESTIONS = [
    "MRR by country",
    "Churn rate by plan",
    "New signups per month",
    "Top industries by customer count",
    "Active vs trial subscriptions",
]


def show():
    st.header("Charts on Demand")
    st.caption("Ask a business question and get an auto-generated chart.")

    # Example question buttons. Write to the text_input's OWN session_state
    # key, then st.rerun() so the input and chart reflect the click on the
    # same interaction (without the rerun the update lags by one run and the
    # click appears to do nothing until the page is revisited).
    cols = st.columns(len(EXAMPLE_QUESTIONS))
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        if cols[i].button(q, key=f"example_{i}"):
            st.session_state.chart_input = q
            st.rerun()

    # Input
    question = st.text_input(
        "Your question:",
        key="chart_input",
    )

    if question:
        with st.spinner("Generating chart..."):
            system = CHART_SYSTEM_PROMPT.format(schema=_schema())
            prompt = f"{system}\n\nQuestion: {question}"
            response = cortex_complete(prompt, model="mistral-large2")

            # Extract SQL
            import re
            sql_match = re.search(r"```sql\s*(.*?)\s*```", response, re.DOTALL)
            if sql_match:
                sql = sql_match.group(1).strip()
                st.code(sql, language="sql")

                try:
                    df = run_query_df(sql)
                    if not df.empty:
                        cols_list = df.columns.tolist()
                        label_col = cols_list[0]
                        value_cols = cols_list[1:]

                        # Auto-detect chart type
                        temporal_keywords = ["month", "year", "date", "week", "quarter"]
                        is_temporal = any(
                            kw in label_col.lower() for kw in temporal_keywords
                        )

                        if is_temporal:
                            fig = px.line(df, x=label_col, y=value_cols[0],
                                         title=question)
                        else:
                            fig = px.bar(df, x=label_col, y=value_cols[0],
                                         title=question)

                        st.plotly_chart(fig, use_container_width=True)

                        # Show raw data
                        with st.expander("Raw Data"):
                            st.dataframe(df)
                    else:
                        st.warning("Query returned no results.")
                except Exception as e:
                    st.error(f"Error running query: {e}")
            else:
                st.warning("Could not extract SQL from the response.")
                st.text(response)
