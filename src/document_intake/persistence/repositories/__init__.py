"""Narrowly scoped production repositories."""

from document_intake.persistence.repositories.document_regions import DocumentRegionSetRepo
from document_intake.persistence.repositories.image_geometry import ImageGeometryRecipeRepo

__all__ = ["DocumentRegionSetRepo", "ImageGeometryRecipeRepo"]
from document_intake.persistence.repositories.document_side_compositions import (
    DocumentSideCompositionRepo,
)

__all__ = ["DocumentSideCompositionRepo"]
