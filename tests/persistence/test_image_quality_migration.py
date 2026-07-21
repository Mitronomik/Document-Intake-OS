from document_intake.persistence.migrations.v0005_image_quality import MIGRATION


def test_v0005_metadata() -> None:
    assert MIGRATION.version == 5
    assert MIGRATION.name == "image_quality_pr009"
    assert MIGRATION.checksum == "6d020d1acfbce3fcb7168e935617f2ae008a32bea7def1f37de84e36e9e2224f"
    assert any("ordinal BETWEEN 0 AND 5" in s for s in MIGRATION.statements)
