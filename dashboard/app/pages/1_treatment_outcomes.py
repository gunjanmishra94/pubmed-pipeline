import sys

import plotly.express as px
import streamlit as st

sys.path.insert(0, "/app")
from db import query

st.set_page_config(page_title="Treatment Outcomes", layout="wide")
st.title("Treatment-Outcome Matrix")

df = query("""
    SELECT treatment, outcome, efficacy_direction, COUNT(*) AS mentions
    FROM treatment_outcomes
    GROUP BY treatment, outcome, efficacy_direction
""")

if df.empty:
    st.info("No extraction data yet — run the treatment_outcome_extraction asset first.")
    st.stop()

top_n = st.slider("Show top N treatments by total mentions", 5, 30, 15)

top_treatments = df.groupby("treatment")["mentions"].sum().nlargest(top_n).index.tolist()
df = df[df["treatment"].isin(top_treatments)]

pivot = df.groupby(["treatment", "outcome"])["mentions"].sum().reset_index()
top_outcomes = pivot.groupby("outcome")["mentions"].sum().nlargest(20).index
pivot = pivot[pivot["outcome"].isin(top_outcomes)]

matrix = pivot.pivot(index="treatment", columns="outcome", values="mentions").fillna(0)

fig = px.imshow(
    matrix,
    labels={"color": "Mentions"},
    color_continuous_scale="Blues",
    aspect="auto",
    title="Treatment × Outcome co-mention frequency",
)
fig.update_layout(height=600)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Efficacy Direction Breakdown")
direction_counts = df.groupby(["treatment", "efficacy_direction"])["mentions"].sum().reset_index()
direction_counts = direction_counts[direction_counts["treatment"].isin(top_treatments)]

fig2 = px.bar(
    direction_counts,
    x="treatment",
    y="mentions",
    color="efficacy_direction",
    color_discrete_map={
        "positive": "#2ecc71",
        "negative": "#e74c3c",
        "neutral": "#95a5a6",
        "mixed": "#f39c12",
        "unclear": "#bdc3c7",
    },
    title="Efficacy direction per treatment",
    labels={"mentions": "Extraction count", "treatment": "Treatment"},
)
fig2.update_layout(height=450, xaxis_tickangle=-45)
st.plotly_chart(fig2, use_container_width=True)
