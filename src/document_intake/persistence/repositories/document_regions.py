"""Scoped immutable document-region-set repository."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from document_intake.domain.document_regions import DocumentRegionSetVersion
from document_intake.domain.value_objects import EntityId
from document_intake.persistence import serialization as ser
from document_intake.persistence.database import _Repo
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode

if TYPE_CHECKING:
    from document_intake.persistence.database import SqlCipherUnitOfWork


class DocumentRegionSetRepo(_Repo):
    _SELECT = (
        "SELECT "
        "region_set_version_id,source_file_id,superseded_region_set_version_id,"
        "revision,confirmed_at_utc,confirmed_by_actor_id,confirmed_by_actor_kind,"
        "canonical_payload "
        "FROM document_region_set_versions"
    )

    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow,
            "document_region_set_versions",
            ser.document_region_set_to_json,
            ser.document_region_set_from_json,
            lambda x: str(x.region_set_version_id),
        )

    def add(self, region_set: DocumentRegionSetVersion) -> None:
        payload = ser.document_region_set_to_json(region_set)
        with self._atomic_write():
            self._execute(
                (
                    "INSERT INTO "
                    "document_region_set_versions(region_set_version_id,source_file_id,"
                    "superseded_region_set_version_id,revision,confirmed_at_utc,"
                    "confirmed_by_actor_id,confirmed_by_actor_kind,canonical_payload) "
                    "VALUES(?,?,?,?,?,?,?,?)"
                ),
                (
                    str(region_set.region_set_version_id),
                    str(region_set.source_file_id),
                    None
                    if region_set.superseded_region_set_version_id is None
                    else str(region_set.superseded_region_set_version_id),
                    region_set.revision,
                    ser.utc_iso(region_set.confirmed_at),
                    str(region_set.confirmed_by.actor_id),
                    region_set.confirmed_by.kind.value,
                    payload,
                ),
                duplicate_is_already_exists=True,
            )
            for member in region_set.members:
                self._execute(
                    (
                        "INSERT INTO "
                        "document_region_set_members(region_set_version_id,order_index,region_id,"
                        "geometry_recipe_version_id) "
                        "VALUES(?,?,?,?)"
                    ),
                    (
                        str(region_set.region_set_version_id),
                        member.order_index,
                        str(member.region_id),
                        str(member.geometry_recipe_version_id),
                    ),
                    duplicate_is_already_exists=True,
                )

    def _deserialize_row(self, row: tuple[Any, ...]) -> DocumentRegionSetVersion:
        entity = cast(DocumentRegionSetVersion, self._deserialize(row[7]))
        members = self._fetchall(
            (
                "SELECT order_index,region_id,geometry_recipe_version_id FROM "
                "document_region_set_members WHERE region_set_version_id=? ORDER BY order_index"
            ),
            (row[0],),
        )
        projection = (
            str(entity.region_set_version_id),
            str(entity.source_file_id),
            None
            if entity.superseded_region_set_version_id is None
            else str(entity.superseded_region_set_version_id),
            entity.revision,
            ser.utc_iso(entity.confirmed_at),
            str(entity.confirmed_by.actor_id),
            entity.confirmed_by.kind.value,
        )
        expected = tuple(
            (m.order_index, str(m.region_id), str(m.geometry_recipe_version_id))
            for m in entity.members
        )
        if (
            projection != tuple(row[:7])
            or expected != members
            or ser.document_region_set_to_json(entity) != row[7]
        ):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        for member in entity.members:
            recipe = self._uow.image_geometry_recipes.get(member.geometry_recipe_version_id)
            if (
                recipe is None
                or recipe.source_file_id != entity.source_file_id
                or recipe.region_id != member.region_id
            ):
                raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return entity

    def _query(self, where: str, args: tuple[Any, ...]) -> tuple[DocumentRegionSetVersion, ...]:
        rows = self._fetchall(
            f"{self._SELECT} WHERE {where} ORDER BY "
            "revision,confirmed_at_utc,region_set_version_id",
            args,
        )
        return tuple(self._deserialize_row(row) for row in rows)

    def _validate_chain(
        self, sets: tuple[DocumentRegionSetVersion, ...], source_id: EntityId
    ) -> tuple[DocumentRegionSetVersion, ...]:
        for index, item in enumerate(sets, 1):
            if item.source_file_id != source_id or item.revision != index:
                raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
            expected = None if index == 1 else sets[index - 2].region_set_version_id
            if item.superseded_region_set_version_id != expected:
                raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return sets

    def get(self, region_set_version_id: EntityId) -> DocumentRegionSetVersion | None:
        rows = self._query("region_set_version_id=?", (str(region_set_version_id),))
        if not rows:
            return None
        item = rows[0]
        chain = self.list_by_source(item.source_file_id)
        return next(
            (value for value in chain if value.region_set_version_id == region_set_version_id), None
        )

    def list_by_source(self, source_file_id: EntityId) -> tuple[DocumentRegionSetVersion, ...]:
        return self._validate_chain(
            self._query("source_file_id=?", (str(source_file_id),)), source_file_id
        )

    def get_latest_by_source(self, source_file_id: EntityId) -> DocumentRegionSetVersion | None:
        rows = self.list_by_source(source_file_id)
        return rows[-1] if rows else None
