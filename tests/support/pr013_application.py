"""Synthetic in-memory PR-013 application evidence helpers."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

from document_intake.application.dto.document_side_composition import (
    CreateDocumentSideCompositionCommand,
    DocumentSideReference,
)
from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.jpeg_preparation import EncodedPreparedJpeg
from document_intake.application.ports.media import DecodedGeometryMedia, RenderedGeometryRaster
from document_intake.domain.document_regions import (
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
from document_intake.domain.enums import DocumentSideCompositionLayout, SourceMediaType
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


class Repo:
    def __init__(self, values=()):
        self.values = {self.key(value): value for value in values}
        self.add_calls = []

    @staticmethod
    def key(value):
        for name in ("region_set_version_id", "recipe_version_id", "artifact_id", "event_id", "id"):
            if (key := getattr(value, name, None)) is not None:
                return key
        raise AssertionError

    def get(self, key):
        return self.values.get(key)

    def add(self, value):
        key = self.key(value)
        if key in self.values:
            raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
        self.add_calls.append(value)
        self.values[key] = value


class CompositionRepo:
    def __init__(self):
        self.compositions = {}
        self.versions = {}
        self.artifacts = {}
        self.natural = None
        self.add_calls = []

    def get_composition(self, key):
        return self.compositions.get(key)

    def get_version(self, key):
        return self.versions.get(key)

    def get_artifact(self, key):
        return self.artifacts.get(key)

    def get_artifact_by_composition_version(self, key):
        return next(
            (value for value in self.artifacts.values() if value.composition_version_id == key),
            None,
        )

    def get_by_natural_key(self, **_kwargs):
        return self.natural

    def add_composition(self, value):
        self.add_calls.append("composition")
        self.compositions[value.id] = value

    def add_version(self, value):
        self.add_calls.append("version")
        self.versions[value.id] = value

    def add_artifact(self, value):
        self.add_calls.append("artifact")
        self.artifacts[value.id] = value


def contexts():
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
        source_file_id=entity_id(21),
        region_id=entity_id(31),
    )
    first_set = DocumentRegionSetVersion(
        entity_id(60),
        first_source.id,
        None,
        1,
        (DocumentRegionSetMember(1, first_recipe.region_id, first_recipe.recipe_version_id),),
        STAMP,
        actor(),
    )
    second_set = DocumentRegionSetVersion(
        entity_id(61),
        second_source.id,
        None,
        1,
        (DocumentRegionSetMember(1, second_recipe.region_id, second_recipe.recipe_version_id),),
        STAMP,
        actor(),
    )
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
    def __init__(self, calls):
        values = contexts()
        self.calls = calls
        self.source_files = Repo(values[:2])
        self.stored_artifacts = Repo(values[2:4])
        self.image_geometry_recipes = Repo(values[4:6])
        self.document_region_sets = Repo(values[6:8])
        self.document_side_compositions = CompositionRepo()
        self.audit_events = Repo()
        self.commits = 0

    def __enter__(self):
        self.calls.append("uow.enter")
        return self

    def __exit__(self, *_args):
        self.calls.append("uow.exit")
        return False

    def commit(self):
        self.calls.append("uow.commit")
        self.commits += 1

    def rollback(self):
        self.calls.append("uow.rollback")


class Factory:
    def __init__(self, calls):
        self.units = [Uow(calls), Uow(calls)]
        self.used = []

    def unit_of_work(self):
        value = self.units[len(self.used)]
        self.used.append(value)
        return value


class Storage:
    def __init__(self, calls):
        self.calls = calls
        self.publish_calls = 0

    def read_bytes(self, *, expected):
        self.calls.append("storage.read")
        return b"synthetic"

    def publish_bytes(self, *, artifact_id, artifact_kind, plaintext, created_at):
        self.calls.append("storage.publish")
        self.publish_calls += 1
        return StoredArtifactRecord(
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


class Decoder:
    def __init__(self, calls):
        self.calls = calls

    def decode_for_geometry(self, *, content):
        self.calls.append("decode")
        return DecodedGeometryMedia(SourceMediaType.JPEG, 32, 24, None, 32, 24, b"\0" * 2304)


class Renderer:
    def __init__(self, calls):
        self.calls = calls

    def render_geometry(self, *, media, quadrilateral, quarter_turn, pipeline):
        self.calls.append("render")
        return RenderedGeometryRaster(32, 24, b"\1" * 2304, pipeline)


class Composer:
    def __init__(self, calls):
        self.calls = calls
        self.count = 0

    def compose(self, *, side_1, side_2, **_kwargs):
        self.calls.append("compose")
        self.count += 1
        return side_1


class Encoder:
    def __init__(self, calls):
        self.calls = calls
        self.count = 0

    def encode_prepared_jpeg(self, raster, *, pipeline):
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


def command(*, swapped=False):
    side_1 = DocumentSideReference(entity_id(60), entity_id(20), entity_id(30), entity_id(30))
    side_2 = DocumentSideReference(entity_id(61), entity_id(21), entity_id(31), entity_id(31))
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
