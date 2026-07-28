from __future__ import annotations
# ruff: noqa: I001

import sqlite3
import sys
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import verify_pr011_jpeg as verifier

from document_intake.application.dto.prepared_jpeg import PrepareJpegCommand
from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.jpeg_preparation import EncodedPreparedJpeg
from document_intake.application.services.prepared_jpeg import prepare_geometry_recipe_as_jpeg
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.prepared_jpeg import (
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_PIPELINE_ID,
    PreparedJpegError,
    PreparedJpegErrorCode,
)
from document_intake.domain.value_objects import Sha256Digest
from document_intake.persistence import database
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.support.pr011 import (
    STAMP,
    actor,
    correlation_id,
    entity_id,
    valid_geometry_recipe,
    valid_original_stored_artifact,
    valid_prepared_artifact,
    valid_source_file,
)


class Repo:
    def __init__(self, value: object = None, *, calls: list[str] | None = None, name: str = "repo"):
        self.value = value
        self.calls = calls
        self.name = name
        self.added: list[object] = []
        self.natural_value: object = None
        self.get_error: Exception | None = None
        self.add_error: Exception | None = None

    def get(self, value: object) -> object:
        if self.calls is not None:
            self.calls.append(f"{self.name}.get")
        if self.get_error:
            raise self.get_error
        return self.value.get(value) if isinstance(self.value, dict) else self.value

    def get_by_natural_key(self, *args: object) -> object:
        if self.calls is not None:
            self.calls.append(f"{self.name}.natural")
        if self.get_error:
            raise self.get_error
        return self.natural_value

    def add(self, value: object) -> None:
        if self.calls is not None:
            self.calls.append(f"{self.name}.add")
        if self.add_error:
            raise self.add_error
        self.added.append(value)


class Uow:
    def __init__(
        self, *, read: bool, calls: list[str], recipe: object, source: object, original: object
    ):
        self.read = read
        self.calls = calls
        self.image_geometry_recipes = Repo(recipe, calls=calls, name="recipe")
        self.source_files = Repo(source, calls=calls, name="source")
        self.stored_artifacts = Repo(
            {valid_source_file().original_artifact_id: original}, calls=calls, name="stored"
        )
        self.prepared_image_artifacts = Repo(None, calls=calls, name="prepared")
        self.audit_events = Repo(None, calls=calls, name="audit")
        self.commit_error: Exception | None = None
        self.commits = 0

    def __enter__(self) -> Uow:
        self.calls.append("read.enter" if self.read else "write.enter")
        return self

    def __exit__(self, *args: object) -> bool:
        self.calls.append("uow.exit")
        return False

    def commit(self) -> None:
        self.calls.append("commit")
        if self.commit_error:
            raise self.commit_error
        self.commits += 1


class Factory:
    def __init__(self, read: Uow, write: Uow):
        self.uows = [read, write]

    def unit_of_work(self) -> Uow:
        return self.uows.pop(0)


class Ports:
    def __init__(self, calls: list[str]):
        self.calls = calls
        self.content = b"synthetic-original"
        self.jpeg = b"synthetic-jpeg"
        self.encoded = EncodedPreparedJpeg(
            self.jpeg,
            32,
            24,
            len(self.jpeg),
            Sha256Digest(sha256(self.jpeg).hexdigest()),
            95,
            100,
            PREPARED_JPEG_PIPELINE_ID,
            1,
            PREPARED_JPEG_OUTPUT_CONTRACT_ID,
            1,
        )
        self.publish_calls = 0
        self.read_error: Exception | None = None
        self.decode_error: Exception | None = None
        self.render_error: Exception | None = None
        self.encode_error: Exception | None = None
        self.record_mutation: dict[str, object] = {}

    def read_bytes(self, **kwargs: object) -> bytes:
        self.calls.append("storage.read")
        if self.read_error:
            raise self.read_error
        return self.content

    def decode_for_geometry(self, **kwargs: object) -> object:
        self.calls.append("decode")
        if self.decode_error:
            raise self.decode_error
        return SimpleNamespace(effective_width=32, effective_height=24)

    def render_geometry(self, **kwargs: object) -> object:
        self.calls.append("render")
        if self.render_error:
            raise self.render_error
        return SimpleNamespace(
            width=32,
            height=24,
            rgb_pixels=b"x" * (32 * 24 * 3),
            pipeline=valid_geometry_recipe().pipeline,
        )

    def encode_prepared_jpeg(self, *args: object, **kwargs: object) -> EncodedPreparedJpeg:
        self.calls.append("encode")
        if self.encode_error:
            raise self.encode_error
        return self.encoded

    def publish_bytes(self, **kwargs: object) -> StoredArtifactRecord:
        self.calls.append("publish")
        self.publish_calls += 1
        values: dict[str, object] = {
            "artifact_id": kwargs["artifact_id"],
            "artifact_kind": ArtifactKind.PREPARED_JPEG,
            "object_generation": 1,
            "plaintext_length": len(self.jpeg),
            "plaintext_sha256": sha256(self.jpeg).hexdigest(),
            "ciphertext_sha256": "d" * 64,
            "key_version": 1,
            "storage_format_version": 1,
            "created_at": kwargs["created_at"],
        }
        values.update(self.record_mutation)
        return StoredArtifactRecord(**values)  # type: ignore[arg-type]


