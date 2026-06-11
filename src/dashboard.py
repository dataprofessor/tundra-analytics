import json
from pathlib import Path
import streamlit as st
import plotly.express as px
import pydeck as pdk
from src.db import run_query_df

_GEOJSON_PATH = Path(__file__).parent / "assets" / "countries.geojson"


@st.cache_data
def _load_country_geojson():
    with open(_GEOJSON_PATH) as f:
        return json.load(f)


def _mrr_color(norm):
    """Blue ramp on a dark basemap: dim navy (low) -> bright blue (high)."""
    return [int(40 + 80 * norm), int(90 + 130 * norm), int(150 + 105 * norm), 210]


def _build_map_layers(map_df):
    """Filled, clickable country polygons colored by active MRR. Falls back
    to a point for any of our countries missing a low-res polygon (e.g. SGP)."""
    df = map_df.copy()
    df["country_code"] = df["country_code"].str.strip()
    df["total_mrr"] = df["total_mrr"].astype(float)
    max_mrr = df["total_mrr"].max() or 1.0
    info = {r.country_code: r for r in df.itertuples()}

    geo = _load_country_geojson()
    features, matched = [], set()
    for f in geo["features"]:
        code = f["properties"].get("ADM0_A3")
        if code not in info:
            continue
        rec = info[code]
        features.append({
            "type": "Feature",
            "geometry": f["geometry"],
            "properties": {
                "country_code": code,
                "country_name": rec.country_name,
                "total_mrr": rec.total_mrr,
                "fill_color": _mrr_color(rec.total_mrr / max_mrr),
            },
        })
        matched.add(code)

    layers = [pdk.Layer(
        "GeoJsonLayer",
        data={"type": "FeatureCollection", "features": features},
        id="mrr_poly",
        pickable=True,
        stroked=True,
        filled=True,
        auto_highlight=True,
        highlight_color=[255, 255, 255, 90],
        get_fill_color="properties.fill_color",
        get_line_color=[90, 100, 120],
        line_width_min_pixels=0.5,
    )]

    # Fallback points for our countries with no low-res polygon
    missing = df[~df["country_code"].isin(matched)].copy()
    if not missing.empty:
        missing["latitude"] = missing["latitude"].astype(float)
        missing["longitude"] = missing["longitude"].astype(float)
        missing["fill_color"] = [_mrr_color(m / max_mrr) for m in missing["total_mrr"]]
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=missing,
            id="mrr_pts",
            get_position="[longitude, latitude]",
            get_fill_color="fill_color",
            get_radius=120000,
            radius_min_pixels=5,
            pickable=True,
            auto_highlight=True,
        ))
    return layers


