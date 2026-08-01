from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_intake.domain.document_regions import (
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
from document_intake.domain.enums import ActorKind
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.value_objects import ActorRef, EntityId


def eid(n: int) -> EntityId:
    return EntityId(UUID(int=n))


def member(n: int) -> DocumentRegionSetMember:
    return DocumentRegionSetMember(n, eid(n), eid(n + 10))


def region_set(*members: DocumentRegionSetMember) -> DocumentRegionSetVersion:
    return DocumentRegionSetVersion(
        eid(30),
        eid(31),
        None,
        1,
        tuple(members),
        datetime(2026, 7, 28, tzinfo=UTC),
        ActorRef(eid(32), ActorKind.OPERATOR),
    )


def test_one_and_two_members_are_ordered_and_immutable() -> None:
    assert region_set(member(1)).members == (member(1),)
    assert len(region_set(member(1), member(2)).members) == 2
    with pytest.raises(FrozenInstanceError):
        region_set(member(1)).revision = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    "members", [(), (member(1), member(2), DocumentRegionSetMember(2, eid(3), eid(13)))]
)
def test_invalid_count_is_rejected(members: tuple[DocumentRegionSetMember, ...]) -> None:
    with pytest.raises(InvalidValueError):
        region_set(*members)


def test_duplicate_region_and_recipe_are_rejected() -> None:
    with pytest.raises(InvalidValueError):
        region_set(member(1), DocumentRegionSetMember(2, eid(1), eid(12)))
    with pytest.raises(InvalidValueError):
        region_set(member(1), DocumentRegionSetMember(2, eid(2), eid(11)))


def test_repr_is_redacted() -> None:
    value = region_set(member(1))
    rendered = repr(value)
    assert str(value.source_file_id) not in rendered and "<redacted>" in rendered
