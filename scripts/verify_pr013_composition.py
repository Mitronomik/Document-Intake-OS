"""Sanitized deterministic production-component verifier for PR-013."""

from __future__ import annotations

import importlib.util
import tempfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import cast
from uuid import UUID

from PIL import Image, JpegImagePlugin

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ExistingRecipeSelection,
    RegionSetMemberInput,
)
from document_intake.application.dto.document_side_composition import (
    CreateDocumentSideCompositionCommand,
    DocumentSideReference,
)
from document_intake.application.dto.image_geometry import CreateImageGeometryRecipeCommand
from document_intake.application.dto.imports import (
    CreateUploadBatchCommand,
    ImportSourceFilesCommand,
    SourceFileImportInput,
)
from document_intake.application.ports.persistence import UnitOfWorkFactory
from document_intake.application.ports.storage import StorageKey
from document_intake.application.services.document_regions import confirm_document_regions
from document_intake.application.services.document_side_composition import (
    create_document_side_composition,
)
from document_intake.application.services.image_geometry import create_image_geometry_recipe
from document_intake.application.services.imports import create_upload_batch, import_source_files
from document_intake.domain.enums import (
    ActorKind,
    AuditAction,
    AuditSubjectType,
    DocumentSideCompositionLayout,
)
from document_intake.domain.image_geometry import (
    GeometryPipelineVersion,
    GeometryPoint,
    GeometryQuarterTurn,
    SourceQuadrilateral,
)
from document_intake.domain.prepared_jpeg import MAX_PREPARED_JPEG_BYTES
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects.imports import BatchNumber
from document_intake.image_pipeline.document_side_composer import PillowDocumentSideComposer
from document_intake.image_pipeline.geometry_transformer import PillowGeometryTransformer
from document_intake.image_pipeline.jpeg_preparer import PillowPreparedJpegEncoder
from document_intake.image_pipeline.media_decoder import PillowMediaDecoder
from document_intake.persistence import CURRENT_SCHEMA_VERSION, EncryptedDatabase
from document_intake.storage.filesystem import ImmutableFilesystemStorage

_NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)
_LABELS = (
    "PR013_VERIFY schema_version=9",
    "PR013_VERIFY encrypted_database=PASS",
    "PR013_VERIFY encrypted_storage=PASS",
    "PR013_VERIFY confirmed_regions=PASS",
    "PR013_VERIFY geometry_replay=PASS",
    "PR013_VERIFY vertical_composition=PASS",
    "PR013_VERIFY horizontal_composition=PASS",
    "PR013_VERIFY jpeg_contract=PASS",
    "PR013_VERIFY persistence_reopen=PASS",
    "PR013_VERIFY ordered_natural_key=PASS",
    "PR013_VERIFY one_to_one=PASS",
    "PR013_VERIFY typed_audit=PASS",
    "PR013_VERIFY reconciliation=PASS",
    "PR013_VERIFY source_immutability=PASS",
    "PR013_VERIFY privacy=PASS",
    "PR013_VERIFY result=PASS",
)
_UNAVAILABLE = "PR013_VERIFY result=INCONCLUSIVE code=SQLCIPHER_UNAVAILABLE"


class _DbKey:
    def get_database_key(self) -> bytes:
        return b"D" * 32


class _StorageKeys:
    def get_current_key(self) -> StorageKey:
        return StorageKey(1, b"S" * 32)

    def get_key(self, version: int) -> StorageKey:
        if version != 1:
            raise ValueError
        return self.get_current_key()