def command() -> PrepareJpegCommand:
    return PrepareJpegCommand(
        entity_id(40), entity_id(41), entity_id(30), entity_id(42), STAMP, actor(), correlation_id()
    )


def scenario() -> tuple[Factory, Uow, Uow, Ports, list[str]]:
    calls: list[str] = []
    recipe = valid_geometry_recipe()
    source = valid_source_file()
    original = valid_original_stored_artifact()
    read = Uow(read=True, calls=calls, recipe=recipe, source=source, original=original)
    write = Uow(read=False, calls=calls, recipe=recipe, source=source, original=original)
    ports = Ports(calls)
    return Factory(read, write), read, write, ports, calls


def invoke(factory: Factory, ports: Ports):
    return prepare_geometry_recipe_as_jpeg(
        command(),
        decoder=ports,
        renderer=ports,
        encoder=ports,
        storage=ports,
        unit_of_work_factory=factory,
    )


def assert_code(factory: Factory, ports: Ports, code: PreparedJpegErrorCode) -> None:
    with pytest.raises(PreparedJpegError) as exc:
        invoke(factory, ports)
    assert exc.value.code is code
    assert exc.value.__cause__ is None


@pytest.mark.parametrize("repository", ["recipe", "source", "stored"])
def test_pr011_svc_001_read_uow_repository_failure_mappings(repository: str) -> None:
    factory, read, _, ports, _ = scenario()
    getattr(
        read,
        {
            "recipe": "image_geometry_recipes",
            "source": "source_files",
            "stored": "stored_artifacts",
        }[repository],
    ).get_error = RuntimeError("private")
    assert_code(factory, ports, PreparedJpegErrorCode.PERSISTENCE_FAILED)
    assert ports.publish_calls == 0


@pytest.mark.parametrize(
    ("target", "code"),
    [
        ("recipe", PreparedJpegErrorCode.GEOMETRY_RECIPE_NOT_FOUND),
        ("source", PreparedJpegErrorCode.SOURCE_FILE_NOT_FOUND),
        ("original", PreparedJpegErrorCode.ORIGINAL_ARTIFACT_NOT_FOUND),
        ("digest", PreparedJpegErrorCode.ORIGINAL_BYTES_INVALID),
    ],
)
def test_pr011_svc_002_missing_and_invalid_read_state(
    target: str, code: PreparedJpegErrorCode
) -> None:
    factory, read, _, ports, _ = scenario()
    if target == "recipe":
        read.image_geometry_recipes.value = None
    elif target == "source":
        read.source_files.value = None
    elif target == "original":
        read.stored_artifacts.value = None
    else:
        read.stored_artifacts.value = replace(
            valid_original_stored_artifact(), plaintext_sha256="f" * 64
        )
    assert_code(factory, ports, code)
    assert ports.publish_calls == 0


def test_pr011_svc_003_source_identity_mismatch_before_storage() -> None:
    factory, read, _, ports, _ = scenario()
    read.source_files.value = replace(valid_source_file(), id=entity_id(999))
    assert_code(factory, ports, PreparedJpegErrorCode.PERSISTENCE_FAILED)
    assert "storage.read" not in ports.calls