def show():
    st.header("Dashboard")

    # Active MRR per country with centroids (for the point fallback)
    map_df = run_query_df("""
        SELECT co.country_code, co.country_name, co.latitude, co.longitude,
               sum(s.mrr) as total_mrr
        FROM subscriptions s
        JOIN customers c ON s.customer_id = c.customer_id
        JOIN countries co ON c.country_code = co.country_code
        WHERE s.status = 'active'
        GROUP BY co.country_code, co.country_name, co.latitude, co.longitude
    """)

    st.caption("Showing global figures by default. Click a country on the map to drill into its metrics.")
    st.markdown("**MRR by Country**")

    deck = pdk.Deck(
        layers=_build_map_layers(map_df),
        initial_view_state=pdk.ViewState(latitude=20, longitude=10, zoom=0.7),
        map_style="dark",
        tooltip={"html": "<b>{country_name}</b><br/>Active MRR: ${total_mrr}"},
    )
    selection = st.pydeck_chart(
        deck, on_select="rerun", selection_mode="single-object", key="world_map"
    )

    # Determine selected country (None means global / first load)
    selected_country = None
    selected_name = None
    if selection and getattr(selection, "selection", None):
        objs = selection.selection.get("objects", {})
        for lid in ("mrr_poly", "mrr_pts"):
            picked = objs.get(lid, [])
            if picked:
                o = picked[0]
                props = o.get("properties") if isinstance(o.get("properties"), dict) else o
                selected_country = props.get("country_code") or o.get("country_code")
                selected_name = props.get("country_name") or o.get("country_name")
                break

    # Use the full country name in labels; the ISO-3 code still drives the SQL.
    name_by_code = dict(zip(map_df["country_code"].str.strip(), map_df["country_name"]))
    scope_label = (
        (selected_name or name_by_code.get(selected_country, selected_country))
        if selected_country else "All Countries"
    )
    where_country = "WHERE c.country_code = %(country)s" if selected_country else ""
    and_country = "AND c.country_code = %(country)s" if selected_country else ""
    params = {"country": selected_country} if selected_country else None

    # Single adaptive metric row: global on first load, country-specific on click
    st.subheader(f"Overview ({scope_label})")
    metrics = run_query_df(f"""
        SELECT
            sum(s.mrr) FILTER (WHERE s.status = 'active') as total_mrr,
            count(*) FILTER (WHERE s.status = 'active') as active_subs,
            round(100.0 * count(*) FILTER (WHERE s.status = 'churned')
                / nullif(count(*), 0), 1) as churn_rate,
            avg(s.seats) FILTER (WHERE s.status = 'active') as avg_seats
        FROM subscriptions s
        JOIN customers c ON s.customer_id = c.customer_id
        {where_country}
    """, params=params)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total MRR", f"${(metrics['total_mrr'].iloc[0] or 0):,.0f}")
    m2.metric("Active Subscriptions", f"{int(metrics['active_subs'].iloc[0] or 0):,}")
    m3.metric("Churn Rate %", f"{(metrics['churn_rate'].iloc[0] or 0):.1f}%")
    m4.metric("Avg Seats", f"{(metrics['avg_seats'].iloc[0] or 0):.1f}")

    # Adaptive accounts table
    st.subheader(f"Accounts ({scope_label})")
    accounts_df = run_query_df(f"""
        SELECT c.company_name, c.industry, co.country_name,
               p.plan_name, s.seats, s.mrr, s.status
        FROM subscriptions s
        JOIN customers c ON s.customer_id = c.customer_id
        JOIN plans p ON s.plan_id = p.plan_id
        JOIN countries co ON c.country_code = co.country_code
        {where_country}
        ORDER BY s.mrr DESC
        LIMIT 100
    """, params=params)
    st.dataframe(accounts_df, use_container_width=True)

    # Trend + feature breakdown side by side, both scope-aware
    left, right = st.columns(2)

    with left:
        st.subheader(f"Monthly Revenue Trend ({scope_label})")
        revenue_df = run_query_df(f"""
            SELECT to_char(i.invoice_date, 'YYYY-MM') as month, sum(i.amount) as revenue
            FROM invoices i
            JOIN customers c ON i.customer_id = c.customer_id
            WHERE i.invoice_date >= date_trunc('month', now()) - interval '12 months'
            {and_country}
            GROUP BY month
            ORDER BY month
        """, params=params)
        if not revenue_df.empty:
            fig_rev = px.line(revenue_df, x="month", y="revenue", title="Monthly Recurring Revenue")
            st.plotly_chart(fig_rev, width="stretch")
        else:
            st.info("No revenue data for this selection.")

    with right:
        st.subheader(f"Most Used Plan Features ({scope_label})")
        features_df = run_query_df(f"""
            SELECT feature, count(*) as usage_count
            FROM subscriptions s
            JOIN plans p ON s.plan_id = p.plan_id
            JOIN customers c ON s.customer_id = c.customer_id
            CROSS JOIN LATERAL unnest(p.features) AS feature
            WHERE s.status = 'active'
            {and_country}
            GROUP BY feature
            ORDER BY usage_count DESC
        """, params=params)
        if not features_df.empty:
            fig_feat = px.pie(
                features_df, names="feature", values="usage_count",
                hole=0.55, title="Plan Features",
            )
            fig_feat.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_feat, width="stretch")
        else:
            st.info("No plan feature data for this selection.")
