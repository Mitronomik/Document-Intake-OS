from __future__ import annotations

import json
from dataclasses import replace

import pytest

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ExistingRecipeSelection,
    RegionSetMemberInput,
)
from document_intake.application.ports.media import DecodedGeometryMedia, RenderedGeometryRaster
from document_intake.application.services.document_regions import confirm_document_regions
from document_intake.domain.document_regions import (
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
from document_intake.domain.enums import (
    AuditAction,
    AuditSubjectType,
    AuditValueClassification,
    SourceMediaType,
)
from document_intake.domain.value_objects.imports import SourceBasename
from document_intake.persistence import serialization as ser
from tests.support.pr011 import STAMP, actor, correlation_id, entity_id, valid_geometry_recipe
from tests.support.pr012_application import (
    Decoder,
    Factory,
    Renderer,
    Storage,
    new_selection,
    run,
    with_previous,
)

DEFAULT_CORRELATION = correlation_id()


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


def test_complete_forbidden_value_provenance_is_absent_from_actual_audits() -> None:
    markers = {
        "private-source-basename.jpg",
        "private-local-path-marker",
        "a1b2c3d4" * 8,
        "c3d4e5f6" * 8,
        "PRIVATEBYTES",
        "private-coordinate-marker",
        "private-effective-dimensions-32x24",
        "private-rendered-dimensions-31x23",
        "private-region-count-1",
        "private-member-order-1",
        "private-document-type-marker",
        "private-document-side-marker",
        "private-owner-marker",
        "private-ocr-marker",
        "private-personal-data-marker",
        "private-raw-sql-marker",
        "private-raw-exception-marker",
        "private-prepared-jpeg-marker",
        "private-jpeg-quality-marker",
        "private-jpeg-resize-marker",
    }
    command = new_command((new_member(1, 100, 700),))
    factory = Factory()
    for unit in factory.units:
        source = next(iter(unit.source_files.committed.values()))
        unit.source_files.committed[source.id] = replace(
            source,
            original_basename=SourceBasename("private-source-basename.jpg"),
            sha256=source.sha256.__class__("a1b2c3d4" * 8),
        )
        stored = next(iter(unit.stored_artifacts.committed.values()))
        unit.stored_artifacts.committed[stored.artifact_id] = replace(
            stored,
            plaintext_sha256="a1b2c3d4" * 8,
            ciphertext_sha256="c3d4e5f6" * 8,
        )
    calls = []

    class ObservedStorage(Storage):
        def __init__(self):
            super().__init__(calls)
            self.privacy_context = tuple(sorted(markers))
            self.observed: set[str] = set()

        def read_bytes(self, *, expected):
            self.observed.update(self.privacy_context)
            assert expected.plaintext_sha256 == "a1b2c3d4" * 8
            assert expected.ciphertext_sha256 == "c3d4e5f6" * 8
            self.calls.append("storage.read")
            return b"PRIVATEBYTES"

    class ObservedDecoder(Decoder):
        def __init__(self):
            super().__init__(calls)
            self.privacy_context = tuple(sorted(markers))
            self.observed: set[str] = set()

        def decode_for_geometry(self, *, content):
            self.observed.update(self.privacy_context)
            assert content == b"PRIVATEBYTES"
            self.calls.append("decode")
            pixels = (b"PRIVATEDECODEDPIXELS" * 128)[: 32 * 24 * 3]
            return DecodedGeometryMedia(SourceMediaType.JPEG, 32, 24, None, 32, 24, pixels)

    class ObservedRenderer(Renderer):
        def __init__(self):
            super().__init__(calls)
            self.privacy_context = tuple(sorted(markers))
            self.observed: set[str] = set()

        def render_geometry(self, *, media, quadrilateral, quarter_turn, pipeline):
            del quarter_turn
            self.observed.update(self.privacy_context)
            assert b"PRIVATEDECODEDPIXELS" in media.rgb_pixels
            assert tuple(point.x for point in quadrilateral.points) == (0, 32, 32, 0)
            self.calls.append("render")
            pixels = (b"PRIVATERENDEREDPIXELS" * 128)[: 32 * 24 * 3]
            return RenderedGeometryRaster(32, 24, pixels, pipeline)

    storage = ObservedStorage()
    decoder = ObservedDecoder()
    renderer = ObservedRenderer()
    write = factory.units[1]
    confirm_document_regions(
        command,
        decoder=decoder,
        renderer=renderer,
        storage=storage,
        unit_of_work_factory=factory,
    )
    events = tuple(write.audit_events.add_calls)
    assert len(events) == 2
    assert storage.observed | decoder.observed | renderer.observed == markers
    serialized = tuple(ser.audit_event_to_json(event) for event in events)
    allowed_keys = {
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
    assert all(set(json.loads(payload)) == allowed_keys for payload in serialized)
    representations = (
        *(str(event) for event in events),
        *(repr(event) for event in events),
        *serialized,
        repr(write.audit_events.add_calls),
        repr(write.audit_events.items),
    )
    for marker in markers:
        assert marker in repr(storage.privacy_context)
        assert all(marker not in representation for representation in representations)
