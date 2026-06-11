# Tundra SaaS Analytics

An interactive analytics app for a fictional global B2B SaaS company, **Tundra**, built with **Streamlit**, **Snowflake Postgres**, and **Snowflake Cortex AI**.

It visualizes subscriptions, usage, and revenue across ~30 countries, with a clickable dark world map, an AI data agent, on-demand charts, and semantic search.

## Features

- **Dashboard** with an interactive dark world map (PyDeck). Click a country to drill its metrics, accounts table, revenue trend, and plan-feature mix all update to that country.
- **AI Agent**: ask questions in natural language; Snowflake Cortex generates SQL, runs it against Postgres, and shows the result. Includes example prompts and human-in-the-loop confirmation for write queries.
- **Charts on Demand**: type a business question and get an auto-generated Plotly chart.
- **Semantic Search**: find accounts by meaning using pgvector and Cortex embeddings.
- **Role-based views**: Analyst, Manager, and Executive each see a tailored set of pages.

## Stack

- Python 3.11+, Streamlit (multipage via `st.navigation`)
- Snowflake Postgres (data), accessed with `psycopg2`
- Snowflake Cortex AI (`COMPLETE`, `EMBED_TEXT_1024`) via `snowflake-snowpark-python`
- PyDeck (map), Plotly (charts), pgvector (semantic search)

## Data model

| Table | Purpose |
|-------|---------|
| `countries` | ISO-3 country reference with coordinates |
| `plans` | Starter / Pro / Enterprise, with a `features` array |
| `customers` | accounts by country and industry |
| `subscriptions` | seats, MRR, status (active / trial / churned) |
| `usage_events` | product usage with JSONB metadata |
| `invoices` | monthly billing |
| `customer_embeddings` | pgvector embeddings for semantic search |

## Run locally

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
# add your credentials to .streamlit/secrets.toml (see below)
.venv/bin/streamlit run streamlit_app.py
```

Create `.streamlit/secrets.toml` (this file is gitignored and must never be committed):

```toml
[postgres]
host = "<your-postgres-host>.postgres.snowflake.app"
port = 5432
dbname = "<database>"
user = "<user>"
password = "<password>"

[snowflake]
account = "<account-identifier>"
user = "<user>"
# password = "<password>"            # or use a programmatic access token:
authenticator = "PROGRAMMATIC_ACCESS_TOKEN"
token = "<token>"
warehouse = "<warehouse>"
role = "<role>"
```

## Deploy to Streamlit Community Cloud

1. Sign in at [share.streamlit.io](https://share.streamlit.io) with GitHub.
2. New app from this repo: branch `main`, main file `streamlit_app.py`, Python 3.11.
3. Under Advanced settings, paste your `secrets.toml` contents into the Secrets box.
4. Deploy.

The Postgres instance must allow inbound access from Community Cloud, and the Snowflake credentials (token or password) must be permitted to authenticate from external IPs for the Cortex-powered pages to work.

## Repo structure

```
streamlit_app.py        role-based navigation entry point
src/db.py               Postgres connection and query helpers
src/cortex.py           Snowpark session and Cortex helpers
src/dashboard.py        world map, metrics, accounts, charts
src/ai_agent.py         natural-language data agent
src/chart_agent.py      natural-language charting
src/kpi_summary.py      executive KPI page
src/semantic_search.py  pgvector semantic search
src/assets/             bundled country GeoJSON for the map
AGENTS.md               project conventions and gotchas (agent context)
```

## Credits

Built with Snowflake Cortex Code. See `AGENTS.md` for the project conventions used during development.
