"""Thin orchestration for deterministic immutable document-side composition."""

from __future__ import annotations

from document_intake.application.dto.document_side_composition import (
    CreateDocumentSideCompositionCommand,
    CreateDocumentSideCompositionResult,
)
from document_intake.application.ports.document_side_composition import DocumentSideComposerPort
from document_intake.application.ports.jpeg_preparation import PreparedJpegEncoderPort
from document_intake.application.ports.media import GeometryDecoderPort, GeometryRendererPort
from document_intake.application.ports.persistence import UnitOfWorkFactory
from document_intake.application.ports.storage import StoragePort
from document_intake.application.services.document_side_composition_loading import (
    load_side_context,
    revalidate_side_context,
)
from document_intake.application.services.document_side_composition_media import (
    compose_and_encode,
    render_document_side,
)
from document_intake.application.services.document_side_composition_persistence import (
    add_records,
    build_records,
    preflight,
    publish_encoded,
)
from document_intake.application.services.document_side_composition_validation import (
    fail,
    validate_composition_command,
)
from document_intake.domain.document_side_composition import (
    DocumentSideCompositionError,
    DocumentSideCompositionErrorCode,
)
from document_intake.persistence.errors import PersistenceError


def create_document_side_composition(
    command: CreateDocumentSideCompositionCommand,
    *,
    decoder: GeometryDecoderPort,
    renderer: GeometryRendererPort,
    composer: DocumentSideComposerPort,
    encoder: PreparedJpegEncoderPort,
    storage: StoragePort,
    unit_of_work_factory: UnitOfWorkFactory,
) -> CreateDocumentSideCompositionResult:
    validate_composition_command(command)
    try:
        with unit_of_work_factory.unit_of_work() as read_uow:
            side_1_context = load_side_context(read_uow, command.side_1)
            side_2_context = load_side_context(read_uow, command.side_2)
    except DocumentSideCompositionError:
        raise
    except Exception:
        fail(DocumentSideCompositionErrorCode.PERSISTENCE_FAILED)

    side_1 = render_document_side(
        side_1_context, decoder=decoder, renderer=renderer, storage=storage
    )
    side_2 = render_document_side(
        side_2_context, decoder=decoder, renderer=renderer, storage=storage
    )
    encoded = compose_and_encode(
        side_1,
        side_2,
        layout=command.layout,
        outer_margin_px=command.outer_margin_px,
        inter_side_gap_px=command.inter_side_gap_px,
        composer=composer,
        encoder=encoder,
    )

    result: CreateDocumentSideCompositionResult | None = None
    committed = False
    try:
        with unit_of_work_factory.unit_of_work() as uow:
            revalidate_side_context(uow, side_1_context)
            revalidate_side_context(uow, side_2_context)
            preflight(command, uow)
            record = publish_encoded(command, encoded, storage)
            composition, version, artifact, audit = build_records(command, encoded)
            add_records(uow, record, composition, version, artifact, audit)
            try:
                uow.commit()
                committed = True
            except Exception:
                fail(DocumentSideCompositionErrorCode.COMMIT_FAILED)
            result = CreateDocumentSideCompositionResult(version, artifact)
    except DocumentSideCompositionError:
        raise
    except PersistenceError:
        fail(DocumentSideCompositionErrorCode.PERSISTENCE_FAILED)
    except Exception:
        fail(
            DocumentSideCompositionErrorCode.COMMIT_FAILED
            if committed
            else DocumentSideCompositionErrorCode.PERSISTENCE_FAILED
        )
    if result is None:
        fail(DocumentSideCompositionErrorCode.PERSISTENCE_FAILED)
    return result
