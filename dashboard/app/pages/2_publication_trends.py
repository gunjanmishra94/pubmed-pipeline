import sys

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, "/app")
from db import query

st.set_page_config(page_title="Publication Trends", layout="wide")
st.title("Publication Trends")

df = query("""
    SELECT publication_year, abstract_count, rct_count, review_count, unique_journals
    FROM publication_trends
    WHERE publication_year IS NOT NULL
    ORDER BY publication_year
""")

if df.empty:
    st.info("No trend data yet — run the publication_trends asset first.")
    st.stop()

df["rct_fraction"] = df["rct_count"] / df["abstract_count"].clip(lower=1)

year_range = st.slider(
    "Year range",
    int(df["publication_year"].min()),
    int(df["publication_year"].max()),
    (int(df["publication_year"].min()), int(df["publication_year"].max())),
)
df = df[df["publication_year"].between(*year_range)]

fig = go.Figure()

fig.add_trace(
    go.Bar(
        x=df["publication_year"],
        y=df["abstract_count"],
        name="Abstracts",
        marker_color="#3498db",
        opacity=0.7,
    )
)

fig.add_trace(
    go.Scatter(
        x=df["publication_year"],
        y=df["rct_fraction"],
        name="RCT fraction",
        yaxis="y2",
        line={"color": "#e74c3c", "width": 2},
        mode="lines+markers",
    )
)

fig.update_layout(
    title="Endometriosis publications per year with RCT fraction",
    xaxis_title="Year",
    yaxis_title="Abstract count",
    yaxis2={
        "title": "RCT fraction",
        "overlaying": "y",
        "side": "right",
        "range": [0, 1],
        "tickformat": ".0%",
    },
    legend={"x": 0.01, "y": 0.99},
    height=500,
)
st.plotly_chart(fig, use_container_width=True)

col1, col2, col3 = st.columns(3)
col1.metric("Total abstracts", int(df["abstract_count"].sum()))
col2.metric("Total RCTs", int(df["rct_count"].sum()))
col3.metric("Unique journals", int(df["unique_journals"].max()))
