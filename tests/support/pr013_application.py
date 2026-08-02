"""Transactional synthetic PR-013 application evidence helpers."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from typing import Any, Literal

from document_intake.application.dto.document_side_composition import (
    CreateDocumentSideCompositionCommand,
    DocumentSideReference,
)
from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.jpeg_preparation import EncodedPreparedJpeg
from document_intake.application.ports.media import DecodedGeometryMedia, RenderedGeometryRaster
from document_intake.application.services.document_side_composition import (
    create_document_side_composition,
)
from document_intake.domain.document_regions import (
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
from document_intake.domain.enums import (
    ArtifactKind,
    DocumentSideCompositionLayout,
    SourceMediaType,
)
from document_intake.domain.prepared_jpeg import (
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
    PREPARED_JPEG_PIPELINE_ID,
    PREPARED_JPEG_PIPELINE_VERSION,
)
from document_intake.domain.value_objects import Sha256Digest, SourceBasename
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.support.pr011 import (
    STAMP,
    actor,
    correlation_id,
    entity_id,
    valid_geometry_recipe,
    valid_original_stored_artifact,
    valid_source_file,
)

Variant = Literal["different_sources", "same_source", "same_region_set"]


def contexts(variant: Variant = "different_sources") -> tuple[Any, ...]:
    first_source = valid_source_file()
    first_original = valid_original_stored_artifact()
    first_recipe = valid_geometry_recipe()
    second_original = replace(first_original, artifact_id=entity_id(12))
    second_source = replace(
        first_source,
        id=entity_id(21),
        original_artifact_id=entity_id(12),
        original_basename=SourceBasename("synthetic-two.jpg"),
    )
    second_recipe = replace(
        first_recipe,
        recipe_version_id=entity_id(31),
        source_file_id=second_source.id,
        region_id=entity_id(31),
    )
    if variant != "different_sources":
        second_source = first_source
        second_original = first_original
        second_recipe = replace(second_recipe, source_file_id=first_source.id)
    first_set = DocumentRegionSetVersion(
        entity_id(60),
        first_source.id,
        None,
        1,
        (DocumentRegionSetMember(1, first_recipe.region_id, first_recipe.recipe_version_id),),
        STAMP,
        actor(),
    )
    second_set_id = entity_id(60) if variant == "same_region_set" else entity_id(61)
    second_members = (
        (
            DocumentRegionSetMember(1, first_recipe.region_id, first_recipe.recipe_version_id),
            DocumentRegionSetMember(2, second_recipe.region_id, second_recipe.recipe_version_id),
        )
        if variant == "same_region_set"
        else (DocumentRegionSetMember(1, second_recipe.region_id, second_recipe.recipe_version_id),)
    )
    second_set = DocumentRegionSetVersion(
        second_set_id,
        second_source.id,
        None,
        1,
        second_members,
        STAMP,
        actor(),
    )
    if variant == "same_region_set":
        first_set = second_set
    return (
        first_source,
        second_source,
        first_original,
        second_original,
        first_recipe,
        second_recipe,
        first_set,
        second_set,
    )


class Uow:
    def __init__(self, calls: list[str], *, variant: Variant, read_only: bool) -> None:
        values = contexts(variant)
        self.calls = calls
        self.read_only = read_only
        self.fail_stage: str | None = None
        self.fail_code = PersistenceErrorCode.PERSISTENCE_CONSTRAINT
        self.commit_error: Exception | None = None
        self.exit_error: Exception | None = None
        self.staged: dict[str, list[Any]] = {}
        self.committed: dict[str, list[Any]] = {}
        self.commit_attempts = 0
        self.commits = 0
        self.rollbacks = 0
        self.committed_complete = False
        self.source_files = Repo(self, "source_files", values[:2])
        self.stored_artifacts = Repo(self, "stored_artifacts", values[2:4])
        self.image_geometry_recipes = Repo(self, "image_geometry_recipes", values[4:6])
        self.document_region_sets = Repo(self, "document_region_sets", values[6:8])
        self.document_side_compositions = CompositionRepo(self)
        self.audit_events = Repo(self, "audit_events")

    def stage(self, stage: str, value: Any) -> None:
        if self.fail_stage == stage:
            raise PersistenceError(self.fail_code)
        self.staged.setdefault(stage, []).append(value)

    def __enter__(self) -> Uow:
        self.calls.append("uow.enter")
        return self

    def __exit__(self, *_args: Any) -> bool:
        if not self.read_only and not self.committed_complete:
            self.rollbacks += 1
            self.staged.clear()
            self.calls.append("uow.rollback")
        self.calls.append("uow.exit")
        if self.exit_error is not None:
            raise self.exit_error
        return False

    def commit(self) -> None:
        self.calls.append("uow.commit")
        self.commit_attempts += 1
        if self.commit_error is not None:
            raise self.commit_error
        self.committed = {name: list(values) for name, values in self.staged.items()}
        self.staged.clear()
        self.commits += 1
        self.committed_complete = True

    def rollback(self) -> None:
        self.calls.append("uow.rollback")
        self.rollbacks += 1
        self.staged.clear()

    @property
    def committed_row_count(self) -> int:
        return sum(len(values) for values in self.committed.values())


class Repo:
    def __init__(self, uow: Uow, name: str, values: tuple[Any, ...] = ()) -> None:
        self.uow = uow
        self.name = name
        self.values = {self.key(value): value for value in values}
        self.add_calls: list[Any] = []
        self.get_calls: list[Any] = []

    @staticmethod
    def key(value: Any) -> Any:
        for name in ("region_set_version_id", "recipe_version_id", "artifact_id", "event_id", "id"):
            if (key := getattr(value, name, None)) is not None:
                return key
        raise AssertionError

    def get(self, key: Any) -> Any:
        self.get_calls.append(key)
        for values in (self.uow.staged.values(), self.uow.committed.values()):
            for value in (item for group in values for item in group):
                if self.key(value) == key:
                    return value
        return self.values.get(key)

    def add(self, value: Any) -> None:
        key = self.key(value)
        if key in self.values:
            raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
        stage = f"{self.name}.add"
        self.uow.stage(stage, value)
        self.add_calls.append(value)


class CompositionRepo:
    def __init__(self, uow: Uow) -> None:
        self.uow = uow
        self.compositions: dict[Any, Any] = {}
        self.versions: dict[Any, Any] = {}
        self.artifacts: dict[Any, Any] = {}
        self.natural: Any = None
        self.add_calls: list[str] = []

    def get_composition(self, key: Any) -> Any:
        return self.compositions.get(key)

    def get_version(self, key: Any) -> Any:
        return self.versions.get(key)

    def get_artifact(self, key: Any) -> Any:
        return self.artifacts.get(key)

    def get_artifact_by_composition_version(self, key: Any) -> Any:
        return next(
            (value for value in self.artifacts.values() if value.composition_version_id == key),
            None,
        )

    def get_by_natural_key(self, **_kwargs: Any) -> Any:
        return self.natural

    def _add(self, name: str, value: Any) -> None:
        self.uow.stage(f"document_side_compositions.add_{name}", value)
        self.add_calls.append(name)

    def add_composition(self, value: Any) -> None:
        self._add("composition", value)

    def add_version(self, value: Any) -> None:
        self._add("version", value)

    def add_artifact(self, value: Any) -> None:
        self._add("artifact", value)


class Factory:
    def __init__(self, calls: list[str], *, variant: Variant = "different_sources") -> None:
        self.units = [
            Uow(calls, variant=variant, read_only=True),
            Uow(calls, variant=variant, read_only=False),
        ]
        self.used: list[Uow] = []

    def unit_of_work(self) -> Uow:
        value = self.units[len(self.used)]
        self.used.append(value)
        return value


class Storage:
    def __init__(self, calls: list[str], *, mismatch: str | None = None) -> None:
        self.calls = calls
        self.mismatch = mismatch
        self.publish_error: Exception | None = None
        self.publish_attempts = 0
        self.publish_calls = 0
        self.published_objects: list[Any] = []
        self.delete_calls = 0
        self.adopt_calls = 0

    def read_bytes(self, *, expected: Any) -> bytes:
        self.calls.append("storage.read")
        return b"synthetic"

    def publish_bytes(
        self, *, artifact_id: Any, artifact_kind: Any, plaintext: bytes, created_at: Any
    ) -> StoredArtifactRecord:
        self.calls.append("storage.publish")
        self.publish_attempts += 1
        if self.publish_error is not None:
            raise self.publish_error
        self.publish_calls += 1
        self.published_objects.append(artifact_id)
        record = StoredArtifactRecord(
            artifact_id,
            artifact_kind,
            1,
            len(plaintext),
            sha256(plaintext).hexdigest(),
            "d" * 64,
            1,
            1,
            created_at,
        )
        changes = {
            "artifact_id": {"artifact_id": entity_id(999)},
            "artifact_kind": {"artifact_kind": ArtifactKind.ORIGINAL},
            "object_generation": {"object_generation": 2},
            "plaintext_length": {"plaintext_length": len(plaintext) + 1},
            "plaintext_sha256": {"plaintext_sha256": "e" * 64},
            "created_at": {"created_at": created_at + timedelta(seconds=1)},
        }
        return replace(record, **changes.get(self.mismatch, {}))

    def delete(self, *_args: Any, **_kwargs: Any) -> None:
        self.delete_calls += 1

    def adopt(self, *_args: Any, **_kwargs: Any) -> None:
        self.adopt_calls += 1


class Decoder:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def decode_for_geometry(self, *, content: bytes) -> DecodedGeometryMedia:
        self.calls.append("decode")
        return DecodedGeometryMedia(SourceMediaType.JPEG, 32, 24, None, 32, 24, b"\0" * 2304)


class Renderer:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def render_geometry(
        self, *, media: Any, quadrilateral: Any, quarter_turn: Any, pipeline: Any
    ) -> RenderedGeometryRaster:
        self.calls.append("render")
        return RenderedGeometryRaster(32, 24, b"\1" * 2304, pipeline)


class Composer:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.count = 0

    def compose(self, *, side_1: Any, side_2: Any, **_kwargs: Any) -> Any:
        self.calls.append("compose")
        self.count += 1
        return side_1


class Encoder:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.count = 0

    def encode_prepared_jpeg(self, raster: Any, *, pipeline: Any) -> EncodedPreparedJpeg:
        self.calls.append("encode")
        self.count += 1
        data = b"synthetic-jpeg"
        return EncodedPreparedJpeg(
            data,
            raster.width,
            raster.height,
            len(data),
            Sha256Digest(sha256(data).hexdigest()),
            95,
            100,
            PREPARED_JPEG_PIPELINE_ID,
            PREPARED_JPEG_PIPELINE_VERSION,
            PREPARED_JPEG_OUTPUT_CONTRACT_ID,
            PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
        )


def command(
    *, variant: Variant = "different_sources", swapped: bool = False
) -> CreateDocumentSideCompositionCommand:
    side_1 = DocumentSideReference(entity_id(60), entity_id(20), entity_id(30), entity_id(30))
    second_set = entity_id(60) if variant == "same_region_set" else entity_id(61)
    second_source = entity_id(21) if variant == "different_sources" else entity_id(20)
    side_2 = DocumentSideReference(second_set, second_source, entity_id(31), entity_id(31))
    if swapped:
        side_1, side_2 = side_2, side_1
    return CreateDocumentSideCompositionCommand(
        entity_id(101),
        entity_id(102),
        side_1,
        side_2,
        DocumentSideCompositionLayout.VERTICAL,
        4,
        2,
        entity_id(103),
        entity_id(104),
        entity_id(105),
        STAMP,
        actor(),
        correlation_id(),
    )


def invoke(factory: Factory, storage: Storage, *, variant: Variant = "different_sources") -> Any:
    calls = factory.units[0].calls
    return create_document_side_composition(
        command(variant=variant),
        decoder=Decoder(calls),
        renderer=Renderer(calls),
        composer=Composer(calls),
        encoder=Encoder(calls),
        storage=storage,
        unit_of_work_factory=factory,
    )
