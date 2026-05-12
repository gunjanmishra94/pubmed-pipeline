import json
from collections import Counter, defaultdict
from typing import Any

from dagster import AssetExecutionContext, Output, asset

from pubmed_pipeline.assets.ingestion import endometriosis_abstracts
from pubmed_pipeline.resources.database import DatabaseResource
from pubmed_pipeline.resources.llm import LLMResource

_LLM_BATCH_SIZE = 20


@asset(
    deps=[endometriosis_abstracts],
    group_name="analytics_llm",
    description=(
        "Use Gemini to extract treatment-outcome pairs from each abstract. "
        "Produces a treatment-outcome matrix with frequency and efficacy direction."
    ),
)
def treatment_outcome_extraction(
    context: AssetExecutionContext,
    database: DatabaseResource,
    llm: LLMResource,
) -> Output[int]:
    rows = database.execute(
        """
        SELECT a.pmid, a.abstract
        FROM abstracts a
        LEFT JOIN treatment_outcomes t ON a.pmid = t.pmid
        WHERE t.pmid IS NULL
        ORDER BY a.pmid
        """
    )
    context.log.info(f"Extracting treatment-outcome pairs from {len(rows)} abstracts")

    processed = 0
    for row in rows:
        pmid = row["pmid"]
        abstract = row["abstract"]
        result = llm.extract_treatment_outcomes(pmid, abstract)

        for extraction in result.extractions:
            database.execute(
                """
                INSERT INTO treatment_outcomes
                    (pmid, treatment, outcome, efficacy_direction, raw_response)
                VALUES (:pmid, :treatment, :outcome, :direction, :raw)
                """,
                {
                    "pmid": pmid,
                    "treatment": extraction.treatment,
                    "outcome": extraction.outcome,
                    "direction": extraction.efficacy_direction,
                    "raw": result.raw_response,
                },
            )
        processed += 1
        if processed % _LLM_BATCH_SIZE == 0:
            context.log.info(f"Processed {processed}/{len(rows)} abstracts")

    context.log.info(f"Treatment-outcome extraction complete: {processed} abstracts")
    return Output(processed, metadata={"abstracts_processed": processed})


@asset(
    deps=[endometriosis_abstracts],
    group_name="analytics_llm",
    description=(
        "Classify each abstract by study design using Gemini. "
        "Tracks how the distribution of study designs has evolved over time."
    ),
)
def study_design_classification(
    context: AssetExecutionContext,
    database: DatabaseResource,
    llm: LLMResource,
) -> Output[int]:
    rows = database.execute(
        """
        SELECT a.pmid, a.abstract
        FROM abstracts a
        LEFT JOIN study_designs sd ON a.pmid = sd.pmid
        WHERE sd.pmid IS NULL
        ORDER BY a.pmid
        """
    )
    context.log.info(f"Classifying study design for {len(rows)} abstracts")

    processed = 0
    for row in rows:
        pmid = row["pmid"]
        result = llm.classify_study_design(pmid, row["abstract"])
        database.execute(
            """
            INSERT INTO study_designs (pmid, design_type, confidence, raw_response)
            VALUES (:pmid, :design, :confidence, :raw)
            ON CONFLICT (pmid) DO NOTHING
            """,
            {
                "pmid": pmid,
                "design": result.design_type,
                "confidence": result.confidence,
                "raw": result.raw_response,
            },
        )
        processed += 1
        if processed % _LLM_BATCH_SIZE == 0:
            context.log.info(f"Classified {processed}/{len(rows)} abstracts")

    context.log.info(f"Study design classification complete: {processed} abstracts")
    return Output(processed, metadata={"abstracts_classified": processed})


