import gzip
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from lxml import etree

from pubmed_pipeline.models.pubmed import Author, PubMedAbstract

ENDOMETRIOSIS_MESH_TERMS = {"Endometriosis"}
ENDOMETRIOSIS_KEYWORDS = frozenset(
    ["endometriosis", "endometrioma", "adenomyosis", "endometrial implant"]
)


def _parse_pub_date(article: etree._Element) -> tuple[int | None, date | None]:
    pub_date = article.find(".//PubDate")
    if pub_date is None:
        return None, None
    year_el = pub_date.find("Year")
    month_el = pub_date.find("Month")
    day_el = pub_date.find("Day")
    medline_date_el = pub_date.find("MedlineDate")

    year: int | None = None
    if year_el is not None and year_el.text:
        try:
            year = int(year_el.text)
        except ValueError:
            pass
    elif medline_date_el is not None and medline_date_el.text:
        try:
            year = int(medline_date_el.text[:4])
        except ValueError:
            pass

    if year is None:
        return None, None

    month_str = month_el.text if month_el is not None else None
    day_str = day_el.text if day_el is not None else None

    month_map = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }
    try:
        month = month_map.get(month_str or "", None) or int(month_str or "1")
        day = int(day_str or "1")
        return year, date(year, month, day)
    except (ValueError, KeyError):
        return year, None


def _parse_abstract_text(article: etree._Element) -> str:
    abstract_el = article.find(".//Abstract")
    if abstract_el is None:
        return ""
    parts = []
    for el in abstract_el.findall("AbstractText"):
        label = el.get("Label")
        text = "".join(el.itertext()).strip()
        if label:
            parts.append(f"{label}: {text}")
        else:
            parts.append(text)
    return " ".join(parts)


def _parse_authors(article: etree._Element) -> tuple[list[Author], list[str]]:
    authors = []
    affiliations = []
    affiliation_set: set[str] = set()

    for author_el in article.findall(".//Author"):
        last = author_el.findtext("LastName") or ""
        fore = author_el.findtext("ForeName") or author_el.findtext("Initials")
        aff_els = author_el.findall(".//AffiliationInfo/Affiliation")
        aff = aff_els[0].text if aff_els and aff_els[0].text else None
        authors.append(Author(last_name=last, fore_name=fore, affiliation=aff))
        if aff and aff not in affiliation_set:
            affiliations.append(aff)
            affiliation_set.add(aff)

    return authors, affiliations


def _is_endometriosis_related(mesh_terms: list[str], title: str, abstract: str) -> bool:
    if ENDOMETRIOSIS_MESH_TERMS.intersection(mesh_terms):
        return True
    combined = (title + " " + abstract).lower()
    return any(kw in combined for kw in ENDOMETRIOSIS_KEYWORDS)


def parse_pubmed_xml(filepath: Path, source_file: str) -> Iterator[PubMedAbstract]:
    open_fn = gzip.open if filepath.suffix == ".gz" else open
    with open_fn(filepath, "rb") as fh:
        for _, element in etree.iterparse(fh, events=("end",), tag="PubmedArticle"):
            try:
                record = _parse_article(element, source_file)
                if record is not None:
                    yield record
            finally:
                element.clear()


def _parse_article(element: etree._Element, source_file: str) -> PubMedAbstract | None:
    citation = element.find("MedlineCitation")
    if citation is None:
        return None

    pmid_el = citation.find("PMID")
    if pmid_el is None or not pmid_el.text:
        return None
    try:
        pmid = int(pmid_el.text)
    except ValueError:
        return None

    article = citation.find("Article")
    if article is None:
        return None

    title_el = article.find("ArticleTitle")
    title = "".join(title_el.itertext()) if title_el is not None else ""
    abstract = _parse_abstract_text(article)

    if not abstract:
        return None

    mesh_terms = [
        el.text
        for el in citation.findall(".//MeshHeadingList/MeshHeading/DescriptorName")
        if el.text
    ]

    if not _is_endometriosis_related(mesh_terms, title, abstract):
        return None

    authors, affiliations = _parse_authors(article)

    journal_el = article.find(".//Journal/Title")
    journal = journal_el.text if journal_el is not None else None

    pub_year, pub_date = _parse_pub_date(article)

    grant_ids = [el.text for el in citation.findall(".//GrantList/Grant/GrantID") if el.text]

    return PubMedAbstract(
        pmid=pmid,
        title=title,
        abstract=abstract,
        authors=authors,
        affiliations=affiliations,
        publication_year=pub_year,
        publication_date=pub_date,
        journal=journal,
        mesh_terms=mesh_terms,
        grant_ids=grant_ids,
        source_file=source_file,
    )
