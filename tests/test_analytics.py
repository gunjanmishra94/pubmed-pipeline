import json
from unittest.mock import patch

import pytest

from pubmed_pipeline.resources.llm import LLMResource, _extract_json


@pytest.mark.parametrize(
    "raw, expected",
    [
        (
            '[{"treatment": "A", "outcome": "B", "efficacy_direction": "positive"}]',
            '[{"treatment": "A", "outcome": "B", "efficacy_direction": "positive"}]',
        ),
        ('```json\n[{"treatment": "X"}]\n```', '[{"treatment": "X"}]'),
        ('```\n[{"treatment": "Y"}]\n```', '[{"treatment": "Y"}]'),
        ("  [{}]  ", "[{}]"),
    ],
)
def test_extract_json(raw: str, expected: str) -> None:
    assert _extract_json(raw) == expected


def test_extract_treatment_outcomes_valid_json() -> None:
    llm = LLMResource(api_key="test", model="gemini/gemini-2.0-flash")
    mock_response = json.dumps(
        [
            {"treatment": "dienogest", "outcome": "pelvic pain", "efficacy_direction": "positive"},
            {
                "treatment": "laparoscopy",
                "outcome": "recurrence rate",
                "efficacy_direction": "positive",
            },
        ]
    )
    with patch("pubmed_pipeline.resources.llm.LLMResource._call", return_value=mock_response):
        result = llm.extract_treatment_outcomes(12345, "sample abstract")

    assert len(result.extractions) == 2
    assert result.extractions[0].treatment == "dienogest"
    assert result.extractions[0].efficacy_direction == "positive"
    assert result.pmid == 12345


def test_extract_treatment_outcomes_malformed_json() -> None:
    llm = LLMResource(api_key="test", model="gemini/gemini-2.0-flash")
    with patch("pubmed_pipeline.resources.llm.LLMResource._call", return_value="not json at all"):
        result = llm.extract_treatment_outcomes(99, "abstract")
    assert result.extractions == []
    assert result.raw_response == "not json at all"


def test_extract_treatment_outcomes_empty_list() -> None:
    llm = LLMResource(api_key="test", model="gemini/gemini-2.0-flash")
    with patch("pubmed_pipeline.resources.llm.LLMResource._call", return_value="[]"):
        result = llm.extract_treatment_outcomes(1, "no treatments here")
    assert result.extractions == []


def test_classify_study_design_valid() -> None:
    llm = LLMResource(api_key="test", model="gemini/gemini-2.0-flash")
    mock_response = json.dumps({"design_type": "randomized_controlled_trial", "confidence": "high"})
    with patch("pubmed_pipeline.resources.llm.LLMResource._call", return_value=mock_response):
        result = llm.classify_study_design(1, "RCT abstract")

    assert result.design_type == "randomized_controlled_trial"
    assert result.confidence == "high"


def test_classify_study_design_fallback_on_bad_json() -> None:
    llm = LLMResource(api_key="test", model="gemini/gemini-2.0-flash")
    with patch("pubmed_pipeline.resources.llm.LLMResource._call", return_value="```broken```"):
        result = llm.classify_study_design(1, "abstract")
    assert result.design_type == "other"
    assert result.confidence == "low"
