"""Scoped immutable image-geometry recipe repository."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from document_intake.domain.image_geometry import ImageGeometryRecipe
from document_intake.domain.value_objects import EntityId
from document_intake.persistence import serialization as ser
from document_intake.persistence.database import _Repo
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode

if TYPE_CHECKING:
    from document_intake.persistence.database import SqlCipherUnitOfWork


class ImageGeometryRecipeRepo(_Repo):
    _SELECT = (
        "SELECT "
        "recipe_version_id,source_file_id,region_id,superseded_recipe_version_id,"
        "revision,coordinate_space,source_effective_width,source_effective_height,"
        "quarter_turn_clockwise,top_left_x,top_left_y,top_right_x,top_right_y,"
        "bottom_right_x,bottom_right_y,bottom_left_x,bottom_left_y,"
        "geometry_pipeline_id,geometry_pipeline_version,created_at_utc,canonical_payload "
        "FROM image_geometry_recipes"
    )

    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow,
            "image_geometry_recipes",
            ser.image_geometry_recipe_to_json,
            ser.image_geometry_recipe_from_json,
            lambda x: str(x.recipe_version_id),
        )

    def add(self, recipe: ImageGeometryRecipe) -> None:
        if not isinstance(recipe, ImageGeometryRecipe):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        latest = self.get_latest_by_region(recipe.source_file_id, recipe.region_id)
        if latest is None:
            valid = recipe.revision == 1 and recipe.superseded_recipe_version_id is None
        else:
            valid = (
                recipe.revision == latest.revision + 1
                and recipe.superseded_recipe_version_id == latest.recipe_version_id
            )
        if not valid:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        self._execute(
            (
                "INSERT INTO "
                "image_geometry_recipes(recipe_version_id,source_file_id,region_id,"
                "superseded_recipe_version_id,revision,coordinate_space,"
                "source_effective_width,source_effective_height,quarter_turn_clockwise,"
                "top_left_x,top_left_y,top_right_x,top_right_y,bottom_right_x,bottom_right_y,"
                "bottom_left_x,bottom_left_y,geometry_pipeline_id,geometry_pipeline_version,"
                "created_at_utc,canonical_payload) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            ),
            (*ser.image_geometry_recipe_columns(recipe), ser.image_geometry_recipe_to_json(recipe)),
            duplicate_is_already_exists=True,
        )

    def _from_projection(self, row: tuple[Any, ...]) -> ImageGeometryRecipe:
        entity = self._deserialize(row[20])
        if (
            not isinstance(entity, ImageGeometryRecipe)
            or ser.image_geometry_recipe_columns(entity) != tuple(row[:20])
            or ser.image_geometry_recipe_to_json(entity) != row[20]
        ):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return entity

    def _query(self, where: str, args: tuple[Any, ...]) -> tuple[ImageGeometryRecipe, ...]:
        rows = self._fetchall(
            f"{self._SELECT} WHERE {where} ORDER BY revision,created_at_utc,recipe_version_id", args
        )
        return tuple(self._from_projection(row) for row in rows)

    def _validate_chain(
        self, recipes: tuple[ImageGeometryRecipe, ...], source_id: EntityId, region_id: EntityId
    ) -> tuple[ImageGeometryRecipe, ...]:
        for index, recipe in enumerate(recipes, 1):
            if (
                recipe.source_file_id != source_id
                or recipe.region_id != region_id
                or recipe.revision != index
            ):
                raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
            if index == 1:
                if (
                    recipe.recipe_version_id != region_id
                    or recipe.superseded_recipe_version_id is not None
                ):
                    raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
            else:
                previous = recipes[index - 2]
                if (
                    recipe.recipe_version_id == region_id
                    or recipe.superseded_recipe_version_id != previous.recipe_version_id
                    or recipe.coordinate_space != previous.coordinate_space
                    or recipe.pipeline != previous.pipeline
                ):
                    raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return recipes

    def get(self, recipe_version_id: EntityId) -> ImageGeometryRecipe | None:
        rows = self._query("recipe_version_id=?", (str(recipe_version_id),))
        if not rows:
            return None
        recipe = rows[0]
        chain = self.list_by_region(recipe.source_file_id, recipe.region_id)
        return next((item for item in chain if item.recipe_version_id == recipe_version_id), None)

    def list_by_region(
        self, source_file_id: EntityId, region_id: EntityId
    ) -> tuple[ImageGeometryRecipe, ...]:
        return self._validate_chain(
            self._query("source_file_id=? AND region_id=?", (str(source_file_id), str(region_id))),
            source_file_id,
            region_id,
        )

    def get_latest_by_region(
        self, source_file_id: EntityId, region_id: EntityId
    ) -> ImageGeometryRecipe | None:
        rows = self.list_by_region(source_file_id, region_id)
        return rows[-1] if rows else None

    def list_by_source(self, source_file_id: EntityId) -> tuple[ImageGeometryRecipe, ...]:
        recipes = self._query("source_file_id=?", (str(source_file_id),))
        regions = sorted({r.region_id for r in recipes}, key=str)
        return tuple(
            item
            for region in regions
            for item in self._validate_chain(
                tuple(r for r in recipes if r.region_id == region), source_file_id, region
            )
        )

    def validate_all(self) -> tuple[ImageGeometryRecipe, ...]:
        rows = self._fetchall(f"{self._SELECT} ORDER BY source_file_id,region_id,revision")
        recipes = tuple(self._from_projection(row) for row in rows)
        scopes = sorted(
            {(r.source_file_id, r.region_id) for r in recipes}, key=lambda x: (str(x[0]), str(x[1]))
        )
        return tuple(
            item
            for source, region in scopes
            for item in self._validate_chain(
                tuple(r for r in recipes if r.source_file_id == source and r.region_id == region),
                source,
                region,
            )
        )

    def get_latest_by_source(self, source_file_id: EntityId) -> ImageGeometryRecipe | None:
        rows = self.list_by_source(source_file_id)
        return rows[-1] if rows else None

    def get_by_source_revision(
        self, source_file_id: EntityId, revision: int
    ) -> ImageGeometryRecipe | None:
        matches = tuple(r for r in self.list_by_source(source_file_id) if r.revision == revision)
        if len(matches) > 1:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return matches[0] if matches else None
