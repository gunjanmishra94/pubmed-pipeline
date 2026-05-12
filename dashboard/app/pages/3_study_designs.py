import sys

import plotly.express as px
import streamlit as st

sys.path.insert(0, "/app")
from db import query

st.set_page_config(page_title="Study Designs", layout="wide")
st.title("Study Design Distribution Over Time")

df = query("""
    SELECT a.publication_year, sd.design_type, COUNT(*) AS count
    FROM study_designs sd
    JOIN abstracts a ON sd.pmid = a.pmid
    WHERE a.publication_year IS NOT NULL
    GROUP BY a.publication_year, sd.design_type
    ORDER BY a.publication_year
""")

if df.empty:
    st.info("No classification data yet — run the study_design_classification asset first.")
    st.stop()

confidence_df = query("""
    SELECT design_type, confidence, COUNT(*) AS count
    FROM study_designs
    GROUP BY design_type, confidence
""")

col1, col2 = st.columns([3, 1])

with col1:
    fig = px.bar(
        df,
        x="publication_year",
        y="count",
        color="design_type",
        title="Study design distribution by year",
        labels={"count": "Abstracts", "publication_year": "Year", "design_type": "Design"},
        barmode="stack",
    )
    fig.update_layout(height=500, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    overall = df.groupby("design_type")["count"].sum().reset_index()
    fig2 = px.pie(
        overall,
        names="design_type",
        values="count",
        title="Overall mix",
        hole=0.4,
    )
    fig2.update_layout(height=500, showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Classification Confidence")
fig3 = px.bar(
    confidence_df,
    x="design_type",
    y="count",
    color="confidence",
    color_discrete_map={"high": "#2ecc71", "medium": "#f39c12", "low": "#e74c3c"},
    title="Confidence per design type",
    barmode="stack",
)
fig3.update_layout(height=400, xaxis_tickangle=-45)
st.plotly_chart(fig3, use_container_width=True)
