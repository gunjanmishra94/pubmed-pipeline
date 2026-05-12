from datetime import date

from pydantic import BaseModel, Field


class Author(BaseModel):
    last_name: str
    fore_name: str | None = None
    affiliation: str | None = None


class PubMedAbstract(BaseModel):
    pmid: int
    title: str
    abstract: str
    authors: list[Author] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    publication_date: date | None = None
    journal: str | None = None
    mesh_terms: list[str] = Field(default_factory=list)
    grant_ids: list[str] = Field(default_factory=list)
    source_file: str


class TreatmentOutcome(BaseModel):
    treatment: str
    outcome: str
    efficacy_direction: str


class TreatmentOutcomeExtractionResult(BaseModel):
    pmid: int
    extractions: list[TreatmentOutcome]
    raw_response: str


class StudyDesignExtractionResult(BaseModel):
    pmid: int
    design_type: str
    confidence: str
    raw_response: str


class FileIngestionRecord(BaseModel):
    filename: str
    file_number: int
    md5_verified: bool
    total_records: int
    filtered_records: int
