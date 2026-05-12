from pathlib import Path

import pytest

from pubmed_pipeline.utils.xml_parser import (
    _is_endometriosis_related,
    parse_pubmed_xml,
)


def test_parse_returns_only_endometriosis_records(sample_xml_gz: Path) -> None:
    records = list(parse_pubmed_xml(sample_xml_gz, "pubmed26n1334.xml.gz"))
    assert len(records) == 1
    assert records[0].pmid == 12345678


def test_parsed_record_fields(sample_xml_gz: Path) -> None:
    record = list(parse_pubmed_xml(sample_xml_gz, "pubmed26n1334.xml.gz"))[0]

    assert record.title == "Endometriosis excision vs ablation: a randomized trial"
    assert "endometriosis" in record.abstract.lower()
    assert record.publication_year == 2022
    assert record.journal == "Fertility and Sterility"
    assert "Endometriosis" in record.mesh_terms
    assert "Laparoscopy" in record.mesh_terms
    assert record.grant_ids == ["R01 HD098765"]
    assert len(record.authors) == 1
    assert record.authors[0].last_name == "Smith"
    assert record.authors[0].fore_name == "Jane"
    assert "Stanford" in (record.authors[0].affiliation or "")


def test_diabetes_record_excluded(sample_xml_gz: Path) -> None:
    records = list(parse_pubmed_xml(sample_xml_gz, "pubmed25n1219.xml.gz"))
    pmids = [r.pmid for r in records]
    assert 99999999 not in pmids


def test_plain_xml_file(sample_xml: Path) -> None:
    records = list(parse_pubmed_xml(sample_xml, "sample.xml"))
    assert len(records) == 1


@pytest.mark.parametrize(
    "mesh_terms, title, abstract, expected",
    [
        (["Endometriosis"], "", "", True),
        ([], "Endometriosis pain study", "", True),
        ([], "", "patients with endometrioma were enrolled", True),
        ([], "Diabetes study", "insulin therapy improved glucose", False),
        ([], "", "adenomyosis lesions were observed", True),
    ],
)
def test_is_endometriosis_related(
    mesh_terms: list[str], title: str, abstract: str, expected: bool
) -> None:
    assert _is_endometriosis_related(mesh_terms, title, abstract) == expected
