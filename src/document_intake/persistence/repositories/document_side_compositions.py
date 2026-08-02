"""Create-only repository for deterministic document-side compositions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from document_intake.domain.document_side_composition import (
    DocumentSideComposition,
    DocumentSideCompositionVersion,
    PreparedCompositionArtifact,
)
from document_intake.domain.enums import DocumentSideCompositionLayout
from document_intake.domain.value_objects import EntityId
from document_intake.persistence import composition_serialization as ser
from document_intake.persistence.database import _Repo
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode

if TYPE_CHECKING:
    from document_intake.persistence.database import SqlCipherUnitOfWork


class DocumentSideCompositionRepo(_Repo):
    _VERSION_SELECT = (
        "SELECT id,composition_id,side_1_region_set_version_id,side_1_source_file_id,"
        "side_1_region_id,side_1_geometry_recipe_version_id,side_2_region_set_version_id,"
        "side_2_source_file_id,side_2_region_id,side_2_geometry_recipe_version_id,layout,"
        "outer_margin_px,inter_side_gap_px,composition_pipeline_id,composition_pipeline_version,"
        "jpeg_pipeline_id,jpeg_pipeline_version,output_contract_id,output_contract_version,"
        "created_at_utc,created_by_id,created_by_kind,correlation_id,canonical_payload "
        "FROM document_side_composition_versions"
    )
    _ARTIFACT_SELECT = (
        "SELECT id,composition_version_id,stored_artifact_id,pipeline_id,pipeline_version,"
        "output_contract_id,output_contract_version,media_type,color_space,width,height,byte_size,"
        "sha256,jpeg_quality,resize_percent,created_at_utc,created_by_id,created_by_kind,"
        "canonical_payload FROM prepared_composition_artifacts"
    )

    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow, "document_side_compositions", lambda _: "", lambda _: None, lambda x: str(x.id)
        )

    def add_composition(self, composition: DocumentSideComposition) -> None:
        if not isinstance(composition, DocumentSideComposition):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        self._execute(
            "INSERT INTO document_side_compositions(id) VALUES(?)",
            (str(composition.id),),
            duplicate_is_already_exists=True,
        )

    def add_version(self, version: DocumentSideCompositionVersion) -> None:
        if not isinstance(version, DocumentSideCompositionVersion):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        self._execute(
            "INSERT INTO document_side_composition_versions(id,composition_id,side_1_region_set_version_id,side_1_source_file_id,side_1_region_id,side_1_geometry_recipe_version_id,side_2_region_set_version_id,side_2_source_file_id,side_2_region_id,side_2_geometry_recipe_version_id,layout,outer_margin_px,inter_side_gap_px,composition_pipeline_id,composition_pipeline_version,jpeg_pipeline_id,jpeg_pipeline_version,output_contract_id,output_contract_version,created_at_utc,created_by_id,created_by_kind,correlation_id,canonical_payload) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",  # noqa: E501
            (*ser.composition_version_columns(version), ser.composition_version_to_json(version)),
            duplicate_is_already_exists=True,
        )

    def add_artifact(self, artifact: PreparedCompositionArtifact) -> None:
        if not isinstance(artifact, PreparedCompositionArtifact):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        self._execute(
            "INSERT INTO prepared_composition_artifacts(id,composition_version_id,stored_artifact_id,pipeline_id,pipeline_version,output_contract_id,output_contract_version,media_type,color_space,width,height,byte_size,sha256,jpeg_quality,resize_percent,created_at_utc,created_by_id,created_by_kind,canonical_payload) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",  # noqa: E501
            (*ser.prepared_artifact_columns(artifact), ser.prepared_artifact_to_json(artifact)),
            duplicate_is_already_exists=True,
        )

    def get_composition(self, composition_id: EntityId) -> DocumentSideComposition | None:
        rows = self._fetchall(
            "SELECT id FROM document_side_compositions WHERE id=?", (str(composition_id),)
        )
        if len(rows) > 1:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return None if not rows else DocumentSideComposition(EntityId.parse(rows[0][0]))

    def _version(self, row: tuple[Any, ...]) -> DocumentSideCompositionVersion:
        version = ser.composition_version_from_json(row[23])
        if (
            ser.composition_version_columns(version) != tuple(row[:23])
            or ser.composition_version_to_json(version) != row[23]
        ):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return version

    def _artifact(self, row: tuple[Any, ...]) -> PreparedCompositionArtifact:
        artifact = ser.prepared_artifact_from_json(row[18])
        if (
            ser.prepared_artifact_columns(artifact) != tuple(row[:18])
            or ser.prepared_artifact_to_json(artifact) != row[18]
        ):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return artifact

    def _versions(
        self, where: str, args: tuple[Any, ...]
    ) -> tuple[DocumentSideCompositionVersion, ...]:
        return tuple(
            self._version(row)
            for row in self._fetchall(f"{self._VERSION_SELECT} WHERE {where}", args)
        )

    def _artifacts(
        self, where: str, args: tuple[Any, ...]
    ) -> tuple[PreparedCompositionArtifact, ...]:
        return tuple(
            self._artifact(row)
            for row in self._fetchall(f"{self._ARTIFACT_SELECT} WHERE {where}", args)
        )

    def get_version(
        self, composition_version_id: EntityId
    ) -> DocumentSideCompositionVersion | None:
        rows = self._versions("id=?", (str(composition_version_id),))
        if len(rows) > 1:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return rows[0] if rows else None

    def get_artifact(self, prepared_artifact_id: EntityId) -> PreparedCompositionArtifact | None:
        rows = self._artifacts("id=?", (str(prepared_artifact_id),))
        if len(rows) > 1:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return rows[0] if rows else None

    def get_artifact_by_composition_version(
        self, composition_version_id: EntityId
    ) -> PreparedCompositionArtifact | None:
        rows = self._artifacts("composition_version_id=?", (str(composition_version_id),))
        if len(rows) > 1:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return rows[0] if rows else None

    def get_by_natural_key(
        self,
        *,
        side_1_region_set_version_id: EntityId,
        side_1_source_file_id: EntityId,
        side_1_region_id: EntityId,
        side_1_geometry_recipe_version_id: EntityId,
        side_2_region_set_version_id: EntityId,
        side_2_source_file_id: EntityId,
        side_2_region_id: EntityId,
        side_2_geometry_recipe_version_id: EntityId,
        layout: DocumentSideCompositionLayout,
        outer_margin_px: int,
        inter_side_gap_px: int,
        composition_pipeline_id: str,
        composition_pipeline_version: int,
        jpeg_pipeline_id: str,
        jpeg_pipeline_version: int,
        output_contract_id: str,
        output_contract_version: int,
    ) -> DocumentSideCompositionVersion | None:
        fields = (
            side_1_region_set_version_id,
            side_1_source_file_id,
            side_1_region_id,
            side_1_geometry_recipe_version_id,
            side_2_region_set_version_id,
            side_2_source_file_id,
            side_2_region_id,
            side_2_geometry_recipe_version_id,
        )
        args: tuple[Any, ...] = (
            *(str(value) for value in fields),
            layout.value,
            outer_margin_px,
            inter_side_gap_px,
            composition_pipeline_id,
            composition_pipeline_version,
            jpeg_pipeline_id,
            jpeg_pipeline_version,
            output_contract_id,
            output_contract_version,
        )
        where = (
            "side_1_region_set_version_id=? AND side_1_source_file_id=? AND side_1_region_id=? "
            "AND side_1_geometry_recipe_version_id=? AND side_2_region_set_version_id=? "
            "AND side_2_source_file_id=? AND side_2_region_id=? "
            "AND side_2_geometry_recipe_version_id=? AND layout=? AND outer_margin_px=? "
            "AND inter_side_gap_px=? AND composition_pipeline_id=? "
            "AND composition_pipeline_version=? AND jpeg_pipeline_id=? "
            "AND jpeg_pipeline_version=? AND output_contract_id=? AND output_contract_version=?"
        )
        rows = self._versions(where, args)
        if len(rows) > 1:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return rows[0] if rows else None
