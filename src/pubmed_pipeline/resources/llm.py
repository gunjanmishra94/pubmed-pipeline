import json
import re
import time
from typing import Any

import litellm
from dagster import ConfigurableResource

from pubmed_pipeline.models.pubmed import (
    StudyDesignExtractionResult,
    TreatmentOutcome,
    TreatmentOutcomeExtractionResult,
)

_TREATMENT_OUTCOME_PROMPT = """\
You are a biomedical information extraction system specializing in endometriosis research.

Extract all treatment-outcome pairs from the abstract below. A treatment is any drug,
surgery, procedure, or therapeutic intervention. An outcome is any measured endpoint
(pain score, pregnancy rate, lesion size, quality of life, etc.).

For each pair, classify efficacy_direction as:
- "positive": treatment improved the outcome
- "negative": treatment worsened or failed to improve the outcome
- "neutral": no significant difference detected
- "mixed": conflicting or dose-dependent results
- "unclear": outcome direction not stated

Return ONLY a JSON array. If no treatments are mentioned, return [].

Example format: [{"treatment": "dienogest", "outcome": "pelvic pain",
"efficacy_direction": "positive"}]

Abstract:
__ABSTRACT__"""

_STUDY_DESIGN_PROMPT = """Classify the study design of this biomedical abstract.

Choose exactly one design_type from:
- randomized_controlled_trial
- cohort_study
- case_control_study
- cross_sectional
- meta_analysis
- systematic_review
- case_report
- case_series
- narrative_review
- other

Return ONLY valid JSON with fields design_type and confidence (high/medium/low).

Example: {"design_type": "cohort_study", "confidence": "high"}

Abstract:
__ABSTRACT__"""

_RETRY_DELAYS = [10, 30, 60]


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


class LLMResource(ConfigurableResource[Any]):
    model: str = "ollama/gemma3:4b"
    api_base: str = "http://ollama:11434"
    api_key: str | None = None

    def _call(self, prompt: str) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }
        if self.model.startswith("ollama/"):
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key

        for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
            try:
                response = litellm.completion(**kwargs)
                return response.choices[0].message.content or ""
            except litellm.RateLimitError:  # type: ignore[attr-defined]
                if attempt == len(_RETRY_DELAYS):
                    raise
                time.sleep(delay)
        return ""

    def extract_treatment_outcomes(
        self, pmid: int, abstract: str
    ) -> TreatmentOutcomeExtractionResult:
        raw = self._call(_TREATMENT_OUTCOME_PROMPT.replace("__ABSTRACT__", abstract))
        try:
            data = json.loads(_extract_json(raw))
            extractions = [TreatmentOutcome(**item) for item in data if isinstance(item, dict)]
        except (json.JSONDecodeError, TypeError, ValueError):
            extractions = []
        return TreatmentOutcomeExtractionResult(
            pmid=pmid, extractions=extractions, raw_response=raw
        )

    def classify_study_design(self, pmid: int, abstract: str) -> StudyDesignExtractionResult:
        raw = self._call(_STUDY_DESIGN_PROMPT.replace("__ABSTRACT__", abstract))
        try:
            data = json.loads(_extract_json(raw))
            design_type = str(data.get("design_type", "other"))
            confidence = str(data.get("confidence", "low"))
        except (json.JSONDecodeError, AttributeError):
            design_type = "other"
            confidence = "low"
        return StudyDesignExtractionResult(
            pmid=pmid, design_type=design_type, confidence=confidence, raw_response=raw
        )
