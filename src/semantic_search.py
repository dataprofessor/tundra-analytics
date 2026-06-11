import streamlit as st
from src.db import run_query_df
from src.cortex import cortex_embed


def show():
    st.header("Semantic Search")
    st.caption("Find similar accounts using AI-powered semantic search")

    query = st.text_input("Describe the type of account you're looking for",
                          placeholder="e.g. fast-growing healthcare companies in EMEA")

    if query:
        with st.spinner("Searching..."):
            embedding = cortex_embed(query)
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

            results = run_query_df("""
                SELECT cu.company_name, cu.industry, co.country_name,
                       p.plan_name, s.mrr, cu.description,
                       1 - (ce.embedding <=> %(emb)s::vector) AS similarity
                FROM customer_embeddings ce
                JOIN customers cu ON cu.customer_id = ce.customer_id
                JOIN countries co ON co.country_code = cu.country_code
                LEFT JOIN subscriptions s ON s.customer_id = cu.customer_id AND s.status = 'active'
                LEFT JOIN plans p ON p.plan_id = s.plan_id
                ORDER BY ce.embedding <=> %(emb)s::vector
                LIMIT 10
            """, {"emb": embedding_str})

        if results.empty:
            st.info("No results found. Make sure embeddings are generated.")
        else:
            for _, row in results.iterrows():
                sim_pct = f"{row['similarity'] * 100:.1f}%" if row["similarity"] else "N/A"
                with st.expander(f"{row['company_name']} — {sim_pct} match"):
                    st.write(f"**Industry:** {row['industry']}")
                    st.write(f"**Country:** {row['country_name']}")
                    st.write(f"**Plan:** {row['plan_name'] or 'N/A'}")
                    st.write(f"**MRR:** ${row['mrr']:,.2f}" if row["mrr"] else "**MRR:** N/A")
                    st.write(f"**Description:** {row['description']}")
