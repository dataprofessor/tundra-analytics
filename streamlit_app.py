import streamlit as st
from src.dashboard import show as dashboard_show
from src.ai_agent import show as agent_show
from src.chart_agent import show as chart_show
from src.kpi_summary import show as kpi_show
from src.semantic_search import show as search_show

st.set_page_config(page_title="Tundra SaaS Analytics", layout="wide")

# Role-based routing
ROLE_MAP = {
    "analyst@tundra.io": "Analyst",
    "manager@tundra.io": "Manager",
    "exec@tundra.io": "Executive",
}

# Try to detect role from email, fall back to sidebar selector
try:
    email = st.experimental_user.email
    role = ROLE_MAP.get(email, "Analyst")
except Exception:
    email = None
    role = None

if not role:
    role = st.sidebar.selectbox("Select Role (demo)", ["Analyst", "Manager", "Executive"])

# Define pages per role
if role == "Executive":
    pages = [
        st.Page(kpi_show, title="KPI Summary", icon=":material/monitoring:", url_path="kpi-summary"),
        st.Page(agent_show, title="AI Agent", icon=":material/smart_toy:", url_path="ai-agent"),
    ]
elif role == "Manager":
    pages = [
        st.Page(dashboard_show, title="Dashboard", icon=":material/dashboard:", url_path="dashboard"),
        st.Page(agent_show, title="AI Agent", icon=":material/smart_toy:", url_path="ai-agent"),
    ]
else:  # Analyst
    pages = [
        st.Page(dashboard_show, title="Dashboard", icon=":material/dashboard:", url_path="dashboard"),
        st.Page(agent_show, title="AI Agent", icon=":material/smart_toy:", url_path="ai-agent"),
        st.Page(chart_show, title="Charts", icon=":material/bar_chart:", url_path="charts"),
        st.Page(search_show, title="Semantic Search", icon=":material/search:", url_path="semantic-search"),
    ]

nav = st.navigation(pages, position="sidebar")
nav.run()
