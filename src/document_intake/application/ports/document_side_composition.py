"""Pure document-side composition application port."""

from typing import Protocol

from document_intake.application.ports.jpeg_preparation import UncompressedRgbRaster
from document_intake.domain.document_side_composition import (
    DocumentSideCompositionPipelineVersion,
)
from document_intake.domain.enums import DocumentSideCompositionLayout


class DocumentSideComposerPort(Protocol):
    def compose(
        self,
        *,
        side_1: UncompressedRgbRaster,
        side_2: UncompressedRgbRaster,
        layout: DocumentSideCompositionLayout,
        outer_margin_px: int,
        inter_side_gap_px: int,
        pipeline: DocumentSideCompositionPipelineVersion,
    ) -> UncompressedRgbRaster: ...
