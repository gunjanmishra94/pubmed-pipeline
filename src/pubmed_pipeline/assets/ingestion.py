import hashlib
import json
import re
from pathlib import Path

import requests
from dagster import (
    AssetExecutionContext,
    Output,
    StaticPartitionsDefinition,
    asset,
)
from sqlalchemy import text
from sqlalchemy.engine import Connection

from pubmed_pipeline.models.pubmed import PubMedAbstract
from pubmed_pipeline.resources.database import DatabaseResource
from pubmed_pipeline.utils.xml_parser import parse_pubmed_xml

PUBMED_BASELINE_URL = "https://ftp.ncbi.nlm.nih.gov/pubmed/baseline"
PUBMED_BASELINE_PREFIX = "pubmed26n"

# 2026 baseline: files 1334 → 1305 (30 most recent). Adjust range as needed.
BASELINE_PARTITIONS = StaticPartitionsDefinition([str(i) for i in range(1334, 1304, -1)])


def _filename(file_number: int) -> str:
    return f"{PUBMED_BASELINE_PREFIX}{file_number:04d}.xml.gz"


def _verify_md5(filepath: Path, expected_md5: str) -> bool:
    hasher = hashlib.md5()
    with filepath.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest() == expected_md5


def _fetch_expected_md5(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    match = re.search(r"([a-f0-9]{32})", response.text)
    if not match:
        raise ValueError(f"Could not parse MD5 from {url}")
    return match.group(1)


def _download_file(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                fh.write(chunk)


@asset(
    partitions_def=BASELINE_PARTITIONS,
    group_name="ingestion",
    description="Download and MD5-verify a single PubMed baseline .xml.gz file.",
)
def pubmed_baseline_file(
    context: AssetExecutionContext,
    database: DatabaseResource,
) -> Output[Path]:
    file_number = int(context.partition_key)
    filename = _filename(file_number)

    database.initialize_schema()

    data_dir = Path("/app/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    dest = data_dir / filename

    if database.file_already_parsed(filename):
        context.log.info(f"{filename} already parsed — skipping download")
        return Output(dest, metadata={"skipped": True, "filename": filename})

    if not dest.exists():
        context.log.info(f"Downloading {filename}")
        file_url = f"{PUBMED_BASELINE_URL}/{filename}"
        md5_url = f"{file_url}.md5"

        expected_md5 = _fetch_expected_md5(md5_url)
        _download_file(file_url, dest)

        if not _verify_md5(dest, expected_md5):
            dest.unlink()
            raise ValueError(f"MD5 mismatch for {filename}")

        database.execute(
            """
            INSERT INTO pipeline_files (filename, file_number, md5_verified)
            VALUES (:fn, :num, TRUE)
            ON CONFLICT (filename) DO UPDATE SET md5_verified = TRUE
            """,
            {"fn": filename, "num": file_number},
        )
        context.log.info(f"Downloaded and verified {filename}")
    else:
        context.log.info(f"{filename} already on disk")

    return Output(dest, metadata={"filename": filename, "file_number": file_number})


def _insert_abstract(conn: Connection, record: PubMedAbstract) -> None:
    conn.execute(
        text("""
            INSERT INTO abstracts
                (pmid, title, abstract, authors, affiliations, publication_year,
                 publication_date, journal, mesh_terms, grant_ids, source_file)
            VALUES
                (:pmid, :title, :abstract,
                 CAST(:authors AS jsonb), CAST(:affiliations AS jsonb),
                 :year, :pub_date, :journal,
                 CAST(:mesh_terms AS jsonb), CAST(:grant_ids AS jsonb),
                 :source_file)
            ON CONFLICT (pmid) DO NOTHING
        """),
        {
            "pmid": record.pmid,
            "title": record.title,
            "abstract": record.abstract,
            "authors": json.dumps([a.model_dump() for a in record.authors]),
            "affiliations": json.dumps(record.affiliations),
            "year": record.publication_year,
            "pub_date": record.publication_date,
            "journal": record.journal,
            "mesh_terms": json.dumps(record.mesh_terms),
            "grant_ids": json.dumps(record.grant_ids),
            "source_file": record.source_file,
        },
    )


@asset(
    partitions_def=BASELINE_PARTITIONS,
    deps=[pubmed_baseline_file],
    group_name="ingestion",
    description="Parse the downloaded XML file, filter for endometriosis, and store abstracts.",
)
def endometriosis_abstracts(
    context: AssetExecutionContext,
    database: DatabaseResource,
) -> Output[int]:
    file_number = int(context.partition_key)
    filename = _filename(file_number)

    if database.file_already_parsed(filename):
        context.log.info(f"{filename} already parsed — skipping")
        rows = database.execute(
            "SELECT filtered_records FROM pipeline_files WHERE filename = :fn",
            {"fn": filename},
        )
        count = rows[0]["filtered_records"] if rows else 0
        return Output(count, metadata={"skipped": True, "filtered_records": count})

    filepath = Path("/app/data") / filename
    if not filepath.exists():
        raise FileNotFoundError(f"{filepath} not found — run pubmed_baseline_file first")

    database.initialize_schema()

    total = 0
    filtered = 0
    engine = database.get_engine()
    with engine.connect() as conn:
        for record in parse_pubmed_xml(filepath, filename):
            _insert_abstract(conn, record)
            filtered += 1
            total += 1
            if filtered % 500 == 0:
                conn.commit()
                context.log.info(f"Inserted {filtered} endometriosis records so far")
        conn.commit()

    database.execute(
        """
        UPDATE pipeline_files
        SET parsed_at = NOW(), total_records = :total, filtered_records = :filtered
        WHERE filename = :fn
        """,
        {"fn": filename, "total": total, "filtered": filtered},
    )

    context.log.info(f"{filename}: {filtered} endometriosis abstracts stored")
    return Output(
        filtered,
        metadata={"filtered_records": filtered, "filename": filename},
    )