@pytest.mark.parametrize("boundary", ["storage", "decoder", "dimensions"])
def test_pr011_svc_004_storage_and_decoder_failure_matrix(boundary: str) -> None:
    factory, _, _, ports, _ = scenario()
    if boundary == "storage":
        ports.read_error = RuntimeError("private")
    elif boundary == "decoder":
        ports.decode_error = RuntimeError("private")
    else:
        ports.decode_for_geometry = lambda **kwargs: SimpleNamespace(
            effective_width=31, effective_height=24
        )  # type: ignore[method-assign]
    code = (
        PreparedJpegErrorCode.SOURCE_DIMENSIONS_MISMATCH
        if boundary == "dimensions"
        else PreparedJpegErrorCode.ORIGINAL_BYTES_INVALID
    )
    assert_code(factory, ports, code)
    assert ports.publish_calls == 0


@pytest.mark.parametrize("invalid", ["exception", "dimensions", "pipeline", "pixels"])
def test_pr011_svc_005_renderer_failure_matrix(invalid: str) -> None:
    factory, _, _, ports, _ = scenario()
    if invalid == "exception":
        ports.render_error = RuntimeError("private")
    else:
        raster = ports.render_geometry()
        changes = {
            "dimensions": {"width": 31},
            "pipeline": {"pipeline": object()},
            "pixels": {"rgb_pixels": b"x"},
        }[invalid]
        ports.render_geometry = lambda **kwargs: SimpleNamespace(**(vars(raster) | changes))  # type: ignore[method-assign]
    assert_code(factory, ports, PreparedJpegErrorCode.GEOMETRY_RENDER_FAILED)
    assert ports.publish_calls == 0


@pytest.mark.parametrize("failure", ["controlled", "unexpected"])
def test_pr011_svc_006_encoder_controlled_and_unexpected_failure_matrix(failure: str) -> None:
    factory, _, _, ports, _ = scenario()
    ports.encode_error = (
        PreparedJpegError(PreparedJpegErrorCode.SIZE_LIMIT_UNREACHABLE)
        if failure == "controlled"
        else RuntimeError("private")
    )
    expected = (
        PreparedJpegErrorCode.SIZE_LIMIT_UNREACHABLE
        if failure == "controlled"
        else PreparedJpegErrorCode.JPEG_ENCODING_FAILED
    )
    assert_code(factory, ports, expected)
    assert ports.publish_calls == 0


@pytest.mark.parametrize("authoritative", ["recipe", "source"])
def test_pr011_svc_007_write_uow_authoritative_revalidation(authoritative: str) -> None:
    factory, _, write, ports, _ = scenario()
    repo = write.image_geometry_recipes if authoritative == "recipe" else write.source_files
    repo.value = (
        replace(valid_geometry_recipe(), created_at=STAMP.replace(year=2025))
        if authoritative == "recipe"
        else replace(valid_source_file(), imported_at=STAMP.replace(year=2025))
    )
    assert_code(factory, ports, PreparedJpegErrorCode.PERSISTENCE_CONFLICT)
    assert ports.publish_calls == 0


@pytest.mark.parametrize(("prepared", "stored", "audit"), [(1, 1, 4), (1, 2, 1), (1, 2, 2)])
def test_pr011_svc_008_caller_id_preflight_matrix(prepared: int, stored: int, audit: int) -> None:
    with pytest.raises(InvalidValueError):
        PrepareJpegCommand(
            entity_id(prepared),
            entity_id(stored),
            entity_id(3),
            entity_id(audit),
            STAMP,
            actor(),
            correlation_id(),
        )


def test_pr011_svc_009_natural_key_preflight() -> None:
    factory, _, write, ports, _ = scenario()
    write.prepared_image_artifacts.natural_value = valid_prepared_artifact()
    assert_code(factory, ports, PreparedJpegErrorCode.PREPARATION_ALREADY_EXISTS)
    assert ports.publish_calls == 0


def test_pr011_svc_010_exact_successful_operation_sequence() -> None:
    factory, _, _, ports, calls = scenario()
    invoke(factory, ports)
    assert calls == [
        "read.enter",
        "recipe.get",
        "source.get",
        "stored.get",
        "uow.exit",
        "storage.read",
        "decode",
        "render",
        "encode",
        "write.enter",
        "recipe.get",
        "source.get",
        "stored.get",
        "prepared.get",
        "stored.get",
        "audit.get",
        "prepared.natural",
        "publish",
        "stored.add",
        "prepared.add",
        "audit.add",
        "commit",
        "uow.exit",
    ]


