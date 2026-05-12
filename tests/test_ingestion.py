import hashlib
from pathlib import Path

from pubmed_pipeline.assets.ingestion import _filename, _verify_md5


def test_filename_format() -> None:
    assert _filename(1) == "pubmed26n0001.xml.gz"
    assert _filename(1334) == "pubmed26n1334.xml.gz"
    assert _filename(42) == "pubmed26n0042.xml.gz"


def test_verify_md5_correct(tmp_path: Path) -> None:
    data = b"hello pubmed"
    filepath = tmp_path / "test.gz"
    filepath.write_bytes(data)
    expected = hashlib.md5(data).hexdigest()
    assert _verify_md5(filepath, expected) is True


def test_verify_md5_wrong(tmp_path: Path) -> None:
    filepath = tmp_path / "test.gz"
    filepath.write_bytes(b"actual content")
    assert _verify_md5(filepath, "00000000000000000000000000000000") is False


def test_verify_md5_large_file(tmp_path: Path) -> None:
    data = b"x" * 200_000
    filepath = tmp_path / "large.gz"
    filepath.write_bytes(data)
    expected = hashlib.md5(data).hexdigest()
    assert _verify_md5(filepath, expected) is True
