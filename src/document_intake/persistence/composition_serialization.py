"""Strict canonical serialization for PR-013 immutable composition records."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

from document_intake.domain.document_side_composition import (
    DocumentSideCompositionVersion,
    PreparedCompositionArtifact,
)
from document_intake.domain.enums import (
    ActorKind,
    ColorSpace,
    DocumentSideCompositionLayout,
    PreparedMediaType,
)
from document_intake.domain.value_objects import ActorRef, EntityId, Sha256Digest
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode


def _invalid() -> None:
    raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)


def _dict(value: Any, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        _invalid()
    return cast(dict[str, Any], value)


def _str(value: Any) -> str:
    if type(value) is not str:
        _invalid()
    return cast(str, value)


def _int(value: Any) -> int:
    if type(value) is not int:
        _invalid()
    return cast(int, value)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _time(value: Any) -> datetime:
    parsed = datetime.fromisoformat(_str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        _invalid()
    return parsed


def _dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _actor_to_json(actor: ActorRef) -> dict[str, str]:
    return {"actor_id": str(actor.actor_id), "kind": actor.kind.value}


def _actor(value: Any) -> ActorRef:
    raw = _dict(value, {"actor_id", "kind"})
    return ActorRef(EntityId.parse(_str(raw["actor_id"])), ActorKind(_str(raw["kind"])))


def composition_version_to_json(value: DocumentSideCompositionVersion) -> str:
    return _dumps(
        {
            "id": str(value.id),
            "composition_id": str(value.composition_id),
            "side_1_region_set_version_id": str(value.side_1_region_set_version_id),
            "side_1_source_file_id": str(value.side_1_source_file_id),
            "side_1_region_id": str(value.side_1_region_id),
            "side_1_geometry_recipe_version_id": str(value.side_1_geometry_recipe_version_id),
            "side_2_region_set_version_id": str(value.side_2_region_set_version_id),
            "side_2_source_file_id": str(value.side_2_source_file_id),
            "side_2_region_id": str(value.side_2_region_id),
            "side_2_geometry_recipe_version_id": str(value.side_2_geometry_recipe_version_id),
            "layout": value.layout.value,
            "outer_margin_px": value.outer_margin_px,
            "inter_side_gap_px": value.inter_side_gap_px,
            "composition_pipeline_id": value.composition_pipeline_id,
            "composition_pipeline_version": value.composition_pipeline_version,
            "jpeg_pipeline_id": value.jpeg_pipeline_id,
            "jpeg_pipeline_version": value.jpeg_pipeline_version,
            "output_contract_id": value.output_contract_id,
            "output_contract_version": value.output_contract_version,
            "created_at": _utc(value.created_at),
            "created_by": _actor_to_json(value.created_by),
            "correlation_id": str(value.correlation_id),
        }
    )


_VERSION_KEYS = {
    "id",
    "composition_id",
    "side_1_region_set_version_id",
    "side_1_source_file_id",
    "side_1_region_id",
    "side_1_geometry_recipe_version_id",
    "side_2_region_set_version_id",
    "side_2_source_file_id",
    "side_2_region_id",
    "side_2_geometry_recipe_version_id",
    "layout",
    "outer_margin_px",
    "inter_side_gap_px",
    "composition_pipeline_id",
    "composition_pipeline_version",
    "jpeg_pipeline_id",
    "jpeg_pipeline_version",
    "output_contract_id",
    "output_contract_version",
    "created_at",
    "created_by",
    "correlation_id",
}


def composition_version_from_json(payload: str) -> DocumentSideCompositionVersion:
    try:
        raw = _dict(json.loads(payload), _VERSION_KEYS)
        return DocumentSideCompositionVersion(
            EntityId.parse(_str(raw["id"])),
            EntityId.parse(_str(raw["composition_id"])),
            EntityId.parse(_str(raw["side_1_region_set_version_id"])),
            EntityId.parse(_str(raw["side_1_source_file_id"])),
            EntityId.parse(_str(raw["side_1_region_id"])),
            EntityId.parse(_str(raw["side_1_geometry_recipe_version_id"])),
            EntityId.parse(_str(raw["side_2_region_set_version_id"])),
            EntityId.parse(_str(raw["side_2_source_file_id"])),
            EntityId.parse(_str(raw["side_2_region_id"])),
            EntityId.parse(_str(raw["side_2_geometry_recipe_version_id"])),
            DocumentSideCompositionLayout(_str(raw["layout"])),
            _int(raw["outer_margin_px"]),
            _int(raw["inter_side_gap_px"]),
            _str(raw["composition_pipeline_id"]),
            _int(raw["composition_pipeline_version"]),
            _str(raw["jpeg_pipeline_id"]),
            _int(raw["jpeg_pipeline_version"]),
            _str(raw["output_contract_id"]),
            _int(raw["output_contract_version"]),
            _time(raw["created_at"]),
            _actor(raw["created_by"]),
            EntityId.parse(_str(raw["correlation_id"])),
        )
    except PersistenceError:
        raise
    except Exception:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None


def composition_version_columns(value: DocumentSideCompositionVersion) -> tuple[Any, ...]:
    return (
        str(value.id),
        str(value.composition_id),
        str(value.side_1_region_set_version_id),
        str(value.side_1_source_file_id),
        str(value.side_1_region_id),
        str(value.side_1_geometry_recipe_version_id),
        str(value.side_2_region_set_version_id),
        str(value.side_2_source_file_id),
        str(value.side_2_region_id),
        str(value.side_2_geometry_recipe_version_id),
        value.layout.value,
        value.outer_margin_px,
        value.inter_side_gap_px,
        value.composition_pipeline_id,
        value.composition_pipeline_version,
        value.jpeg_pipeline_id,
        value.jpeg_pipeline_version,
        value.output_contract_id,
        value.output_contract_version,
        _utc(value.created_at),
        str(value.created_by.actor_id),
        value.created_by.kind.value,
        str(value.correlation_id),
    )


def prepared_artifact_to_json(value: PreparedCompositionArtifact) -> str:
    return _dumps(
        {
            "id": str(value.id),
            "composition_version_id": str(value.composition_version_id),
            "stored_artifact_id": str(value.stored_artifact_id),
            "pipeline_id": value.pipeline_id,
            "pipeline_version": value.pipeline_version,
            "output_contract_id": value.output_contract_id,
            "output_contract_version": value.output_contract_version,
            "media_type": value.media_type.value,
            "color_space": value.color_space.value,
            "width": value.width,
            "height": value.height,
            "byte_size": value.byte_size,
            "sha256": value.sha256.value,
            "jpeg_quality": value.jpeg_quality,
            "resize_percent": value.resize_percent,
            "created_at": _utc(value.created_at),
            "created_by": _actor_to_json(value.created_by),
        }
    )


_ARTIFACT_KEYS = {
    "id",
    "composition_version_id",
    "stored_artifact_id",
    "pipeline_id",
    "pipeline_version",
    "output_contract_id",
    "output_contract_version",
    "media_type",
    "color_space",
    "width",
    "height",
    "byte_size",
    "sha256",
    "jpeg_quality",
    "resize_percent",
    "created_at",
    "created_by",
}


def prepared_artifact_from_json(payload: str) -> PreparedCompositionArtifact:
    try:
        raw = _dict(json.loads(payload), _ARTIFACT_KEYS)
        return PreparedCompositionArtifact(
            EntityId.parse(_str(raw["id"])),
            EntityId.parse(_str(raw["composition_version_id"])),
            EntityId.parse(_str(raw["stored_artifact_id"])),
            _str(raw["pipeline_id"]),
            _int(raw["pipeline_version"]),
            _str(raw["output_contract_id"]),
            _int(raw["output_contract_version"]),
            PreparedMediaType(_str(raw["media_type"])),
            ColorSpace(_str(raw["color_space"])),
            _int(raw["width"]),
            _int(raw["height"]),
            _int(raw["byte_size"]),
            Sha256Digest(_str(raw["sha256"])),
            _int(raw["jpeg_quality"]),
            _int(raw["resize_percent"]),
            _time(raw["created_at"]),
            _actor(raw["created_by"]),
        )
    except PersistenceError:
        raise
    except Exception:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None


def prepared_artifact_columns(value: PreparedCompositionArtifact) -> tuple[Any, ...]:
    return (
        str(value.id),
        str(value.composition_version_id),
        str(value.stored_artifact_id),
        value.pipeline_id,
        value.pipeline_version,
        value.output_contract_id,
        value.output_contract_version,
        value.media_type.value,
        value.color_space.value,
        value.width,
        value.height,
        value.byte_size,
        value.sha256.value,
        value.jpeg_quality,
        value.resize_percent,
        _utc(value.created_at),
        str(value.created_by.actor_id),
        value.created_by.kind.value,
    )
