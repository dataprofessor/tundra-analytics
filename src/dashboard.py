import json
import os
import streamlit as st
import pydeck as pdk
import plotly.express as px
from src.db import run_query_df


def _load_geojson():
    path = os.path.join(os.path.dirname(__file__), "assets", "countries.geojson")
    with open(path) as f:
        return json.load(f)


def show():
    st.header("Dashboard")

    # Load GeoJSON and MRR data for the choropleth
    geojson = _load_geojson()
    mrr_by_country = run_query_df("""
        SELECT cu.country_code, co.country_name, co.latitude, co.longitude,
               round(sum(s.mrr)::numeric, 2) AS total_mrr
        FROM subscriptions s
        JOIN customers cu ON cu.customer_id = s.customer_id
        JOIN countries co ON co.country_code = cu.country_code
        WHERE s.status = 'active'
        GROUP BY cu.country_code, co.country_name, co.latitude, co.longitude
    """)

    # Build lookup for MRR coloring
    mrr_lookup = dict(zip(mrr_by_country["country_code"].str.strip(), mrr_by_country["total_mrr"]))
    max_mrr = mrr_by_country["total_mrr"].max() if not mrr_by_country.empty else 1

    # Add MRR and color to GeoJSON features
    for feat in geojson["features"]:
        code = feat["properties"].get("ADM0_A3", "")
        mrr_val = mrr_lookup.get(code, 0)
        feat["properties"]["mrr"] = float(mrr_val)
        intensity = min(mrr_val / max_mrr, 1.0) if max_mrr > 0 else 0
        feat["properties"]["fill_color"] = [
            int(20 + 80 * intensity),
            int(80 + 175 * intensity),
            int(80 + 100 * intensity),
            180,
        ]

    # GeoJSON layer (filled polygons)
    geo_layer = pdk.Layer(
        "GeoJsonLayer",
        id="countries",
        data=geojson,
        pickable=True,
        stroked=True,
        filled=True,
        get_fill_color="properties.fill_color",
        get_line_color=[255, 255, 255, 50],
        line_width_min_pixels=1,
        auto_highlight=True,
        highlight_color=[255, 200, 0, 128],
    )

    # Scatterplot fallback for countries without polygons (e.g. SGP)
    geo_codes = set()
    for feat in geojson["features"]:
        geo_codes.add(feat["properties"].get("ADM0_A3", ""))
    scatter_data = mrr_by_country[~mrr_by_country["country_code"].str.strip().isin(geo_codes)]

    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        id="points",
        data=scatter_data,
        get_position=["longitude", "latitude"],
        get_radius=50000,
        get_fill_color=[100, 200, 150, 200],
        pickable=True,
    )

    view_state = pdk.ViewState(latitude=20, longitude=0, zoom=1.3, pitch=0)
    deck = pdk.Deck(
        layers=[geo_layer, scatter_layer],
        initial_view_state=view_state,
        map_style="dark",
        tooltip={"text": "{properties.NAME}: ${properties.mrr}"},
    )

    selection = st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object")

    # Parse selection
    selected_country = None
    selected_country_name = None
    if selection and selection.selection:
        objects = selection.selection.get("objects", {})
        # Check GeoJson layer
        geo_picks = objects.get("countries", [])
        if geo_picks:
            props = geo_picks[0].get("properties", geo_picks[0])
            selected_country = props.get("ADM0_A3")
            selected_country_name = props.get("NAME")
        # Check scatter layer
        point_picks = objects.get("points", [])
        if point_picks:
            selected_country = point_picks[0].get("country_code", "").strip()
            selected_country_name = point_picks[0].get("country_name")

    # Scope label
    scope_label = f"Overview ({selected_country_name})" if selected_country else "Overview (All Countries)"
    st.subheader(scope_label)

    # Metrics query
    if selected_country:
        metrics = run_query_df("""
            SELECT
                round(sum(CASE WHEN s.status='active' THEN s.mrr ELSE 0 END)::numeric, 2) AS total_mrr,
                count(*) FILTER (WHERE s.status='active') AS active_subs,
                round(100.0 * count(*) FILTER (WHERE s.status='churned') / NULLIF(count(*), 0), 1) AS churn_rate,
                round(avg(CASE WHEN s.status='active' THEN s.seats END)::numeric, 1) AS avg_seats,
                round((sum(CASE WHEN s.status='active' THEN s.mrr ELSE 0 END) /
                       NULLIF(count(DISTINCT CASE WHEN s.status='active' THEN s.customer_id END), 0))::numeric, 2) AS arpa
            FROM subscriptions s
            JOIN customers cu ON cu.customer_id = s.customer_id
            WHERE cu.country_code = %(country)s
        """, {"country": selected_country})
    else:
        metrics = run_query_df("""
            SELECT
                round(sum(CASE WHEN s.status='active' THEN s.mrr ELSE 0 END)::numeric, 2) AS total_mrr,
                count(*) FILTER (WHERE s.status='active') AS active_subs,
                round(100.0 * count(*) FILTER (WHERE s.status='churned') / NULLIF(count(*), 0), 1) AS churn_rate,
                round(avg(CASE WHEN s.status='active' THEN s.seats END)::numeric, 1) AS avg_seats,
                round((sum(CASE WHEN s.status='active' THEN s.mrr ELSE 0 END) /
                       NULLIF(count(DISTINCT CASE WHEN s.status='active' THEN s.customer_id END), 0))::numeric, 2) AS arpa
            FROM subscriptions s
        """)

    if not metrics.empty:
        row = metrics.iloc[0]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total MRR", f"${row['total_mrr']:,.0f}")
        c2.metric("Active Subscriptions", f"{int(row['active_subs']):,}")
        c3.metric("Churn Rate", f"{row['churn_rate']}%")
        c4.metric("Avg Seats", f"{row['avg_seats']}")
        c5.metric("ARPA", f"${row['arpa']:,.0f}")

    # Accounts table
    st.subheader("Accounts")
    if selected_country:
        accounts = run_query_df("""
            SELECT cu.company_name, cu.industry, co.country_name,
                   p.plan_name, s.seats, s.mrr, s.status
            FROM subscriptions s
            JOIN customers cu ON cu.customer_id = s.customer_id
            JOIN countries co ON co.country_code = cu.country_code
            JOIN plans p ON p.plan_id = s.plan_id
            WHERE cu.country_code = %(country)s
            ORDER BY s.mrr DESC
            LIMIT 50
        """, {"country": selected_country})
    else:
        accounts = run_query_df("""
            SELECT cu.company_name, cu.industry, co.country_name,
                   p.plan_name, s.seats, s.mrr, s.status
            FROM subscriptions s
            JOIN customers cu ON cu.customer_id = s.customer_id
            JOIN countries co ON co.country_code = cu.country_code
            JOIN plans p ON p.plan_id = s.plan_id
            ORDER BY s.mrr DESC
            LIMIT 50
        """)

    if accounts.empty:
        st.info("No accounts found for this selection.")
    else:
        st.dataframe(accounts, width="stretch")

    # Charts side by side
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Monthly Revenue Trend")
        if selected_country:
            revenue = run_query_df("""
                SELECT to_char(i.invoice_date, 'YYYY-MM') AS month,
                       round(sum(i.amount)::numeric, 0) AS revenue
                FROM invoices i
                JOIN customers cu ON cu.customer_id = i.customer_id
                WHERE cu.country_code = %(country)s
                GROUP BY 1 ORDER BY 1
            """, {"country": selected_country})
        else:
            revenue = run_query_df("""
                SELECT to_char(i.invoice_date, 'YYYY-MM') AS month,
                       round(sum(i.amount)::numeric, 0) AS revenue
                FROM invoices i
                GROUP BY 1 ORDER BY 1
            """)
        if not revenue.empty:
            fig = px.line(revenue, x="month", y="revenue", markers=True)
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No revenue data.")

    with col2:
        st.subheader("Most Used Plan Features")
        if selected_country:
            features = run_query_df("""
                SELECT unnest(p.features) AS feature, count(*) AS usage_count
                FROM subscriptions s
                JOIN plans p ON p.plan_id = s.plan_id
                JOIN customers cu ON cu.customer_id = s.customer_id
                WHERE s.status = 'active' AND cu.country_code = %(country)s
                GROUP BY 1 ORDER BY 2 DESC
            """, {"country": selected_country})
        else:
            features = run_query_df("""
                SELECT unnest(p.features) AS feature, count(*) AS usage_count
                FROM subscriptions s
                JOIN plans p ON p.plan_id = s.plan_id
                WHERE s.status = 'active'
                GROUP BY 1 ORDER BY 2 DESC
            """)
        if not features.empty:
            fig = px.pie(features, names="feature", values="usage_count", hole=0.4)
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No feature data.")