def test_pr011_svc_011_selected_jpeg_publication_exactly_once() -> None:
    factory, _, _, ports, _ = scenario()
    result = invoke(factory, ports)
    assert ports.publish_calls == 1
    assert result.artifact.sha256 == ports.encoded.sha256
    assert result.artifact.byte_size == len(ports.jpeg)


@pytest.mark.parametrize(
    "field",
    [
        "artifact_id",
        "artifact_kind",
        "object_generation",
        "plaintext_length",
        "plaintext_sha256",
        "created_at",
    ],
)
def test_pr011_svc_012_returned_storage_record_mismatch_matrix(field: str) -> None:
    factory, _, _, ports, _ = scenario()
    ports.record_mutation[field] = {
        "artifact_id": entity_id(999),
        "artifact_kind": ArtifactKind.ORIGINAL,
        "object_generation": 2,
        "plaintext_length": 1,
        "plaintext_sha256": "f" * 64,
        "created_at": STAMP.replace(year=2025),
    }[field]
    assert_code(factory, ports, PreparedJpegErrorCode.STORAGE_PUBLICATION_FAILED)


@pytest.mark.parametrize("boundary", ["stored", "prepared", "audit", "commit"])
def test_pr011_svc_013_repository_add_and_precommit_failure_matrix(boundary: str) -> None:
    factory, _, write, ports, _ = scenario()
    if boundary == "commit":
        write.commit_error = RuntimeError("private")
    else:
        repository = {
            "stored": write.stored_artifacts,
            "prepared": write.prepared_image_artifacts,
            "audit": write.audit_events,
        }[boundary]
        repository.add_error = RuntimeError("private")
    assert_code(factory, ports, PreparedJpegErrorCode.PERSISTENCE_FAILED)
    assert ports.publish_calls == 1


@pytest.mark.parametrize(
    "code",
    [PersistenceErrorCode.ENTITY_ALREADY_EXISTS, PersistenceErrorCode.PERSISTENCE_CONSTRAINT],
)
def test_pr011_svc_014_late_database_uniqueness_race_matrix(code: PersistenceErrorCode) -> None:
    factory, _, write, ports, _ = scenario()
    write.commit_error = PersistenceError(code)
    assert_code(factory, ports, PreparedJpegErrorCode.PERSISTENCE_CONFLICT)
    assert ports.publish_calls == 1


def _sqlite(path: Path, provider: object) -> sqlite3.Connection:
    del provider
    return sqlite3.connect(path, isolation_level=None)


def test_pr011_svc_015_real_rollback_after_publication_before_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(database, "_open_connection", _sqlite)
    attempts = 0
    original_commit = verifier._FailCommitUow.commit

    def record_failure(uow: object) -> None:
        nonlocal attempts
        attempts += 1
        original_commit(uow)  # type: ignore[arg-type]

    monkeypatch.setattr(verifier._FailCommitUow, "commit", record_failure)
    assert "rollback=PASS" in verifier._run_production(tmp_path)
    assert attempts == 1


def test_pr011_svc_016_real_orphan_reconciliation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(database, "_open_connection", _sqlite)
    reports: list[object] = []
    original_reconcile = verifier.ImmutableFilesystemStorage.reconcile

    def record_reconcile(storage: object, **kwargs: object) -> object:
        report = original_reconcile(storage, **kwargs)  # type: ignore[arg-type]
        reports.append(report)
        return report

    monkeypatch.setattr(verifier.ImmutableFilesystemStorage, "reconcile", record_reconcile)
    statuses = verifier._run_production(tmp_path)
    assert statuses[-1] == "rollback=PASS"
    assert len(reports) == 1
    report = reports[0]
    assert len(report.orphan) == 1  # type: ignore[attr-defined]
    assert report.missing == report.invalid == ()  # type: ignore[attr-defined]


def test_pr011_svc_017_controlled_error_privacy_matrix() -> None:
    forbidden = ("private.db", "SELECT", "key=", "synthetic-jpeg")
    for code in PreparedJpegErrorCode:
        error = PreparedJpegError(code)
        rendered = f"{error!s} {error!r}"
        assert code.value in rendered
        assert all(value not in rendered for value in forbidden)
        assert error.__cause__ is None
