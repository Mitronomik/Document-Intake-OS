"""Canonical document-region-set aggregate serialization."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

from document_intake.domain.document_regions import (
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
from document_intake.domain.enums import ActorKind
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode


def _invalid() -> None:
    raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)


def _dict(value: Any, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        _invalid()
    return cast(dict[str, Any], value)


def _string(value: Any) -> str:
    if type(value) is not str:
        _invalid()
    return cast(str, value)


def _integer(value: Any) -> int:
    if type(value) is not int:
        _invalid()
    return cast(int, value)


def _time(value: Any) -> datetime:
    result = datetime.fromisoformat(_string(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        _invalid()
    return result


def document_region_set_to_json(value: DocumentRegionSetVersion) -> str:
    raw = {
        "region_set_version_id": str(value.region_set_version_id),
        "source_file_id": str(value.source_file_id),
        "superseded_region_set_version_id": None
        if value.superseded_region_set_version_id is None
        else str(value.superseded_region_set_version_id),
        "revision": value.revision,
        "members": [
            {
                "order_index": m.order_index,
                "region_id": str(m.region_id),
                "geometry_recipe_version_id": str(m.geometry_recipe_version_id),
            }
            for m in value.members
        ],
        "confirmed_at": value.confirmed_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "confirmed_by": {
            "actor_id": str(value.confirmed_by.actor_id),
            "kind": value.confirmed_by.kind.value,
        },
    }
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False)


def document_region_set_from_json(payload: str) -> DocumentRegionSetVersion:
    try:
        raw = _dict(
            json.loads(payload),
            {
                "region_set_version_id",
                "source_file_id",
                "superseded_region_set_version_id",
                "revision",
                "members",
                "confirmed_at",
                "confirmed_by",
            },
        )
        actor = _dict(raw["confirmed_by"], {"actor_id", "kind"})
        if type(raw["members"]) is not list:
            _invalid()
        members = tuple(
            DocumentRegionSetMember(
                _integer(m["order_index"]),
                EntityId.parse(_string(m["region_id"])),
                EntityId.parse(_string(m["geometry_recipe_version_id"])),
            )
            for m in raw["members"]
            if _dict(m, {"order_index", "region_id", "geometry_recipe_version_id"})
        )
        predecessor = raw["superseded_region_set_version_id"]
        return DocumentRegionSetVersion(
            EntityId.parse(_string(raw["region_set_version_id"])),
            EntityId.parse(_string(raw["source_file_id"])),
            None if predecessor is None else EntityId.parse(_string(predecessor)),
            _integer(raw["revision"]),
            members,
            _time(raw["confirmed_at"]),
            ActorRef(EntityId.parse(_string(actor["actor_id"])), ActorKind(_string(actor["kind"]))),
        )
    except PersistenceError:
        raise
    except Exception:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None
