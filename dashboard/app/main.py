import streamlit as st

st.set_page_config(
    page_title="Endometriosis Evidence Pipeline",
    page_icon="🔬",
    layout="wide",
)

st.title("Endometriosis Treatment Evidence Dashboard")
st.markdown(
    """
    Visualisations derived from the PubMed 2025 baseline pipeline.
    Use the sidebar to navigate between views.

    | Page | What it shows |
    |---|---|
    | Treatment Outcomes | Heatmap of treatments × outcomes, coloured by efficacy direction |
    | Publication Trends | Abstract volume per year with RCT fraction overlay |
    | Study Designs | Stacked bar of study design distribution over time |
    | MeSH Network | Force-directed co-occurrence graph of MeSH descriptors |
    | Paradigm Shifts | Top treatments per year as a stacked area chart |
    """
)

rows = st.columns(3)
with rows[0]:
    st.metric("Data source", "PubMed 2025 baseline")
with rows[1]:
    st.metric("Condition", "Endometriosis")
with rows[2]:
    st.metric("Files ingested", "files 1190 – 1219")
