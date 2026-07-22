from __future__ import annotations

import inspect
import io
from dataclasses import replace

import pytest
from PIL import Image
from scripts import verify_pr008_import as verifier

from document_intake.persistence.migrations.model import Migration


def _chain() -> tuple[Migration, ...]:
    return (verifier.V0001, verifier.V0002, verifier.V0003, verifier.V0004, verifier.V0005)


def test_pr008_verifier_accepts_only_exact_current_five_migration_chain() -> None:
    assert verifier._migration_chain_valid(5, _chain())
    assert not verifier._migration_chain_valid(4, _chain())


@pytest.mark.parametrize(
    "mutated",
    [
        lambda chain: chain[:-1],
        lambda chain: (chain[0], chain[1], chain[2], chain[4], chain[3]),
        lambda chain: (*chain[:2], Migration(99, "synthetic_middle", (), "0" * 64), *chain[2:]),
        lambda chain: (*chain[:3], replace(chain[3], checksum="1" * 64), chain[4]),
        lambda chain: (*chain[:4], replace(chain[4], checksum="2" * 64)),
    ],
    ids=(
        "missing-v0005",
        "reordered",
        "inserted-middle",
        "changed-v0004-checksum",
        "changed-v0005-checksum",
    ),
)
def test_pr008_verifier_rejects_non_exact_migration_chain(mutated) -> None:  # type: ignore[no-untyped-def]
    assert not verifier._migration_chain_valid(5, mutated(_chain()))


def test_pr008_verifier_preserves_accepted_migration_output_field() -> None:
    statuses = dict.fromkeys(verifier._CHECKS, True)
    lines = verifier._render_status_lines(statuses)
    assert "PR008_VERIFY migration_v0004=PASS" in lines


def test_pr008_verifier_proves_mpo_through_production_import_without_new_output() -> None:
    content = verifier._generated_mpo_bytes(primary_variant=1, secondary_variant=1)
    assert content == verifier._generated_mpo_bytes(primary_variant=1, secondary_variant=1)
    with Image.open(io.BytesIO(content)) as image:
        assert image.format == "MPO"
        assert image.n_frames == 2

    source = inspect.getsource(verifier._run_supported)
    for required in (
        "import_source_files(",
        "mpo_sources[0].perceptual_hash == mpo_sources[1].perceptual_hash",
        "mpo_sources[0].perceptual_hash != mpo_sources[2].perceptual_hash",
        "storage.read_bytes(expected=mpo_expected) == mpo_bytes",
    ):
        assert required in source
    assert verifier._CHECKS == (
        "migration_v0004",
        "encrypted_storage",
        "byte_identity",
        "media_jpeg",
        "media_png",
        "media_heif",
        "extension_casefold",
        "extension_mismatch_warning",
        "unsupported_extension",
        "exact_duplicate",
        "perceptual_duplicate",
        "no_self_match",
        "warning_order",
        "partial_success",
        "audit_atomicity",
        "orphan_reconciliation",
        "privacy",
    )
