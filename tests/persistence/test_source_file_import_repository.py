from document_intake.persistence.migrations import CURRENT_SCHEMA_VERSION


def test_schema_version_is_pr008():
    assert CURRENT_SCHEMA_VERSION == 4
