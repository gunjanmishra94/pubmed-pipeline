from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from dagster import ConfigurableResource
from sqlalchemy import Engine, create_engine, text

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS pipeline_files (
    filename        VARCHAR(100) PRIMARY KEY,
    file_number     INTEGER NOT NULL,
    downloaded_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    parsed_at       TIMESTAMP,
    total_records   INTEGER,
    filtered_records INTEGER,
    md5_verified    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS abstracts (
    pmid             BIGINT PRIMARY KEY,
    title            TEXT,
    abstract         TEXT,
    authors          JSONB,
    affiliations     JSONB,
    publication_year INTEGER,
    publication_date DATE,
    journal          VARCHAR(500),
    mesh_terms       JSONB,
    grant_ids        JSONB,
    source_file      VARCHAR(100),
    created_at       TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_abstracts_year ON abstracts (publication_year);
CREATE INDEX IF NOT EXISTS idx_abstracts_source ON abstracts (source_file);

CREATE TABLE IF NOT EXISTS treatment_outcomes (
    id                  SERIAL PRIMARY KEY,
    pmid                BIGINT NOT NULL REFERENCES abstracts(pmid),
    treatment           TEXT NOT NULL,
    outcome             TEXT NOT NULL,
    efficacy_direction  VARCHAR(50) NOT NULL,
    raw_response        TEXT,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_treatment_pmid ON treatment_outcomes (pmid);
CREATE INDEX IF NOT EXISTS idx_treatment_name ON treatment_outcomes (treatment);

CREATE TABLE IF NOT EXISTS study_designs (
    pmid         BIGINT PRIMARY KEY REFERENCES abstracts(pmid),
    design_type  VARCHAR(100) NOT NULL,
    confidence   VARCHAR(20) NOT NULL,
    raw_response TEXT,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS publication_trends (
    publication_year  INTEGER PRIMARY KEY,
    abstract_count    INTEGER NOT NULL,
    rct_count         INTEGER NOT NULL DEFAULT 0,
    review_count      INTEGER NOT NULL DEFAULT 0,
    unique_journals   INTEGER NOT NULL DEFAULT 0,
    updated_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mesh_cooccurrences (
    term_a      VARCHAR(500) NOT NULL,
    term_b      VARCHAR(500) NOT NULL,
    co_count    INTEGER NOT NULL DEFAULT 0,
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (term_a, term_b)
);
"""


class DatabaseResource(ConfigurableResource[Any]):
    connection_string: str

    def get_engine(self) -> Engine:
        return create_engine(self.connection_string, pool_pre_ping=True)

    def initialize_schema(self) -> None:
        engine = self.get_engine()
        with engine.connect() as conn:
            conn.execute(text(_CREATE_TABLES))
            conn.commit()

    @contextmanager
    def connect(self) -> Generator[Any, None, None]:
        engine = self.get_engine()
        with engine.connect() as conn:
            yield conn

    def execute(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        engine = self.get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            if result.returns_rows:
                columns = list(result.keys())
                return [dict(zip(columns, row)) for row in result.fetchall()]
            return []

    def file_already_parsed(self, filename: str) -> bool:
        rows = self.execute(
            "SELECT 1 FROM pipeline_files WHERE filename = :fn AND parsed_at IS NOT NULL",
            {"fn": filename},
        )
        return len(rows) > 0
