from document_intake.persistence import serialization as ser
from document_intake.persistence.database import PreparedImageArtifactRepo
from tests.domain.test_prepared_jpeg import artifact


def test_prepared_artifact_canonical_round_trip_has_no_bytes_or_paths() -> None:
    value = artifact()
    payload = ser.prepared_image_artifact_to_json(value)
    assert ser.prepared_image_artifact_from_json(payload) == value
    assert all(marker not in payload for marker in ("jpeg_bytes", "path", "filename"))


def test_repository_surface_is_create_once() -> None:
    assert hasattr(PreparedImageArtifactRepo, "add") and hasattr(PreparedImageArtifactRepo, "get")
    assert not hasattr(PreparedImageArtifactRepo, "update")
    assert not hasattr(PreparedImageArtifactRepo, "delete")
    assert not hasattr(PreparedImageArtifactRepo, "replace")
