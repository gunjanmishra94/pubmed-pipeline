import sys

import plotly.express as px
import streamlit as st

sys.path.insert(0, "/app")
from db import query

st.set_page_config(page_title="Paradigm Shifts", layout="wide")
st.title("Treatment Paradigm Shifts Over Time")

df = query("""
    SELECT a.publication_year, t.treatment, COUNT(*) AS mentions
    FROM treatment_outcomes t
    JOIN abstracts a ON t.pmid = a.pmid
    WHERE a.publication_year IS NOT NULL
    GROUP BY a.publication_year, t.treatment
""")

if df.empty:
    st.info("No data yet — run treatment_outcome_extraction first.")
    st.stop()

top_n = st.slider("Number of top treatments to track", 5, 20, 10)

min_year = int(df["publication_year"].min())
max_year = int(df["publication_year"].max())
if min_year < max_year:
    year_range = st.slider("Year range", min_year, max_year, (min_year, max_year))
    df = df[df["publication_year"].between(*year_range)]
else:
    st.caption(f"Showing data for {min_year}")

top_treatments = df.groupby("treatment")["mentions"].sum().nlargest(top_n).index.tolist()
df = df[df["treatment"].isin(top_treatments)]

pivot = (
    df.pivot_table(index="publication_year", columns="treatment", values="mentions", aggfunc="sum")
    .fillna(0)
    .reset_index()
)

melted = pivot.melt(id_vars="publication_year", var_name="treatment", value_name="mentions")

fig = px.area(
    melted,
    x="publication_year",
    y="mentions",
    color="treatment",
    title=f"Top {top_n} treatments by year — stacked mention count",
    labels={"mentions": "Mentions", "publication_year": "Year"},
    groupnorm="",
)
fig.update_layout(height=520, hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Normalised share (% of all mentions per year)")
fig2 = px.area(
    melted,
    x="publication_year",
    y="mentions",
    color="treatment",
    groupnorm="percent",
    title="Relative treatment focus over time",
    labels={"mentions": "Share (%)", "publication_year": "Year"},
)
fig2.update_layout(height=400, hovermode="x unified", yaxis_ticksuffix="%")
st.plotly_chart(fig2, use_container_width=True)
