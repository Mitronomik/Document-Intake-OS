from __future__ import annotations

import ast
import inspect
import io

from PIL import Image
from scripts import verify_pr009_quality as verifier


def _passing_run() -> verifier._Run:
    return verifier._Run(dict.fromkeys(verifier._CHECKS, True))


def test_pr009_verifier_exact_success_output_and_exit_zero(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(verifier, "_unsupported_code", lambda: None)
    monkeypatch.setattr(verifier, "_run_supported", _passing_run)
    assert verifier.main() == 0
    assert tuple(capsys.readouterr().out.splitlines()) == verifier._SUCCESS_LINES


def test_pr009_verifier_unsupported_exit_two_has_no_false_pass(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(verifier, "_unsupported_code", lambda: "UNSUPPORTED_PLATFORM")
    assert verifier.main() == 2
    output = capsys.readouterr().out
    assert output == "PR009_VERIFY result=INCONCLUSIVE code=UNSUPPORTED_PLATFORM\n"
    assert "PASS" not in output


def test_pr009_verifier_product_failure_exit_one_is_allowlisted(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(verifier, "_unsupported_code", lambda: None)
    statuses = dict.fromkeys(verifier._CHECKS, True)
    statuses["quality_decoder"] = False
    monkeypatch.setattr(verifier, "_run_supported", lambda: verifier._Run(statuses))
    assert verifier.main() == 1
    lines = tuple(capsys.readouterr().out.splitlines())
    assert verifier._has_allowlisted_shape(lines)
    assert "PR009_VERIFY quality_decoder=FAIL" in lines
    assert lines[-1] == "PR009_VERIFY result=FAIL"


def test_pr009_unexpected_failure_does_not_render_exception_text(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(verifier, "_unsupported_code", lambda: None)

    def fail() -> verifier._Run:
        raise RuntimeError("SYNTHETIC_SECRET_PATH SQL key material")

    monkeypatch.setattr(verifier, "_run_supported", fail)
    assert verifier.main() == 1
    assert capsys.readouterr().out == "PR009_VERIFY result=FAIL\n"


def test_pr009_failure_rendering_rejects_non_allowlisted_or_private_output() -> None:
    statuses = dict.fromkeys(verifier._CHECKS, True)
    statuses["audit"] = False
    lines = verifier._render(statuses)
    assert verifier._privacy_safe(lines, forbidden_values=("synthetic-private-marker",))
    assert not verifier._privacy_safe(
        (*lines[:-1], "synthetic-private-marker"),
        forbidden_values=("synthetic-private-marker",),
    )
    assert not verifier._has_allowlisted_shape(("PR009_VERIFY persistence=PASS",))


def test_pr009_import_and_quality_vectors_are_literal_frozen_values() -> None:
    assert verifier._EXPECTED_DHASH64 == "18e0e0e0f10f0f07"
    assert (
        bytes(
            [
                37,
                38,
                41,
                41,
                27,
                0,
                0,
                0,
                0,
                34,
                33,
                31,
                30,
                33,
                42,
                52,
                59,
                59,
                36,
                33,
                25,
                23,
                52,
                112,
                170,
                209,
                210,
                72,
                66,
                53,
                47,
                74,
                138,
                203,
                247,
                247,
                119,
                115,
                109,
                103,
                100,
                106,
                115,
                122,
                117,
                106,
                118,
                137,
                161,
                164,
                137,
                99,
                70,
                56,
                55,
                84,
                131,
                192,
                230,
                212,
                165,
                124,
                102,
                21,
                59,
                121,
                202,
                255,
                255,
                210,
                166,
                140,
            ]
        )
        == verifier._EXPECTED_IMPORT_GRAYSCALE
    )
    assert (
        bytes([36, 29, 0, 44, 64, 255, 124, 128, 76, 69, 250, 150])
        == verifier._EXPECTED_QUALITY_GRAYSCALE
    )
    assert verifier._EXPECTED_ENCODED_DIMENSIONS == (4, 3)
    assert verifier._EXPECTED_EFFECTIVE_DIMENSIONS == (3, 4)
    assert verifier._EXPECTED_EXIF_ORIENTATION == 6


def test_pr009_seven_metric_vector_is_literal_and_complete() -> None:
    assert verifier._EXPECTED_METRICS == (
        ("SHORT_SIDE_PIXELS", "RESOLUTION_V1", 1, "3", "PIXELS"),
        ("LONG_SIDE_PIXELS", "RESOLUTION_V1", 1, "4", "PIXELS"),
        ("LAPLACIAN_VARIANCE", "BLUR_LAPLACIAN_V1", 1, "9801.000000", "VARIANCE"),
        (
            "LUMINANCE_STANDARD_DEVIATION",
            "CONTRAST_STDDEV_V1",
            1,
            "79.287933",
            "LUMA_LEVEL",
        ),
        (
            "HIGHLIGHT_CLIPPED_FRACTION",
            "GLARE_CLIPPED_FRACTION_V1",
            1,
            "0.16666667",
            "FRACTION",
        ),
        (
            "SHADOW_CLIPPED_FRACTION",
            "EXPOSURE_CLIPPED_FRACTION_V1",
            1,
            "0.16666667",
            "FRACTION",
        ),
        (
            "BRIGHT_CLIPPED_FRACTION",
            "EXPOSURE_CLIPPED_FRACTION_V1",
            1,
            "0.16666667",
            "FRACTION",
        ),
    )
    assert len(verifier._EXPECTED_METRICS) == 7


def test_pr009_expected_vectors_are_not_generated_by_production_calculators() -> None:
    module_source = inspect.getsource(verifier)
    tree = ast.parse(module_source)
    assignments = {
        node.targets[0].id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    assert isinstance(assignments["_EXPECTED_DHASH64"], ast.Constant)
    assert isinstance(assignments["_EXPECTED_IMPORT_GRAYSCALE"], ast.Constant)
    assert isinstance(assignments["_EXPECTED_QUALITY_GRAYSCALE"], ast.Constant)
    assert isinstance(assignments["_EXPECTED_METRICS"], ast.Tuple)
    assert "calculate_quality_metrics" not in module_source
    assert "derive_quality_issues_and_status" not in module_source


def test_pr009_verifier_uses_required_production_components_and_services() -> None:
    source = inspect.getsource(verifier._run_supported)
    for required in (
        "EncryptedDatabase(",
        "ImmutableFilesystemStorage(",
        "create_upload_batch(",
        "import_source_files(",
        "PillowMediaDecoder()",
        "assess_source_file_quality(",
        "database.unit_of_work()",
        "uow.image_quality_assessments.get(",
        "uow.audit_events.get(",
    ):
        assert required in source


def test_pr009_verifier_proves_mpo_primary_frame_through_production_flow() -> None:
    content = verifier._synthetic_mpo(primary_variant=1, secondary_variant=1)
    assert content == verifier._synthetic_mpo(primary_variant=1, secondary_variant=1)
    with Image.open(io.BytesIO(content)) as image:
        assert image.format == "MPO"
        assert image.n_frames == 2

    source = inspect.getsource(verifier._verify_mpo_production_flow)
    for required in (
        "import_source_files(",
        "assess_source_file_quality(",
        "source.detected_media_type is SourceMediaType.JPEG",
        "sources[0].perceptual_hash == sources[1].perceptual_hash",
        "sources[0].perceptual_hash != sources[2].perceptual_hash",
        "decoded[0].grayscale_pixels == decoded[1].grayscale_pixels",
        "decoded[0].grayscale_pixels != decoded[2].grayscale_pixels",
        "metric_vectors[0] == metric_vectors[1]",
        "metric_vectors[0] != metric_vectors[2]",
        "storage.read_bytes(expected=artifact) == content",
    ):
        assert required in source


def test_pr009_verifier_contains_persistence_audit_and_storage_proofs() -> None:
    source = inspect.getsource(verifier._run_supported)
    for required in (
        "metric_count == 7",
        "persisted.policy == first_command.policy",
        "first_listing == (persisted,)",
        "audit_event.action_code is AuditAction.IMAGE_QUALITY_ASSESSED",
        "encrypted_object_after == encrypted_object_before",
        "object_paths_after == object_paths_before",
        "source_after_success == authoritative_source",
        "artifact_after_success == authoritative_artifact",
    ):
        assert required in source


def test_pr009_verifier_contains_real_uow_rollback_proof() -> None:
    source = inspect.getsource(verifier._run_supported)
    assert "_FailingAuditFactory(database)" in source
    assert "QualityAssessmentErrorCode.PERSISTENCE_FAILED" in source
    assert "rolled_back_assessment is None" in source
    assert "rolled_back_metric_count == 0" in source
    assert "rolled_back_issue_count == 0" in source
    assert "rolled_back_audit is None" in source


def test_pr009_verifier_corrupts_real_sqlcipher_row_and_requires_rejection() -> None:
    source = inspect.getsource(verifier._run_supported)
    assert '"DROP TRIGGER image_quality_metrics_no_update"' in source
    assert "\"UPDATE image_quality_metrics SET numeric_value='999' \"" in source
    assert "uow.image_quality_assessments.get(first_command.assessment_id)" in source
    assert "PersistenceErrorCode.PERSISTED_DATA_INVALID" in source
    assert "and corruption_rejected" in source
