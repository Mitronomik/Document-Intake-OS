from __future__ import annotations

import json
from dataclasses import fields, replace
from inspect import Parameter, signature

import pytest

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ExistingRecipeSelection,
    NewRecipeRevision,
    RegionSetMemberInput,
)
from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.media import (
    DecodedGeometryMedia,
    GeometryDecoderPort,
    GeometryRendererPort,
    RenderedGeometryRaster,
)
from document_intake.application.ports.storage import StoragePort
from document_intake.application.services.document_regions import confirm_document_regions
from document_intake.domain.document_regions import (
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.entities.imports import SourceFile
from document_intake.domain.enums import (
    ArtifactKind,
    AuditAction,
    AuditSubjectType,
    AuditValueClassification,
    SourceMediaType,
)
from document_intake.domain.image_geometry import GeometryPoint, SourceQuadrilateral
from document_intake.domain.value_objects.imports import SourceBasename
from document_intake.persistence import serialization as ser
from tests.support.pr011 import STAMP, actor, correlation_id, entity_id, valid_geometry_recipe
from tests.support.pr012_application import (
    Factory,
    new_selection,
    run,
    with_previous,
)

DEFAULT_CORRELATION = correlation_id()
AUDIT_JSON_KEYS = {
    "event_id",
    "occurred_at",
    "actor",
    "action_code",
    "subject_type",
    "subject_id",
    "field_key",
    "before",
    "after",
    "reason_code",
    "correlation_id",
}
ACTOR_JSON_KEYS = {"actor_id", "kind"}
SUMMARY_JSON_KEYS = {"classification", "display_value", "was_present"}


def new_command(
    members: tuple[RegionSetMemberInput, ...],
    *,
    set_id: int = 600,
    audit_id: int = 601,
    revision: int = 1,
    predecessor: int | None = None,
    correlation=DEFAULT_CORRELATION,
) -> ConfirmDocumentRegionsCommand:
    return ConfirmDocumentRegionsCommand(
        entity_id(set_id),
        entity_id(20),
        None if predecessor is None else entity_id(predecessor),
        revision,
        members,
        entity_id(audit_id),
        STAMP,
        actor(),
        correlation,
    )


def new_member(order: int, recipe_id: int, audit_id: int, *, offset: int = 0):
    base = valid_geometry_recipe().quadrilateral
    quad = (
        base
        if offset == 0
        else replace(
            base,
            top_left=replace(base.top_left, x=offset),
            bottom_left=replace(base.bottom_left, x=offset),
        )
    )
    return RegionSetMemberInput(
        order,
        entity_id(recipe_id),
        new_selection(entity_id(recipe_id), entity_id(audit_id), quad),
    )


def existing_member(order: int, recipe_id: int, region_id: int):
    return RegionSetMemberInput(
        order,
        entity_id(region_id),
        ExistingRecipeSelection(entity_id(recipe_id)),
    )


def audit_events(command, factory):
    write = factory.units[1]
    run(command, factory)
    return tuple(write.audit_events.add_calls)


def assert_summary(actual, classification, display, present) -> None:
    assert actual is not None
    assert actual.classification is classification
    assert actual.display_value == display
    assert actual.was_present is present


def json_leaf_values(value: object) -> tuple[object, ...]:
    if isinstance(value, dict):
        return tuple(leaf for child in value.values() for leaf in json_leaf_values(child))
    if isinstance(value, list):
        return tuple(leaf for child in value for leaf in json_leaf_values(child))
    return (value,)


def assert_exact_serialized_audit_surface(payload: str) -> dict[str, object]:
    parsed = json.loads(payload)
    assert isinstance(parsed, dict)
    assert set(parsed) == AUDIT_JSON_KEYS
    assert isinstance(parsed["actor"], dict)
    assert set(parsed["actor"]) == ACTOR_JSON_KEYS
    for name in ("before", "after"):
        assert isinstance(parsed[name], dict)
        assert set(parsed[name]) == SUMMARY_JSON_KEYS
    return parsed


def repeated_rgb(marker: bytes, width: int, height: int) -> bytes:
    required = width * height * 3
    return (marker * ((required // len(marker)) + 1))[:required]


def test_recipe_and_region_set_audit_fields_are_exact() -> None:
    command = new_command((new_member(1, 100, 700),))
    recipe_event, set_event = audit_events(command, Factory())
    assert recipe_event.event_id == entity_id(700)
    assert recipe_event.occurred_at == command.confirmed_at
    assert recipe_event.actor == command.actor
    assert recipe_event.action_code is AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED
    assert recipe_event.subject_type is AuditSubjectType.IMAGE_GEOMETRY_RECIPE
    assert recipe_event.subject_id == entity_id(100)
    assert recipe_event.field_key is None
    assert_summary(recipe_event.before, AuditValueClassification.ABSENT, None, False)
    assert_summary(
        recipe_event.after,
        AuditValueClassification.NON_SENSITIVE,
        "IMAGE_GEOMETRY_RECIPE",
        True,
    )
    assert recipe_event.reason_code is not None
    assert recipe_event.reason_code.value == "IMAGE_GEOMETRY_RECIPE_CREATED"
    assert recipe_event.correlation_id == command.correlation_id

    assert set_event.event_id == command.region_set_audit_event_id
    assert set_event.occurred_at == command.confirmed_at
    assert set_event.actor == command.actor
    assert set_event.action_code is AuditAction.DOCUMENT_REGION_SET_CONFIRMED
    assert set_event.subject_type is AuditSubjectType.DOCUMENT_REGION_SET
    assert set_event.subject_id == command.region_set_version_id
    assert set_event.field_key is None
    assert_summary(set_event.before, AuditValueClassification.ABSENT, None, False)
    assert_summary(
        set_event.after,
        AuditValueClassification.NON_SENSITIVE,
        "DOCUMENT_REGION_SET",
        True,
    )
    assert set_event.reason_code is not None
    assert set_event.reason_code.value == "DOCUMENT_REGION_SET_CONFIRMED"
    assert set_event.correlation_id == command.correlation_id


def audit_sequence(command, factory):
    return tuple((event.event_id, event.action_code) for event in audit_events(command, factory))


def test_audit_cardinality_and_order_for_one_and_two_new_members() -> None:
    one = new_command((new_member(1, 100, 700),))
    assert audit_sequence(one, Factory()) == (
        (entity_id(700), AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED),
        (entity_id(601), AuditAction.DOCUMENT_REGION_SET_CONFIRMED),
    )
    two = new_command((new_member(1, 100, 700), new_member(2, 200, 701, offset=8)))
    assert audit_sequence(two, Factory()) == (
        (entity_id(700), AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED),
        (entity_id(701), AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED),
        (entity_id(601), AuditAction.DOCUMENT_REGION_SET_CONFIRMED),
    )


def test_audit_cardinality_for_mixed_all_existing_and_order_only() -> None:
    a = valid_geometry_recipe()
    b_selection = new_member(1, 200, 799, offset=8).recipe_selection
    assert hasattr(b_selection, "quadrilateral")
    b = replace(
        a,
        recipe_version_id=entity_id(200),
        region_id=entity_id(200),
        quadrilateral=b_selection.quadrilateral,
    )
    mixed = new_command((existing_member(1, 30, 30), new_member(2, 200, 701, offset=8)))
    assert audit_sequence(mixed, Factory(a)) == (
        (entity_id(701), AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED),
        (entity_id(601), AuditAction.DOCUMENT_REGION_SET_CONFIRMED),
    )
    existing = new_command((existing_member(1, 30, 30), existing_member(2, 200, 200)))
    assert audit_sequence(existing, Factory(a, b)) == (
        (entity_id(601), AuditAction.DOCUMENT_REGION_SET_CONFIRMED),
    )
    previous = DocumentRegionSetVersion(
        entity_id(600),
        entity_id(20),
        None,
        1,
        (
            DocumentRegionSetMember(1, entity_id(30), entity_id(30)),
            DocumentRegionSetMember(2, entity_id(200), entity_id(200)),
        ),
        STAMP,
        actor(),
    )
    order_only = new_command(
        (existing_member(1, 200, 200), existing_member(2, 30, 30)),
        set_id=602,
        audit_id=603,
        revision=2,
        predecessor=600,
    )
    assert audit_sequence(order_only, with_previous(Factory(a, b), previous)) == (
        (entity_id(603), AuditAction.DOCUMENT_REGION_SET_CONFIRMED),
    )


@pytest.mark.parametrize("correlation", [correlation_id(), None])
def test_correlation_id_is_copied_exactly_without_generation(correlation) -> None:
    command = new_command((new_member(1, 100, 700),), correlation=correlation)
    assert tuple(event.correlation_id for event in audit_events(command, Factory())) == (
        correlation,
        correlation,
    )


def test_flow_carried_private_values_are_absent_from_actual_audits() -> None:
    source_basename = "synthetic-flow-private-source.jpg"
    source_plaintext_checksum = "a1b2c3d4" * 8
    artifact_ciphertext_checksum = "c3d4e5f6" * 8
    source_bytes = b"SYNTHETIC-FLOW-SOURCE-BYTES-4B"
    decoded_marker = b"SYNTHETIC-FLOW-DECODED-RGB-4B"
    rendered_markers = (
        b"SYNTHETIC-FLOW-RENDERED-RGB-A-4B",
        b"SYNTHETIC-FLOW-RENDERED-RGB-B-4B",
    )
    source_width, source_height = 47, 43
    quadrilaterals = (
        SourceQuadrilateral(
            GeometryPoint(3, 5),
            GeometryPoint(31, 5),
            GeometryPoint(31, 23),
            GeometryPoint(3, 23),
        ),
        SourceQuadrilateral(
            GeometryPoint(7, 27),
            GeometryPoint(42, 27),
            GeometryPoint(42, 39),
            GeometryPoint(7, 39),
        ),
    )
    rendered_dimensions = ((28, 18), (35, 12))
    command = new_command(
        (
            RegionSetMemberInput(
                1,
                entity_id(100),
                new_selection(entity_id(100), entity_id(700), quadrilaterals[0]),
            ),
            RegionSetMemberInput(
                2,
                entity_id(200),
                new_selection(entity_id(200), entity_id(701), quadrilaterals[1]),
            ),
        )
    )
    assert len(command.members) == 2
    assert tuple(member.order_index for member in command.members) == (1, 2)

    factory = Factory()
    read, write = factory.units
    for unit in factory.units:
        source = next(iter(unit.source_files.committed.values()))
        unit.source_files.committed[source.id] = replace(
            source,
            original_basename=SourceBasename(source_basename),
            byte_size=len(source_bytes),
            sha256=source.sha256.__class__(source_plaintext_checksum),
            width=source_width,
            height=source_height,
        )
        stored = next(iter(unit.stored_artifacts.committed.values()))
        unit.stored_artifacts.committed[stored.artifact_id] = replace(
            stored,
            plaintext_length=len(source_bytes),
            plaintext_sha256=source_plaintext_checksum,
            ciphertext_sha256=artifact_ciphertext_checksum,
        )

    for unit in (read, write):
        source_snapshot = next(iter(unit.source_files.committed.values()))
        artifact_snapshot = next(iter(unit.stored_artifacts.committed.values()))
        assert source_snapshot.original_basename == SourceBasename(source_basename)
        assert source_snapshot.sha256.value == source_plaintext_checksum
        assert (source_snapshot.width, source_snapshot.height) == (
            source_width,
            source_height,
        )
        assert artifact_snapshot.plaintext_sha256 == source_plaintext_checksum
        assert artifact_snapshot.ciphertext_sha256 == artifact_ciphertext_checksum

    decoded_pixels = repeated_rgb(decoded_marker, source_width, source_height)
    decoded_media = DecodedGeometryMedia(
        SourceMediaType.JPEG,
        source_width,
        source_height,
        None,
        source_width,
        source_height,
        decoded_pixels,
    )
    rendered_rasters = tuple(
        RenderedGeometryRaster(
            width,
            height,
            repeated_rgb(marker, width, height),
            valid_geometry_recipe().pipeline,
        )
        for (width, height), marker in zip(rendered_dimensions, rendered_markers, strict=True)
    )

    class FlowStorage:
        def __init__(self) -> None:
            self.received: list[StoredArtifactRecord] = []

        def read_bytes(self, *, expected):
            self.received.append(expected)
            assert expected == next(iter(read.stored_artifacts.committed.values()))
            assert expected.plaintext_sha256 == source_plaintext_checksum
            assert expected.ciphertext_sha256 == artifact_ciphertext_checksum
            return source_bytes

        def publish_bytes(self, **_kwargs):
            raise AssertionError("storage publication")

    class FlowDecoder:
        def __init__(self) -> None:
            self.received: list[bytes] = []

        def decode_for_geometry(self, *, content):
            self.received.append(content)
            assert content == source_bytes
            return decoded_media

    class FlowRenderer:
        def __init__(self) -> None:
            self.received: list[tuple[DecodedGeometryMedia, SourceQuadrilateral]] = []
            self.returned: list[RenderedGeometryRaster] = []

        def render_geometry(self, *, media, quadrilateral, quarter_turn, pipeline):
            index = len(self.received)
            expected_quadrilateral = quadrilaterals[index]
            expected_raster = rendered_rasters[index]
            assert media == decoded_media
            assert media.rgb_pixels == decoded_pixels
            assert (media.effective_width, media.effective_height) == (
                source_width,
                source_height,
            )
            assert quadrilateral == expected_quadrilateral
            assert tuple((point.x, point.y) for point in quadrilateral.points) == tuple(
                (point.x, point.y) for point in expected_quadrilateral.points
            )
            assert quarter_turn == valid_geometry_recipe().quarter_turn
            assert pipeline == valid_geometry_recipe().pipeline
            self.received.append((media, quadrilateral))
            self.returned.append(expected_raster)
            return expected_raster

    storage = FlowStorage()
    decoder = FlowDecoder()
    renderer = FlowRenderer()
    result = confirm_document_regions(
        command,
        decoder=decoder,
        renderer=renderer,
        storage=storage,
        unit_of_work_factory=factory,
    )

    expected_artifact = next(iter(read.stored_artifacts.committed.values()))
    assert read.source_files.get_calls == [command.source_file_id]
    assert write.source_files.get_calls == [command.source_file_id]
    assert read.stored_artifacts.get_calls == [expected_artifact.artifact_id]
    assert write.stored_artifacts.get_calls == [expected_artifact.artifact_id]
    assert expected_artifact.artifact_kind is ArtifactKind.ORIGINAL
    assert storage.received == [expected_artifact]
    assert decoder.received == [source_bytes]
    assert renderer.received == [
        (decoded_media, quadrilaterals[0]),
        (decoded_media, quadrilaterals[1]),
    ]
    assert renderer.returned == list(rendered_rasters)
    assert tuple(recipe.quadrilateral for recipe in result.selected_recipes) == quadrilaterals
    assert tuple(
        (recipe.source_effective_width, recipe.source_effective_height)
        for recipe in result.selected_recipes
    ) == ((source_width, source_height), (source_width, source_height))

    events = tuple(write.audit_events.add_calls)
    assert len(events) == 3
    assert tuple(write.audit_events.committed.values()) == events
    assert tuple(event.event_id for event in events) == (
        entity_id(700),
        entity_id(701),
        command.region_set_audit_event_id,
    )
    assert tuple(event.action_code for event in events) == (
        AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
        AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
        AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
    )
    assert tuple(event.subject_id for event in events) == (
        entity_id(100),
        entity_id(200),
        command.region_set_version_id,
    )
    for event in events[:2]:
        assert event.occurred_at == command.confirmed_at
        assert event.actor == command.actor
        assert event.subject_type is AuditSubjectType.IMAGE_GEOMETRY_RECIPE
        assert event.field_key is None
        assert_summary(event.before, AuditValueClassification.ABSENT, None, False)
        assert_summary(
            event.after,
            AuditValueClassification.NON_SENSITIVE,
            "IMAGE_GEOMETRY_RECIPE",
            True,
        )
        assert event.reason_code is not None
        assert event.reason_code.value == "IMAGE_GEOMETRY_RECIPE_CREATED"
        assert event.correlation_id == command.correlation_id
    set_event = events[2]
    assert set_event.occurred_at == command.confirmed_at
    assert set_event.actor == command.actor
    assert set_event.subject_type is AuditSubjectType.DOCUMENT_REGION_SET
    assert set_event.field_key is None
    assert_summary(set_event.before, AuditValueClassification.ABSENT, None, False)
    assert_summary(
        set_event.after,
        AuditValueClassification.NON_SENSITIVE,
        "DOCUMENT_REGION_SET",
        True,
    )
    assert set_event.reason_code is not None
    assert set_event.reason_code.value == "DOCUMENT_REGION_SET_CONFIRMED"
    assert set_event.correlation_id == command.correlation_id

    serialized = tuple(ser.audit_event_to_json(event) for event in events)
    parsed = tuple(assert_exact_serialized_audit_surface(payload) for payload in serialized)
    native_private_integers = {
        source_width,
        source_height,
        *(
            coordinate
            for quad in quadrilaterals
            for point in quad.points
            for coordinate in (point.x, point.y)
        ),
        *(dimension for raster in rendered_rasters for dimension in (raster.width, raster.height)),
    }
    serialized_integer_leaves = {
        leaf for payload in parsed for leaf in json_leaf_values(payload) if type(leaf) is int
    }
    assert native_private_integers.isdisjoint(serialized_integer_leaves)
    assert all(
        payload["before"]
        == {
            "classification": "ABSENT",
            "display_value": None,
            "was_present": False,
        }
        for payload in parsed
    )
    assert tuple(payload["after"]["display_value"] for payload in parsed) == (
        "IMAGE_GEOMETRY_RECIPE",
        "IMAGE_GEOMETRY_RECIPE",
        "DOCUMENT_REGION_SET",
    )
    assert all(
        {"region_count", "members", "order_index", "quadrilateral", "coordinates"}.isdisjoint(
            payload
        )
        for payload in parsed
    )
    representations = (
        *(str(event) for event in events),
        *(repr(event) for event in events),
        *serialized,
        repr(write.audit_events.add_calls),
        repr(write.audit_events.items),
    )
    flow_carried_string_markers = {
        source_basename,
        source_plaintext_checksum,
        artifact_ciphertext_checksum,
        source_bytes.decode(),
        decoded_marker.decode(),
        *(marker.decode() for marker in rendered_markers),
    }
    for marker in flow_carried_string_markers:
        assert all(marker not in representation for representation in representations)


def test_non_pr012_private_categories_are_structurally_unreachable_from_audits() -> None:
    """These categories are structurally unavailable to the PR-012 audit
    construction path; they were not runtime-injected markers.
    """
    assert {field.name for field in fields(ConfirmDocumentRegionsCommand)} == {
        "region_set_version_id",
        "source_file_id",
        "superseded_region_set_version_id",
        "set_revision",
        "members",
        "region_set_audit_event_id",
        "confirmed_at",
        "actor",
        "correlation_id",
    }
    assert {field.name for field in fields(RegionSetMemberInput)} == {
        "order_index",
        "region_id",
        "recipe_selection",
    }
    assert {field.name for field in fields(ExistingRecipeSelection)} == {
        "geometry_recipe_version_id"
    }
    assert {field.name for field in fields(NewRecipeRevision)} == {
        "recipe_version_id",
        "superseded_recipe_version_id",
        "recipe_revision",
        "quadrilateral",
        "quarter_turn",
        "recipe_audit_event_id",
    }
    assert {field.name for field in fields(SourceFile)} == {
        "id",
        "batch_id",
        "original_artifact_id",
        "original_basename",
        "detected_media_type",
        "byte_size",
        "sha256",
        "perceptual_hash",
        "width",
        "height",
        "exif_orientation",
        "imported_at",
        "imported_by",
    }
    assert {field.name for field in fields(StoredArtifactRecord)} == {
        "artifact_id",
        "artifact_kind",
        "object_generation",
        "plaintext_length",
        "plaintext_sha256",
        "ciphertext_sha256",
        "key_version",
        "storage_format_version",
        "created_at",
    }
    assert {field.name for field in fields(DecodedGeometryMedia)} == {
        "media_type",
        "encoded_width",
        "encoded_height",
        "exif_orientation",
        "effective_width",
        "effective_height",
        "rgb_pixels",
    }
    assert {field.name for field in fields(RenderedGeometryRaster)} == {
        "width",
        "height",
        "rgb_pixels",
        "pipeline",
    }
    assert {field.name for field in fields(AuditEvent)} == {
        "event_id",
        "occurred_at",
        "actor",
        "action_code",
        "subject_type",
        "subject_id",
        "field_key",
        "before",
        "after",
        "reason_code",
        "correlation_id",
    }

    service_parameters = signature(confirm_document_regions).parameters
    assert tuple(service_parameters) == (
        "command",
        "decoder",
        "renderer",
        "storage",
        "unit_of_work_factory",
    )
    assert service_parameters["command"].kind is Parameter.POSITIONAL_OR_KEYWORD
    assert all(
        service_parameters[name].kind is Parameter.KEYWORD_ONLY
        for name in ("decoder", "renderer", "storage", "unit_of_work_factory")
    )
    assert tuple(signature(GeometryDecoderPort.decode_for_geometry).parameters) == (
        "self",
        "content",
    )
    assert tuple(signature(GeometryRendererPort.render_geometry).parameters) == (
        "self",
        "media",
        "quadrilateral",
        "quarter_turn",
        "pipeline",
    )
    assert tuple(signature(StoragePort.read_bytes).parameters) == ("self", "expected")

    command = new_command((new_member(1, 100, 700),))
    events = audit_events(command, Factory())
    parsed = tuple(
        assert_exact_serialized_audit_surface(ser.audit_event_to_json(event)) for event in events
    )
    assert len(parsed) == 2
    assert all(set(payload) == AUDIT_JSON_KEYS for payload in parsed)
