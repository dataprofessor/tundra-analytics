import streamlit as st

st.set_page_config(
    page_title="Tundra SaaS Analytics",
    page_icon="🏔️",
    layout="wide",
)

from src.dashboard import show as dashboard_show
from src.ai_agent import show as ai_agent_show
from src.chart_agent import show as chart_show
from src.kpi_summary import show as kpi_show
from src.semantic_search import show as search_show

# Role mapping from email to role
ROLE_MAP = {
    "analyst@tundra.io": "analyst",
    "manager@tundra.io": "manager",
    "exec@tundra.io": "executive",
}

# Detect role from st.experimental_user or fallback to sidebar
try:
    user_email = st.experimental_user.get("email", "")
    role = ROLE_MAP.get(user_email, None)
except Exception:
    role = None

if not role:
    role = st.sidebar.selectbox(
        "Select Role (demo)", ["analyst", "manager", "executive"]
    )

# Define pages by role
ROLE_PAGES = {
    "analyst": [
        st.Page(dashboard_show, title="Dashboard", url_path="dashboard", icon=":material/dashboard:"),
        st.Page(ai_agent_show, title="AI Agent", url_path="ai-agent", icon=":material/smart_toy:"),
        st.Page(chart_show, title="Charts", url_path="charts", icon=":material/bar_chart:"),
        st.Page(search_show, title="Semantic Search", url_path="search", icon=":material/search:"),
    ],
    "manager": [
        st.Page(dashboard_show, title="Dashboard", url_path="dashboard", icon=":material/dashboard:"),
        st.Page(ai_agent_show, title="AI Agent", url_path="ai-agent", icon=":material/smart_toy:"),
    ],
    "executive": [
        st.Page(kpi_show, title="KPI Summary", url_path="kpi-summary", icon=":material/trending_up:"),
        st.Page(ai_agent_show, title="AI Agent", url_path="ai-agent", icon=":material/smart_toy:"),
    ],
}

pages = st.navigation(ROLE_PAGES.get(role, ROLE_PAGES["analyst"]), position="top")
pages.run()
