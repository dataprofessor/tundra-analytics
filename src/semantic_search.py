import streamlit as st
from src.db import run_query_df
from src.cortex import cortex_embed


def show():
    st.header("Semantic Search")
    st.caption("Find accounts by describing what you're looking for.")

    query = st.text_input(
        "Describe the kind of account you're looking for:",
        placeholder="e.g. fast-growing healthcare companies in EMEA",
    )

    if query:
        with st.spinner("Searching..."):
            # Embed the query
            query_embedding = cortex_embed(query)
            if not query_embedding:
                st.error("Failed to generate embedding for query.")
                return

            # Format embedding as pgvector literal
            emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

            # Query PG using cosine distance
            results_df = run_query_df(
                """
                SELECT
                    c.customer_id,
                    c.company_name,
                    c.industry,
                    co.country_name,
                    p.plan_name,
                    s.mrr,
                    1 - (ce.embedding <=> %(emb)s::vector) as similarity
                FROM customer_embeddings ce
                JOIN customers c ON ce.customer_id = c.customer_id
                JOIN countries co ON c.country_code = co.country_code
                LEFT JOIN subscriptions s ON s.customer_id = c.customer_id AND s.status = 'active'
                LEFT JOIN plans p ON s.plan_id = p.plan_id
                ORDER BY ce.embedding <=> %(emb)s::vector
                LIMIT 10
                """,
                params={"emb": emb_str},
            )

            if results_df.empty:
                st.info("No results found.")
                return

            st.subheader(f"Top {len(results_df)} Results")
            for _, row in results_df.iterrows():
                similarity_pct = row["similarity"] * 100 if row["similarity"] else 0
                with st.expander(
                    f"🏢 {row['company_name']} — {similarity_pct:.1f}% match"
                ):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Industry", row["industry"])
                    col2.metric("Country", row["country_name"])
                    col3.metric("Plan", row["plan_name"] or "N/A")

                    if row["mrr"]:
                        st.metric("MRR", f"${row['mrr']:,.0f}")
