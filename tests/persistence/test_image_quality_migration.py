from document_intake.persistence.migrations.v0005_image_quality import MIGRATION


def test_v0005_metadata() -> None:
    assert MIGRATION.version == 5
    assert MIGRATION.name == "image_quality_pr009"
    assert MIGRATION.checksum == "74f6376fbfd42ed4b9748cadd936daba3c26755a04ddc7cedee76ed2143d95f2"
    assert any("ordinal BETWEEN 0 AND 5" in s for s in MIGRATION.statements)
