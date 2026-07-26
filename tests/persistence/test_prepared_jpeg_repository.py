from document_intake.persistence import serialization as ser
from tests.domain.test_prepared_jpeg import artifact


def test_prepared_artifact_canonical_round_trip_has_no_bytes_or_paths() -> None:
    value = artifact()
    payload = ser.prepared_image_artifact_to_json(value)
    assert ser.prepared_image_artifact_from_json(payload) == value
    assert "jpeg_bytes" not in payload and "path" not in payload and "filename" not in payload
