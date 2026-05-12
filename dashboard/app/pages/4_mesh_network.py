import sys

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

sys.path.insert(0, "/app")
from db import query

st.set_page_config(page_title="MeSH Network", layout="wide")
st.title("MeSH Term Co-occurrence Network")

top_n = st.slider("Number of top pairs to show", 50, 500, 150)

df = query(
    "SELECT term_a, term_b, co_count FROM mesh_cooccurrences ORDER BY co_count DESC LIMIT :n",
    {"n": top_n},
)

if df.empty:
    st.info("No co-occurrence data yet — run the mesh_cooccurrence_network asset first.")
    st.stop()

min_count = int(df["co_count"].min())
max_count = int(df["co_count"].max())
threshold = st.slider("Minimum co-occurrence count", min_count, max_count, min_count)
df = df[df["co_count"] >= threshold]

net = Network(height="650px", width="100%", bgcolor="#1a1a2e", font_color="white")
net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=120)

node_weights: dict[str, int] = {}
for _, row in df.iterrows():
    node_weights[row["term_a"]] = node_weights.get(row["term_a"], 0) + row["co_count"]
    node_weights[row["term_b"]] = node_weights.get(row["term_b"], 0) + row["co_count"]

max_weight = max(node_weights.values()) if node_weights else 1
for term, weight in node_weights.items():
    size = 10 + 30 * (weight / max_weight)
    net.add_node(term, label=term, size=size, title=f"{term}\nTotal co-occurrences: {weight}")

max_co = df["co_count"].max() if not df.empty else 1
for _, row in df.iterrows():
    width = 1 + 5 * (row["co_count"] / max_co)
    net.add_edge(
        row["term_a"],
        row["term_b"],
        value=row["co_count"],
        title=str(row["co_count"]),
        width=width,
    )

html = net.generate_html()
components.html(html, height=670, scrolling=False)

st.caption(
    f"Showing {len(df)} edges across {len(node_weights)} MeSH terms. "
    "Node size and edge width reflect co-occurrence frequency."
)
