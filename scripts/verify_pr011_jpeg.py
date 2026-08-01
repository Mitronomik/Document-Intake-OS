"""Sanitized production-component verifier for PR-011."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import tempfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from PIL import Image, JpegImagePlugin

from document_intake.application.dto.image_geometry import CreateImageGeometryRecipeCommand
from document_intake.application.dto.imports import (
    CreateUploadBatchCommand,
    ImportSourceFilesCommand,
    SourceFileImportInput,
)
from document_intake.application.dto.prepared_jpeg import PrepareJpegCommand
from document_intake.application.ports.jpeg_preparation import UncompressedRgbRaster
from document_intake.application.ports.persistence import UnitOfWork, UnitOfWorkFactory
from document_intake.application.ports.storage import StorageKey
from document_intake.application.services.image_geometry import create_image_geometry_recipe
from document_intake.application.services.imports import create_upload_batch, import_source_files
from document_intake.application.services.prepared_jpeg import prepare_geometry_recipe_as_jpeg
from document_intake.domain.enums import ActorKind, AuditAction, AuditSubjectType
from document_intake.domain.image_geometry import (
    GeometryPipelineVersion,
    GeometryPoint,
    GeometryQuarterTurn,
    SourceQuadrilateral,
)
from document_intake.domain.prepared_jpeg import (
    MAX_PREPARED_JPEG_BYTES,
    PreparedJpegError,
    PreparedJpegErrorCode,
    PreparedJpegPipelineVersion,
)
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects.imports import BatchNumber
from document_intake.image_pipeline.geometry_transformer import PillowGeometryTransformer
from document_intake.image_pipeline.jpeg_preparer import (
    PillowPreparedJpegEncoder,
    _encode_prepared_jpeg_internal,
    _iter_candidate_attempts,
)
from document_intake.image_pipeline.media_decoder import PillowMediaDecoder
from document_intake.persistence import CURRENT_SCHEMA_VERSION, EncryptedDatabase
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations.v0007_prepared_jpeg import MIGRATION
from document_intake.storage.filesystem import ImmutableFilesystemStorage

_CHECKSUM = "afad8ccc6de4ef81d73f137cbffa5a45fec1fdbb6940eabb0507cc9d6580a4a7"
_NOW = datetime(2026, 7, 26, 12, tzinfo=UTC)
_LABELS = (
    "schema_version=8",
    "byte_limit=1992294",
    "original_immutable=PASS",
    "geometry_replay=PASS",
    "candidate_order=PASS",
    "jpeg_valid=PASS",
    "rgb=PASS",
    "metadata_removed=PASS",
    "size_limit=PASS",
    "deterministic=PASS",
    "persistence=PASS",
    "audit=PASS",
    "rollback=PASS",
    "privacy=PASS",
    "result=PASS",
)


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


def _png() -> bytes:
    image = Image.new("RGB", (96, 64))
    pixels = image.load()
    assert pixels is not None
    for y in range(64):
        for x in range(96):
            pixels[x, y] = ((x * 17 + y * 3) % 256, (x * 5 + y * 11) % 256, (x * 13 + y * 7) % 256)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class _FailCommitUow:
    def __init__(self, inner: UnitOfWork) -> None:
        self._inner = inner

    def __enter__(self) -> Any:
        self._inner.__enter__()
        return self

    def __exit__(self, *args: Any) -> bool:
        return self._inner.__exit__(*args)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def commit(self) -> None:
        raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED)

    def rollback(self) -> None:
        self._inner.rollback()


class _FailCommitFactory:
    def __init__(self, db: EncryptedDatabase) -> None:
        self._db = db
        self.calls = 0

    def unit_of_work(self) -> UnitOfWork:
        self.calls += 1
        inner = cast(UnitOfWork, self._db.unit_of_work())
        return inner if self.calls % 2 else cast(UnitOfWork, _FailCommitUow(inner))


def _recipe_command(
    recipe: int, source: int, audit: int, *, revision: int = 1, previous: int | None = None
) -> CreateImageGeometryRecipeCommand:
    q = SourceQuadrilateral(
        GeometryPoint(0, 0), GeometryPoint(96, 0), GeometryPoint(96, 64), GeometryPoint(0, 64)
    )
    return CreateImageGeometryRecipeCommand(
        _id(recipe),
        _id(source),
        None if previous is None else _id(previous),
        revision,
        96,
        64,
        q,
        GeometryQuarterTurn.DEG_0,
        GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", 1),
        _NOW,
        _actor(),
        _id(audit),
        _id(audit + 100),
    )


def _run_production(root: Path) -> tuple[str, ...]:
    db = EncryptedDatabase(root / "state.db", _DbKey())
    db.initialize()
    storage_root = root / "storage"
    storage_root.mkdir()
    storage = ImmutableFilesystemStorage(storage_root, _StorageKeys())
    decoder = PillowMediaDecoder()
    renderer = PillowGeometryTransformer()
    encoder = PillowPreparedJpegEncoder()
    factory = cast(UnitOfWorkFactory, db)
    statuses: list[str] = []
    if CURRENT_SCHEMA_VERSION != 8 or MIGRATION.checksum != _CHECKSUM:
        raise RuntimeError from None
    statuses.append("schema_version=8")
    statuses.append("byte_limit=1992294")
    source_path = root / "source.png"
    original = _png()
    source_path.write_bytes(original)
    create_upload_batch(
        CreateUploadBatchCommand(_id(1), BatchNumber("VERIFY-PR011"), _NOW, _actor()),
        unit_of_work_factory=factory,
    )
    imported = import_source_files(
        ImportSourceFilesCommand(
            _id(1), _actor(), (SourceFileImportInput(_id(2), _id(3), _id(4), source_path, _NOW),)
        ),
        storage=storage,
        media_decoder=decoder,
        unit_of_work_factory=factory,
    )
    if len(imported.imported) != 1:
        raise RuntimeError from None
    recipe_command = _recipe_command(5, 2, 6)
    create_image_geometry_recipe(
        recipe_command,
        decoder=decoder,
        renderer=renderer,
        storage=storage,
        unit_of_work_factory=factory,
    )
    media = decoder.decode_for_geometry(content=original)
    rendered = renderer.render_geometry(
        media=media,
        quadrilateral=recipe_command.quadrilateral,
        quarter_turn=recipe_command.quarter_turn,
        pipeline=recipe_command.pipeline,
    )
    render_raster = UncompressedRgbRaster(rendered.width, rendered.height, rendered.rgb_pixels)
    observed: list[Any] = []
    deterministic_first = _encode_prepared_jpeg_internal(
        render_raster, pipeline=PreparedJpegPipelineVersion(), attempt_observer=observed.append
    )
    deterministic_second = PillowPreparedJpegEncoder().encode_prepared_jpeg(
        render_raster, pipeline=PreparedJpegPipelineVersion()
    )
    plan = _iter_candidate_attempts(render_raster)
    if not observed or tuple(observed) != plan[: len(observed)]:
        raise RuntimeError from None
    selected = observed[-1]
    if (
        deterministic_first.resize_percent,
        deterministic_first.jpeg_quality,
        deterministic_first.width,
        deterministic_first.height,
    ) != (selected.resize_percent, selected.jpeg_quality, selected.width, selected.height):
        raise RuntimeError from None
    command = PrepareJpegCommand(_id(7), _id(8), _id(5), _id(9), _NOW, _actor(), _id(10))
    result = prepare_geometry_recipe_as_jpeg(
        command,
        decoder=decoder,
        renderer=renderer,
        encoder=encoder,
        storage=storage,
        unit_of_work_factory=factory,
    )
    if source_path.read_bytes() != original:
        raise RuntimeError from None
    statuses.extend(("original_immutable=PASS", "geometry_replay=PASS"))
    with db.unit_of_work() as uow:
        stored = uow.stored_artifacts.get(_id(8))
        prepared = uow.prepared_image_artifacts.get(_id(7))
        audit = uow.audit_events.get(_id(9))
        if (
            stored is None
            or prepared != result.artifact
            or audit is None
            or audit.action_code is not AuditAction.PREPARED_JPEG_CREATED
            or audit.subject_type is not AuditSubjectType.PREPARED_IMAGE_ARTIFACT
        ):
            raise RuntimeError from None
    content = storage.read_bytes(expected=stored)
    with Image.open(BytesIO(content)) as image:
        image.load()
        if (
            image.format != "JPEG"
            or image.mode != "RGB"
            or image.getexif()
            or "icc_profile" in image.info
            or image.info.get("progressive")
            or JpegImagePlugin.get_sampling(image) != 0
        ):
            raise RuntimeError from None
    if len(content) > MAX_PREPARED_JPEG_BYTES:
        raise RuntimeError from None
    statuses.extend(
        (
            "candidate_order=PASS",
            "jpeg_valid=PASS",
            "rgb=PASS",
            "metadata_removed=PASS",
            "size_limit=PASS",
        )
    )
    if deterministic_first != deterministic_second or content != deterministic_first.jpeg_bytes:
        raise RuntimeError from None
    statuses.extend(("deterministic=PASS", "persistence=PASS", "audit=PASS"))
    try:
        prepare_geometry_recipe_as_jpeg(
            command,
            decoder=decoder,
            renderer=renderer,
            encoder=encoder,
            storage=storage,
            unit_of_work_factory=factory,
        )
    except PreparedJpegError as exc:
        if exc.code is not PreparedJpegErrorCode.IDENTITY_CONFLICT:
            raise RuntimeError from None
    else:
        raise RuntimeError from None
    create_image_geometry_recipe(
        _recipe_command(11, 2, 12, revision=2, previous=5),
        decoder=decoder,
        renderer=renderer,
        storage=storage,
        unit_of_work_factory=factory,
    )
    rollback_command = PrepareJpegCommand(
        _id(13), _id(14), _id(11), _id(15), _NOW, _actor(), _id(16)
    )
    try:
        prepare_geometry_recipe_as_jpeg(
            rollback_command,
            decoder=decoder,
            renderer=renderer,
            encoder=encoder,
            storage=storage,
            unit_of_work_factory=cast(UnitOfWorkFactory, _FailCommitFactory(db)),
        )
    except PreparedJpegError as late_exc:
        if late_exc.code is not PreparedJpegErrorCode.PERSISTENCE_FAILED:
            raise RuntimeError from None
    else:
        raise RuntimeError from None
    with db.unit_of_work() as uow:
        if (
            uow.stored_artifacts.get(_id(14))
            or uow.prepared_image_artifacts.get(_id(13))
            or uow.audit_events.get(_id(15))
        ):
            raise RuntimeError from None
        report = storage.reconcile(expected=uow.stored_artifacts.list_all())
    if not report.orphan:
        raise RuntimeError from None
    statuses.append("rollback=PASS")
    return tuple(statuses)


_GENERIC_FORBIDDEN = (
    ".db",
    ".jpg",
    ".jpeg",
    ".png",
    "\\",
    "/",
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "Traceback",
    "Exception",
    "sha256=",
    "key=",
    "quality=",
    "resize=",
    "width=",
    "height=",
)


def _render_success(
    statuses: tuple[str, ...], forbidden_values: tuple[str, ...]
) -> tuple[str, ...]:
    expected_statuses = _LABELS[:-2]
    if statuses != expected_statuses:
        raise RuntimeError from None
    lines = tuple(f"PR011_VERIFY {status}" for status in (*statuses, "privacy=PASS", "result=PASS"))
    allowed = tuple(f"PR011_VERIFY {status}" for status in _LABELS)
    if lines != allowed:
        raise RuntimeError from None
    joined = "\n".join(lines)
    if any(marker and marker in joined for marker in (*_GENERIC_FORBIDDEN, *forbidden_values)):
        raise RuntimeError from None
    return lines


def main() -> int:
    if platform.system() != "Windows":
        print("PR011_VERIFY result=INCONCLUSIVE")
        return 2
    if importlib.util.find_spec("sqlcipher3") is None:
        print("PR011_VERIFY result=INCONCLUSIVE")
        return 2
    root = Path(tempfile.mkdtemp(prefix="pr011-"))
    try:
        statuses = _run_production(root)
        lines = _render_success(
            statuses,
            (str(root), "source.png", "state.db", "storage", (b"D" * 32).hex(), (b"S" * 32).hex()),
        )
    except Exception:
        print("PR011_VERIFY result=FAIL")
        return 1
    finally:
        shutil.rmtree(root, ignore_errors=True)
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
