import gzip
import textwrap
from pathlib import Path

import pytest

SAMPLE_ENDO_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE PubmedArticleSet SYSTEM "http://dtd.nlm.nih.gov/ncbi/pubmed/doc/out/250101/pubmed.dtd">
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation Status="MEDLINE" Owner="NLM">
          <PMID Version="1">12345678</PMID>
          <Article PubModel="Print">
            <Journal>
              <Title>Fertility and Sterility</Title>
              <JournalIssue CitedMedium="Internet">
                <PubDate><Year>2022</Year><Month>Jun</Month><Day>15</Day></PubDate>
              </JournalIssue>
            </Journal>
            <ArticleTitle>Endometriosis excision vs ablation: a randomized trial</ArticleTitle>
            <Abstract>
              <AbstractText Label="OBJECTIVE">
                To compare pain outcomes after excision versus ablation for endometriosis.
              </AbstractText>
              <AbstractText Label="RESULTS">
                Excision significantly reduced pelvic pain scores compared to ablation (p&lt;0.01).
                Dienogest administered postoperatively reduced recurrence rates.
              </AbstractText>
            </Abstract>
            <AuthorList CompleteYN="Y">
              <Author ValidYN="Y">
                <LastName>Smith</LastName>
                <ForeName>Jane</ForeName>
                <AffiliationInfo>
                  <Affiliation>Department of Gynecology, Stanford University, CA, USA</Affiliation>
                </AffiliationInfo>
              </Author>
            </AuthorList>
          </Article>
          <MeshHeadingList>
            <MeshHeading>
              <DescriptorName UI="D004715" MajorTopicYN="Y">Endometriosis</DescriptorName>
            </MeshHeading>
            <MeshHeading>
              <DescriptorName UI="D010535" MajorTopicYN="N">Laparoscopy</DescriptorName>
            </MeshHeading>
          </MeshHeadingList>
          <GrantList CompleteYN="Y">
            <Grant>
              <GrantID>R01 HD098765</GrantID>
              <Agency>NICHD NIH HHS</Agency>
            </Grant>
          </GrantList>
        </MedlineCitation>
        <PubmedData>
          <PublicationStatus>ppublish</PublicationStatus>
        </PubmedData>
      </PubmedArticle>
      <PubmedArticle>
        <MedlineCitation Status="MEDLINE" Owner="NLM">
          <PMID Version="1">99999999</PMID>
          <Article PubModel="Print">
            <Journal>
              <Title>Diabetes Care</Title>
              <JournalIssue CitedMedium="Internet">
                <PubDate><Year>2022</Year><Month>Jan</Month></PubDate>
              </JournalIssue>
            </Journal>
            <ArticleTitle>Insulin therapy in type 2 diabetes</ArticleTitle>
            <Abstract>
              <AbstractText>Insulin glargine improved HbA1c in type 2 diabetes.</AbstractText>
            </Abstract>
            <AuthorList CompleteYN="Y">
              <Author ValidYN="Y">
                <LastName>Jones</LastName>
                <ForeName>Bob</ForeName>
              </Author>
            </AuthorList>
          </Article>
          <MeshHeadingList>
            <MeshHeading>
              <DescriptorName UI="D003924">Diabetes Mellitus, Type 2</DescriptorName>
            </MeshHeading>
          </MeshHeadingList>
        </MedlineCitation>
        <PubmedData>
          <PublicationStatus>ppublish</PublicationStatus>
        </PubmedData>
      </PubmedArticle>
    </PubmedArticleSet>
""")


@pytest.fixture
def sample_xml_gz(tmp_path: Path) -> Path:
    gz_path = tmp_path / "pubmed26n1334.xml.gz"
    with gzip.open(gz_path, "wb") as fh:
        fh.write(SAMPLE_ENDO_XML.encode())
    return gz_path


@pytest.fixture
def sample_xml(tmp_path: Path) -> Path:
    xml_path = tmp_path / "sample.xml"
    xml_path.write_text(SAMPLE_ENDO_XML)
    return xml_path
