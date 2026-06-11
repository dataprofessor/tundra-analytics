import streamlit as st
import plotly.express as px
from src.db import run_query_df


def show():
    st.header("Executive KPI Summary")

    # KPI metrics
    metrics = run_query_df("""
        SELECT
            round(sum(CASE WHEN s.status='active' THEN s.mrr ELSE 0 END)::numeric, 2) AS total_mrr,
            count(*) FILTER (WHERE s.status='active') AS active_subs,
            round(100.0 * count(*) FILTER (WHERE s.status='churned') / NULLIF(count(*), 0), 1) AS churn_rate,
            round((sum(CASE WHEN s.status='active' THEN s.mrr ELSE 0 END) /
                   NULLIF(count(DISTINCT CASE WHEN s.status='active' THEN s.customer_id END), 0))::numeric, 2) AS arpa
        FROM subscriptions s
    """)

    if not metrics.empty:
        row = metrics.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Active MRR", f"${row['total_mrr']:,.0f}")
        c2.metric("Active Subscriptions", f"{int(row['active_subs']):,}")
        c3.metric("Churn Rate", f"{row['churn_rate']}%")
        c4.metric("ARPA", f"${row['arpa']:,.0f}")

    # 6-month MRR area chart
    st.subheader("MRR Trend (Last 6 Months)")
    mrr_trend = run_query_df("""
        SELECT to_char(i.invoice_date, 'YYYY-MM') AS month,
               round(sum(i.amount)::numeric, 0) AS mrr
        FROM invoices i
        WHERE i.invoice_date >= (CURRENT_DATE - INTERVAL '6 months')
        GROUP BY 1 ORDER BY 1
    """)

    if not mrr_trend.empty:
        fig = px.area(mrr_trend, x="month", y="mrr", markers=True)
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=350)
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No revenue data for the last 6 months.")
