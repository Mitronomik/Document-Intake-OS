from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from document_intake.application.dto.imports import ImportSourceFilesCommand, SourceFileImportInput
from document_intake.domain.enums import ActorKind
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.value_objects import ActorRef, EntityId


def eid(): return EntityId(uuid4())
def actor(): return ActorRef(eid(), ActorKind.OPERATOR)

def test_dto_fields_and_validation():
    assert [f.name for f in fields(SourceFileImportInput)] == ["source_file_id", "artifact_id", "audit_event_id", "source_path", "imported_at"]
    item = SourceFileImportInput(eid(), eid(), eid(), Path("synthetic.jpg"), datetime(2026,1,1,tzinfo=UTC))
    assert "source_path=<redacted>" in repr(item)
    with pytest.raises(InvalidValueError): SourceFileImportInput(item.source_file_id, item.source_file_id, eid(), Path("x"), datetime(2026,1,1,tzinfo=UTC))
    with pytest.raises(InvalidValueError): ImportSourceFilesCommand(eid(), actor(), ())
    with pytest.raises(InvalidValueError): ImportSourceFilesCommand(eid(), actor(), [item])  # type: ignore[arg-type]