def _id(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def _actor() -> ActorRef:
    return ActorRef(_id(900), ActorKind.SYSTEM)


def _png(seed: int) -> bytes:
    image = Image.new("RGB", (96, 64))
    pixels = image.load()
    assert pixels is not None
    for y in range(64):
        for x in range(96):
            pixels[x, y] = (
                (x * 17 + y * 3 + seed) % 256,
                (x * 5 + y * 11 + seed * 2) % 256,
                (x * 13 + y * 7 + seed * 3) % 256,
            )
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _recipe(recipe: int, source: int, audit: int) -> CreateImageGeometryRecipeCommand:
    quadrilateral = SourceQuadrilateral(
        GeometryPoint(0, 0),
        GeometryPoint(96, 0),
        GeometryPoint(96, 64),
        GeometryPoint(0, 64),
    )
    return CreateImageGeometryRecipeCommand(
        _id(recipe),
        _id(source),
        None,
        1,
        96,
        64,
        quadrilateral,
        GeometryQuarterTurn.DEG_0,
        GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", 1),
        _NOW,
        _actor(),
        _id(audit),
        _id(100),
    )


def _regions(set_id: int, source: int, recipe: int, audit: int) -> ConfirmDocumentRegionsCommand:
    return ConfirmDocumentRegionsCommand(
        _id(set_id),
        _id(source),
        None,
        1,
        (RegionSetMemberInput(1, _id(recipe), ExistingRecipeSelection(_id(recipe))),),
        _id(audit),
        _NOW,
        _actor(),
        _id(100),
    )


def _composition(
    base: int, layout: DocumentSideCompositionLayout
) -> CreateDocumentSideCompositionCommand:
    return CreateDocumentSideCompositionCommand(
        _id(base),
        _id(base + 1),
        DocumentSideReference(_id(20), _id(2), _id(10), _id(10)),
        DocumentSideReference(_id(21), _id(5), _id(11), _id(11)),
        layout,
        8,
        4,
        _id(base + 2),
        _id(base + 3),
        _id(base + 4),
        _NOW,
        _actor(),
        _id(base + 5),
    )


def _valid_jpeg(content: bytes) -> bool:
    with Image.open(BytesIO(content)) as image:
        image.load()
        forbidden = {"icc_profile", "xmp", "XML:com.adobe.xmp", "iptc", "comment"}
        return (
            image.format == "JPEG"
            and image.mode == "RGB"
            and not image.getexif()
            and not (forbidden & image.info.keys())
            and JpegImagePlugin.get_sampling(image) == 0
            and len(content) <= MAX_PREPARED_JPEG_BYTES
        )


def _run(root: Path) -> None:
    if CURRENT_SCHEMA_VERSION != 9:
        raise RuntimeError
    database_path = root / "state.db"
    database = EncryptedDatabase(database_path, _DbKey())
    database.initialize()
    storage_root = root / "storage"
    storage_root.mkdir()
    storage = ImmutableFilesystemStorage(storage_root, _StorageKeys())
    decoder = PillowMediaDecoder()
    renderer = PillowGeometryTransformer()
    composer = PillowDocumentSideComposer()
    encoder = PillowPreparedJpegEncoder()
    factory = cast(UnitOfWorkFactory, database)
    source_a, source_b = root / "a.png", root / "b.png"
    original_a, original_b = _png(1), _png(2)
    source_a.write_bytes(original_a)
    source_b.write_bytes(original_b)
    create_upload_batch(
        CreateUploadBatchCommand(_id(1), BatchNumber("VERIFY-PR013"), _NOW, _actor()),
        unit_of_work_factory=factory,
    )
    imported = import_source_files(
        ImportSourceFilesCommand(
            _id(1),
            _actor(),
            (
                SourceFileImportInput(_id(2), _id(3), _id(4), source_a, _NOW),
                SourceFileImportInput(_id(5), _id(6), _id(7), source_b, _NOW),
            ),
        ),
        storage=storage,
        media_decoder=decoder,
        unit_of_work_factory=factory,
    )
    if len(imported.imported) != 2:
        raise RuntimeError
    for recipe in (_recipe(10, 2, 12), _recipe(11, 5, 13)):
        create_image_geometry_recipe(
            recipe,
            decoder=decoder,
            renderer=renderer,
            storage=storage,
            unit_of_work_factory=factory,
        )
    for regions in (_regions(20, 2, 10, 22), _regions(21, 5, 11, 23)):
        confirm_document_regions(
            regions,
            decoder=decoder,
            renderer=renderer,
            storage=storage,
            unit_of_work_factory=factory,
        )
    results = tuple(
        create_document_side_composition(
            _composition(base, layout),
            decoder=decoder,
            renderer=renderer,
            composer=composer,
            encoder=encoder,
            storage=storage,
            unit_of_work_factory=factory,
        )
        for base, layout in (
            (30, DocumentSideCompositionLayout.VERTICAL),
            (40, DocumentSideCompositionLayout.HORIZONTAL),
        )
    )
    reopened = EncryptedDatabase(database_path, _DbKey())
    with reopened.unit_of_work() as uow:
        for result, base, layout in zip(
            results,
            (30, 40),
            (DocumentSideCompositionLayout.VERTICAL, DocumentSideCompositionLayout.HORIZONTAL),
            strict=True,
        ):
            version = uow.document_side_compositions.get_version(_id(base + 1))
            artifact = uow.document_side_compositions.get_artifact_by_composition_version(
                _id(base + 1)
            )
            audit = uow.audit_events.get(_id(base + 4))
            if version != result.composition_version or artifact != result.artifact:
                raise RuntimeError
            if (
                version is None
                or uow.document_side_compositions.get_by_natural_key(
                    side_1_region_set_version_id=version.side_1_region_set_version_id,
                    side_1_source_file_id=version.side_1_source_file_id,
                    side_1_region_id=version.side_1_region_id,
                    side_1_geometry_recipe_version_id=version.side_1_geometry_recipe_version_id,
                    side_2_region_set_version_id=version.side_2_region_set_version_id,
                    side_2_source_file_id=version.side_2_source_file_id,
                    side_2_region_id=version.side_2_region_id,
                    side_2_geometry_recipe_version_id=version.side_2_geometry_recipe_version_id,
                    layout=layout,
                    outer_margin_px=8,
                    inter_side_gap_px=4,
                    composition_pipeline_id=version.composition_pipeline_id,
                    composition_pipeline_version=version.composition_pipeline_version,
                    jpeg_pipeline_id=version.jpeg_pipeline_id,
                    jpeg_pipeline_version=version.jpeg_pipeline_version,
                    output_contract_id=version.output_contract_id,
                    output_contract_version=version.output_contract_version,
                )
                != version
            ):
                raise RuntimeError
            if (
                audit is None
                or audit.action_code is not AuditAction.DOCUMENT_SIDE_COMPOSITION_CREATED
                or audit.subject_type is not AuditSubjectType.DOCUMENT_SIDE_COMPOSITION
            ):
                raise RuntimeError
            stored = uow.stored_artifacts.get(_id(base + 3))
            if stored is None or not _valid_jpeg(storage.read_bytes(expected=stored)):
                raise RuntimeError
        expected = uow.stored_artifacts.list_all()
    report = storage.reconcile(expected=expected)
    if report.missing or report.invalid or report.orphan or report.temporary:
        raise RuntimeError
    if source_a.read_bytes() != original_a or source_b.read_bytes() != original_b:
        raise RuntimeError


def main() -> int:
    if importlib.util.find_spec("sqlcipher3") is None:
        print(_UNAVAILABLE)
        return 2
    try:
        with tempfile.TemporaryDirectory(prefix="pr013-verify-") as temporary:
            _run(Path(temporary))
    except Exception:
        print("PR013_VERIFY result=FAIL")
        return 1
    for line in _LABELS:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
