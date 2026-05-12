import os

from dagster import AssetSelection, Definitions, define_asset_job, load_assets_from_modules

from pubmed_pipeline.assets import analytics, ingestion
from pubmed_pipeline.assets.ingestion import BASELINE_PARTITIONS
from pubmed_pipeline.resources.database import DatabaseResource
from pubmed_pipeline.resources.llm import LLMResource


def _build_llm_resource() -> LLMResource:
    use_local = os.environ.get("USE_LOCAL_LLM", "true").lower() != "false"
    if use_local:
        return LLMResource(
            model=os.environ.get("LOCAL_LLM_MODEL", "ollama/gemma3:4b"),
            api_base=os.environ.get("LOCAL_LLM_API_BASE", "http://ollama:11434"),
        )
    return LLMResource(
        model=os.environ.get("LLM_MODEL", "gemini/gemini-2.0-flash-lite"),
        api_key=os.environ.get("GEMINI_API_KEY") or None,
    )


def _pipeline_db_url() -> str:
    user = os.environ["PIPELINE_DB_USER"]
    password = os.environ["PIPELINE_DB_PASSWORD"]
    host = os.environ["PIPELINE_DB_HOST"]
    port = os.environ.get("PIPELINE_DB_PORT", "5432")
    name = os.environ["PIPELINE_DB_NAME"]
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


_ingestion_job = define_asset_job(
    name="ingestion_job",
    selection=AssetSelection.groups("ingestion"),
    partitions_def=BASELINE_PARTITIONS,
    description=(
        "Download, verify, and parse one PubMed baseline file. "
        "Select a partition (file number 1304–1334) when launching."
    ),
)

_analytics_job = define_asset_job(
    name="analytics_job",
    selection=(
        AssetSelection.groups("analytics_llm")
        | AssetSelection.groups("analytics_metadata")
        | AssetSelection.groups("analytics_combined")
    ),
    description=(
        "Run all analytics in dependency order: "
        "LLM extraction + study design → publication trends + MeSH network → paradigm shifts."
    ),
)

defs = Definitions(
    assets=load_assets_from_modules([ingestion, analytics]),
    jobs=[_ingestion_job, _analytics_job],
    resources={
        "database": DatabaseResource(connection_string=_pipeline_db_url()),
        "llm": _build_llm_resource(),
    },
)