@asset(
    deps=[endometriosis_abstracts],
    group_name="analytics_metadata",
    description=(
        "Aggregate publication volume per year and correlate with study design distribution. "
        "Stored in publication_trends for downstream querying."
    ),
)
def publication_trends(
    context: AssetExecutionContext,
    database: DatabaseResource,
) -> Output[dict[int, dict[str, Any]]]:
    rows = database.execute(
        """
        SELECT
            a.publication_year,
            COUNT(*) AS abstract_count,
            COUNT(DISTINCT a.journal) AS unique_journals
        FROM abstracts a
        WHERE a.publication_year IS NOT NULL
        GROUP BY a.publication_year
        ORDER BY a.publication_year
        """
    )

    design_rows = database.execute(
        """
        SELECT a.publication_year, sd.design_type, COUNT(*) AS cnt
        FROM study_designs sd
        JOIN abstracts a ON sd.pmid = a.pmid
        WHERE a.publication_year IS NOT NULL
        GROUP BY a.publication_year, sd.design_type
        """
    )

    rct_by_year: dict[int, int] = defaultdict(int)
    review_by_year: dict[int, int] = defaultdict(int)
    for dr in design_rows:
        yr = dr["publication_year"]
        if dr["design_type"] == "randomized_controlled_trial":
            rct_by_year[yr] += dr["cnt"]
        elif dr["design_type"] in ("systematic_review", "meta_analysis", "narrative_review"):
            review_by_year[yr] += dr["cnt"]

    trend_data = {}
    for row in rows:
        yr = row["publication_year"]
        trend_data[yr] = {
            "abstract_count": row["abstract_count"],
            "unique_journals": row["unique_journals"],
            "rct_count": rct_by_year.get(yr, 0),
            "review_count": review_by_year.get(yr, 0),
        }
        database.execute(
            """
            INSERT INTO publication_trends
                (publication_year, abstract_count, rct_count, review_count, unique_journals)
            VALUES (:yr, :cnt, :rct, :rev, :jrn)
            ON CONFLICT (publication_year) DO UPDATE
                SET abstract_count = EXCLUDED.abstract_count,
                    rct_count = EXCLUDED.rct_count,
                    review_count = EXCLUDED.review_count,
                    unique_journals = EXCLUDED.unique_journals,
                    updated_at = NOW()
            """,
            {
                "yr": yr,
                "cnt": row["abstract_count"],
                "rct": rct_by_year.get(yr, 0),
                "rev": review_by_year.get(yr, 0),
                "jrn": row["unique_journals"],
            },
        )

    context.log.info(f"Publication trends computed for {len(trend_data)} years")
    return Output(trend_data, metadata={"years_covered": len(trend_data)})


@asset(
    deps=[endometriosis_abstracts],
    group_name="analytics_metadata",
    description=(
        "Build a MeSH term co-occurrence matrix. "
        "Each row is a (term_a, term_b, co_count) triple indicating how often two MeSH "
        "descriptors appear together across abstracts."
    ),
)
def mesh_cooccurrence_network(
    context: AssetExecutionContext,
    database: DatabaseResource,
) -> Output[int]:
    rows = database.execute("SELECT mesh_terms FROM abstracts WHERE mesh_terms != '[]'::jsonb")

    co_counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        raw_terms = row["mesh_terms"]
        terms = json.loads(raw_terms) if isinstance(raw_terms, str) else raw_terms
        terms = sorted(set(terms))
        for i, term_a in enumerate(terms):
            for term_b in terms[i + 1 :]:
                co_counts[(term_a, term_b)] += 1

    # Persist only the top 5000 pairs to avoid table explosion
    top_pairs = co_counts.most_common(5000)
    for (term_a, term_b), count in top_pairs:
        database.execute(
            """
            INSERT INTO mesh_cooccurrences (term_a, term_b, co_count)
            VALUES (:a, :b, :cnt)
            ON CONFLICT (term_a, term_b) DO UPDATE
                SET co_count = EXCLUDED.co_count, updated_at = NOW()
            """,
            {"a": term_a, "b": term_b, "cnt": count},
        )

    context.log.info(f"MeSH co-occurrence network: {len(top_pairs)} pairs stored")
    return Output(len(top_pairs), metadata={"pairs_stored": len(top_pairs)})


@asset(
    deps=[treatment_outcome_extraction, publication_trends],
    group_name="analytics_combined",
    description=(
        "Overlay LLM-extracted treatment mentions onto the publication timeline. "
        "Reveals which treatments dominated each era and when new therapies emerged."
    ),
)
def treatment_paradigm_shifts(
    context: AssetExecutionContext,
    database: DatabaseResource,
) -> Output[dict[int, list[dict[str, Any]]]]:
    rows = database.execute(
        """
        SELECT
            a.publication_year,
            t.treatment,
            t.efficacy_direction,
            COUNT(*) AS mention_count
        FROM treatment_outcomes t
        JOIN abstracts a ON t.pmid = a.pmid
        WHERE a.publication_year IS NOT NULL
        GROUP BY a.publication_year, t.treatment, t.efficacy_direction
        ORDER BY a.publication_year, mention_count DESC
        """
    )

    by_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_year[row["publication_year"]].append(
            {
                "treatment": row["treatment"],
                "efficacy_direction": row["efficacy_direction"],
                "mention_count": row["mention_count"],
            }
        )

    top_by_year = {yr: entries[:10] for yr, entries in sorted(by_year.items())}
    context.log.info(f"Treatment paradigm shifts computed across {len(top_by_year)} years")
    return Output(top_by_year, metadata={"years_with_data": len(top_by_year)})
