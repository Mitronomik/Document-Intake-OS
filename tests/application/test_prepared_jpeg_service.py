from __future__ import annotations

import inspect
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from document_intake.application.dto.prepared_jpeg import PrepareJpegCommand
from document_intake.application.services.prepared_jpeg import prepare_geometry_recipe_as_jpeg
from document_intake.domain.enums import ActorKind
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.prepared_jpeg import PreparedJpegError, PreparedJpegErrorCode
from document_intake.domain.value_objects import ActorRef, EntityId


def eid(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def command() -> PrepareJpegCommand:
    return PrepareJpegCommand(
        eid(1),
        eid(2),
        eid(3),
        eid(4),
        datetime(2026, 7, 26, tzinfo=UTC),
        ActorRef(eid(9), ActorKind.SYSTEM),
        eid(5),
    )


class Repo:
    def get(self, value: object) -> None:
        return None


class Uow:
    image_geometry_recipes = Repo()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Factory:
    def unit_of_work(self):
        return Uow()


def test_service_public_signature_is_recipe_specific() -> None:
    assert tuple(inspect.signature(prepare_geometry_recipe_as_jpeg).parameters) == (
        "command",
        "decoder",
        "renderer",
        "encoder",
        "storage",
        "unit_of_work_factory",
    )


def test_missing_recipe_is_controlled_before_publication() -> None:
    storage = SimpleNamespace(publish_bytes=lambda **kwargs: pytest.fail("published"))
    with pytest.raises(PreparedJpegError) as exc:
        prepare_geometry_recipe_as_jpeg(
            command(),
            decoder=object(),
            renderer=object(),
            encoder=object(),
            storage=storage,
            unit_of_work_factory=Factory(),
        )  # type: ignore[arg-type]
    assert exc.value.code is PreparedJpegErrorCode.GEOMETRY_RECIPE_NOT_FOUND
    assert exc.value.__cause__ is None


def test_duplicate_caller_ids_are_rejected_by_command() -> None:
    with pytest.raises(InvalidValueError):
        PrepareJpegCommand(
            eid(1),
            eid(1),
            eid(3),
            eid(4),
            datetime(2026, 7, 26, tzinfo=UTC),
            ActorRef(eid(9), ActorKind.SYSTEM),
            eid(5),
        )
