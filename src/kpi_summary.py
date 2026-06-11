import streamlit as st
import plotly.express as px
from src.db import run_query_df


def show():
    st.header("Executive KPI Summary")

    # KPI metrics
    kpi_df = run_query_df("""
        SELECT
            sum(s.mrr) FILTER (WHERE s.status = 'active') as total_active_mrr,
            count(*) FILTER (WHERE s.status = 'active') as active_subs,
            round(100.0 * count(*) FILTER (WHERE s.status = 'churned')
                / nullif(count(*), 0), 1) as churn_rate,
            sum(s.mrr) FILTER (WHERE s.status = 'active')
                / nullif(count(DISTINCT s.customer_id) FILTER (WHERE s.status = 'active'), 0) as arpa
        FROM subscriptions s
    """)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Active MRR", f"${kpi_df['total_active_mrr'].iloc[0]:,.0f}")
    c2.metric("Active Subscriptions", f"{kpi_df['active_subs'].iloc[0]:,}")
    c3.metric("Churn Rate %", f"{kpi_df['churn_rate'].iloc[0]:.1f}%")
    c4.metric("ARPA", f"${kpi_df['arpa'].iloc[0]:,.0f}")

    # 6-month MRR area chart
    st.subheader("MRR Trend (Last 6 Months)")
    mrr_df = run_query_df("""
        SELECT to_char(invoice_date, 'YYYY-MM') as month, sum(amount) as mrr
        FROM invoices
        WHERE invoice_date >= date_trunc('month', now()) - interval '6 months'
        GROUP BY month
        ORDER BY month
    """)
    if not mrr_df.empty:
        fig = px.area(mrr_df, x="month", y="mrr", title="Monthly Recurring Revenue")
        st.plotly_chart(fig, use_container_width=True)
