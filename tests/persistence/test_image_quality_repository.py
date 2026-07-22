from pathlib import Path


def test_repository_file_exists() -> None:
    assert Path("src/document_intake/persistence/repositories/image_quality.py").is_file()
