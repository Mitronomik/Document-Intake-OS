"""Deterministic populated SQLCipher evidence support for the PR-012 verifier."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from PIL import Image

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ExistingRecipeSelection,
    NewRecipeRevision,
    RegionSetMemberInput,
)
from document_intake.application.dto.storage import (
    StorageReconciliationReport,
    StoredArtifactRecord,
)
from document_intake.application.ports.persistence import UnitOfWorkFactory
from document_intake.application.services.document_regions import confirm_document_regions
from document_intake.domain.document_regions import DocumentRegionSetVersion
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.entities.imports import SourceFile, UploadBatch
from document_intake.domain.enums import (
    ActorKind,
    ArtifactKind,
    AuditAction,
    AuditSubjectType,
    AuditValueClassification,
    ColorSpace,
    PreparedMediaType,
    SourceMediaType,
    UploadBatchStatus,
)
from document_intake.domain.image_geometry import (
    GeometryCoordinateSpace,
    GeometryPipelineVersion,
    GeometryPoint,
    GeometryQuarterTurn,
    ImageGeometryRecipe,
    SourceQuadrilateral,
)
from document_intake.domain.prepared_jpeg import (
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_PIPELINE_ID,
    PreparedImageArtifact,
)
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects import Sha256Digest as PreparedSha256Digest
from document_intake.domain.value_objects.imports import (
    BatchNumber,
    PerceptualHash,
    Sha256Digest,
    SourceBasename,
)
from document_intake.image_pipeline.geometry_transformer import PillowGeometryTransformer
from document_intake.image_pipeline.media_decoder import PillowMediaDecoder
from document_intake.persistence import APPLICATION_ID, EncryptedDatabase, database, serialization
from document_intake.persistence.geometry_serialization import (
    image_geometry_recipe_columns,
    image_geometry_recipe_to_json,
)
from document_intake.persistence.migrations import MIGRATIONS
from document_intake.persistence.migrations.v0008_document_regions import MIGRATION

EVIDENCE_FIELDS = (
    "populated_migration",
    "source_a_history",
    "source_b_isolation",
    "prepared_references",
    "repository_reopen",
    "first_service_command",
    "second_service_command",
    "region_set_history",
    "audit_order",
    "migration_history",
    "foreign_keys",
    "cipher_integrity",
    "wrong_key_rejection",
    "sqlite_rejection",
)
_STAMP = datetime(2026, 8, 1, 12, tzinfo=UTC)
_CHECKSUM = "ff1d114954cf6a43cfe38ef8338a05b8bc11912fb51cd36dec2442d7ecee8f9b"


@dataclass(frozen=True, slots=True)
class VerifierEvidence:
    populated_migration: bool
    source_a_history: bool
    source_b_isolation: bool
    prepared_references: bool
    repository_reopen: bool
    first_service_command: bool
    second_service_command: bool
    region_set_history: bool
    audit_order: bool
    migration_history: bool
    foreign_keys: bool
    cipher_integrity: bool
    wrong_key_rejection: bool
    sqlite_rejection: bool


class _KeyProvider:
    def get_database_key(self) -> bytes:
        return b"R" * 32


def _id(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def _actor() -> ActorRef:
    return ActorRef(_id(90), ActorKind.SYSTEM)


def _png(width: int, height: int, seed: int) -> bytes:
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    assert pixels is not None
    for y in range(height):
        for x in range(width):
            pixels[x, y] = (
                (x * 17 + y * 3 + seed) % 256,
                (x * 5 + y * 11 + seed * 2) % 256,
                (x * 13 + y * 7 + seed * 3) % 256,
            )
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _stored(number: int, kind: ArtifactKind, content: bytes, offset: int) -> StoredArtifactRecord:
    return StoredArtifactRecord(
        _id(number),
        kind,
        1,
        len(content),
        hashlib.sha256(content).hexdigest(),
        hashlib.sha256(b"cipher" + content).hexdigest(),
        1,
        1,
        _STAMP + timedelta(minutes=offset),
    )


def _source(
    source_id: EntityId,
    batch_id: EntityId,
    original: StoredArtifactRecord,
    basename: str,
    width: int,
    height: int,
    marker: str,
    offset: int,
) -> tuple[UploadBatch, SourceFile]:
    batch = UploadBatch(
        batch_id,
        BatchNumber(f"VERIFY-{marker}"),
        _STAMP + timedelta(minutes=offset),
        _actor(),
        UploadBatchStatus.NEW,
        (),
    )
    source = SourceFile(
        source_id,
        batch_id,
        original.artifact_id,
        SourceBasename(basename),
        SourceMediaType.PNG,
        original.plaintext_length,
        Sha256Digest(original.plaintext_sha256),
        PerceptualHash("DHASH64", 1, 64, marker * 16),
        width,
        height,
        None,
        _STAMP + timedelta(minutes=offset),
        _actor(),
    )
    return batch, source


def _quad(left: int, top: int, right: int, bottom: int) -> SourceQuadrilateral:
    return SourceQuadrilateral(
        GeometryPoint(left, top),
        GeometryPoint(right, top),
        GeometryPoint(right, bottom),
        GeometryPoint(left, bottom),
    )


def _recipe(
    recipe_id: EntityId,
    source_id: EntityId,
    region_id: EntityId,
    predecessor: EntityId | None,
    revision: int,
    width: int,
    height: int,
    quadrilateral: SourceQuadrilateral,
    turn: GeometryQuarterTurn,
) -> ImageGeometryRecipe:
    return ImageGeometryRecipe(
        recipe_id,
        source_id,
        predecessor,
        revision,
        GeometryCoordinateSpace.SOURCE_EFFECTIVE_PIXELS_V1,
        width,
        height,
        turn,
        quadrilateral,
        GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", 1),
        _STAMP + timedelta(minutes=10 + revision),
        region_id,
    )


def _prepared(
    prepared_id: EntityId,
    source_id: EntityId,
    recipe_id: EntityId,
    stored: StoredArtifactRecord,
    offset: int,
) -> PreparedImageArtifact:
    return PreparedImageArtifact(
        prepared_id,
        source_id,
        recipe_id,
        stored.artifact_id,
        PREPARED_JPEG_PIPELINE_ID,
        1,
        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
        1,
        PreparedMediaType.JPEG,
        ColorSpace.SRGB,
        48 + offset,
        36 + offset,
        stored.plaintext_length,
        PreparedSha256Digest(stored.plaintext_sha256),
        95 - offset * 5,
        100 - offset * 10,
        _STAMP + timedelta(minutes=30 + offset),
        _actor(),
    )


@dataclass(frozen=True, slots=True)
class Fixture:
    sources: tuple[SourceFile, SourceFile]
    batches: tuple[UploadBatch, UploadBatch]
    originals: tuple[StoredArtifactRecord, StoredArtifactRecord]
    source_bytes: tuple[bytes, bytes]
    recipes: tuple[ImageGeometryRecipe, ...]
    prepared_stored: tuple[StoredArtifactRecord, ...]
    prepared: tuple[PreparedImageArtifact, ...]

    @property
    def source_a_recipes(self) -> tuple[ImageGeometryRecipe, ...]:
        return self.recipes[:3]

    @property
    def source_b_recipes(self) -> tuple[ImageGeometryRecipe, ...]:
        return self.recipes[3:]


def _fixture() -> Fixture:
    source_bytes = (_png(96, 72, 7), _png(80, 60, 11))
    originals = (
        _stored(111, ArtifactKind.ORIGINAL, source_bytes[0], 1),
        _stored(211, ArtifactKind.ORIGINAL, source_bytes[1], 2),
    )
    a = _source(_id(120), _id(101), originals[0], "verify-a.png", 96, 72, "1", 1)
    b = _source(_id(220), _id(201), originals[1], "verify-b.png", 80, 60, "2", 2)
    a_ids = (_id(301), _id(302), _id(303))
    b_ids = (_id(401), _id(402))
    recipes = (
        _recipe(
            a_ids[0],
            a[1].id,
            a_ids[0],
            None,
            1,
            96,
            72,
            _quad(3, 4, 88, 65),
            GeometryQuarterTurn.DEG_0,
        ),
        _recipe(
            a_ids[1],
            a[1].id,
            a_ids[0],
            a_ids[0],
            2,
            96,
            72,
            _quad(4, 5, 87, 64),
            GeometryQuarterTurn.DEG_90,
        ),
        _recipe(
            a_ids[2],
            a[1].id,
            a_ids[0],
            a_ids[1],
            3,
            96,
            72,
            _quad(5, 6, 86, 63),
            GeometryQuarterTurn.DEG_180,
        ),
        _recipe(
            b_ids[0],
            b[1].id,
            b_ids[0],
            None,
            1,
            80,
            60,
            _quad(3, 3, 74, 55),
            GeometryQuarterTurn.DEG_270,
        ),
        _recipe(
            b_ids[1],
            b[1].id,
            b_ids[0],
            b_ids[0],
            2,
            80,
            60,
            _quad(4, 4, 73, 54),
            GeometryQuarterTurn.DEG_0,
        ),
    )
    prepared_stored = tuple(
        _stored(
            number, ArtifactKind.PREPARED_JPEG, bytes([number % 251]) * (120 + index), 31 + index
        )
        for index, number in enumerate((311, 313, 412))
    )
    prepared = (
        _prepared(_id(310), a[1].id, a_ids[0], prepared_stored[0], 0),
        _prepared(_id(312), a[1].id, a_ids[2], prepared_stored[1], 1),
        _prepared(_id(411), b[1].id, b_ids[1], prepared_stored[2], 2),
    )
    return Fixture(
        (a[1], b[1]), (a[0], b[0]), originals, source_bytes, recipes, prepared_stored, prepared
    )


@contextmanager
def _historical_schema() -> Iterator[None]:
    old_migrations = database.MIGRATIONS  # type: ignore[attr-defined]
    old_version = database.CURRENT_SCHEMA_VERSION  # type: ignore[attr-defined]
    try:
        database.MIGRATIONS = MIGRATIONS[:7]  # type: ignore[attr-defined]
        database.CURRENT_SCHEMA_VERSION = 7  # type: ignore[attr-defined]
        yield
    finally:
        database.MIGRATIONS = old_migrations  # type: ignore[attr-defined]
        database.CURRENT_SCHEMA_VERSION = old_version  # type: ignore[attr-defined]


def _insert_legacy_recipe(connection: Any, recipe: ImageGeometryRecipe) -> None:
    columns = image_geometry_recipe_columns(recipe)
    payload = json.loads(image_geometry_recipe_to_json(recipe))
    del payload["region_id"]
    connection.execute(
        "INSERT INTO image_geometry_recipes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            columns[0],
            columns[1],
            *columns[3:],
            json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False),
        ),
    )


class _ReadOnlyStorage:
    def __init__(self, expected: StoredArtifactRecord, content: bytes) -> None:
        self.expected = expected
        self.content = content
        self.publish_calls = 0

    def publish_bytes(self, **_options: Any) -> StoredArtifactRecord:
        self.publish_calls += 1
        raise AssertionError

    def read_bytes(self, *, expected: StoredArtifactRecord) -> bytes:
        assert expected == self.expected
        assert hashlib.sha256(self.content).hexdigest() == expected.plaintext_sha256
        return self.content

    def verify(self, *, expected: StoredArtifactRecord) -> None:
        assert expected == self.expected

    def reconcile(
        self, *, expected: tuple[StoredArtifactRecord, ...]
    ) -> StorageReconciliationReport:
        raise AssertionError(expected)

    def cleanup_temporary_files(self) -> int:
        raise AssertionError


class _CountingUnitOfWork:
    def __init__(self, inner: Any, factory: _CountingFactory) -> None:
        self._inner = inner
        self._factory = factory

    def __enter__(self) -> _CountingUnitOfWork:
        self._inner.__enter__()
        return self

    def __exit__(self, *args: Any) -> bool:
        return bool(self._inner.__exit__(*args))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def commit(self) -> None:
        self._inner.commit()
        self._factory.commits += 1

    def rollback(self) -> None:
        self._inner.rollback()
        self._factory.rollbacks += 1


class _CountingFactory:
    def __init__(self, encrypted: EncryptedDatabase) -> None:
        self._encrypted = encrypted
        self.calls = 0
        self.commits = 0
        self.rollbacks = 0

    def unit_of_work(self) -> Any:
        self.calls += 1
        return _CountingUnitOfWork(self._encrypted.unit_of_work(), self)


class VerificationScenario:
    def __init__(self, root: Path) -> None:
        self._path = root / "state.db"
        self._provider = _KeyProvider()
        self.fixture = _fixture()
        self.storage = _ReadOnlyStorage(self.fixture.originals[0], self.fixture.source_bytes[0])
        self.last_uow_calls = 0
        self.last_commits = 0
        self.last_rollbacks = 0

    def create_schema7(self) -> None:
        with _historical_schema():
            encrypted = EncryptedDatabase(self._path, self._provider)
            encrypted.initialize()
            with encrypted.unit_of_work() as unit:
                for batch, source, original in zip(
                    self.fixture.batches,
                    self.fixture.sources,
                    self.fixture.originals,
                    strict=True,
                ):
                    unit.upload_batches.add(batch)
                    unit.stored_artifacts.add(original)
                    unit.source_files.add(source)
                    unit.upload_batches.update(batch.append_source_file_id(source.id))
                for recipe in self.fixture.recipes:
                    _insert_legacy_recipe(unit._connection(), recipe)
                for stored, prepared in zip(
                    self.fixture.prepared_stored, self.fixture.prepared, strict=True
                ):
                    unit.stored_artifacts.add(stored)
                    unit.prepared_image_artifacts.add(prepared)
                unit.commit()

    def open_connection(self) -> Any:
        return database._open_connection(self._path, self._provider)

    def database(self) -> EncryptedDatabase:
        return EncryptedDatabase(self._path, self._provider)

    def migrate(self) -> None:
        assert MIGRATION.checksum == _CHECKSUM
        self.database().initialize()

    def schema_history(self, connection: Any) -> tuple[tuple[Any, ...], ...]:
        return tuple(
            connection.execute(
                "SELECT version,name,checksum FROM schema_migrations ORDER BY version"
            ).fetchall()
        )

    def assert_schema7(self) -> None:
        connection = self.open_connection()
        try:
            assert connection.execute("PRAGMA user_version").fetchone() == (7,)
            assert connection.execute("PRAGMA application_id").fetchone() == (APPLICATION_ID,)
            assert self.schema_history(connection) == tuple(
                (item.version, item.name, item.checksum) for item in MIGRATIONS[:7]
            )
            assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
            assert connection.execute("PRAGMA cipher_integrity_check").fetchall() == []
            rows = connection.execute(
                "SELECT recipe_version_id,superseded_recipe_version_id,revision,canonical_payload "
                "FROM image_geometry_recipes ORDER BY source_file_id,revision"
            ).fetchall()
            assert tuple((row[0], row[1], row[2]) for row in rows) == tuple(
                (
                    str(recipe.recipe_version_id),
                    None
                    if recipe.superseded_recipe_version_id is None
                    else str(recipe.superseded_recipe_version_id),
                    recipe.revision,
                )
                for recipe in self.fixture.recipes
            )
            assert all("region_id" not in json.loads(row[3]) for row in rows)
        finally:
            connection.close()

    def assert_migrated_repositories(self) -> None:
        with self.database().unit_of_work() as unit:
            for expected in self.fixture.recipes:
                assert unit.image_geometry_recipes.get(expected.recipe_version_id) == expected
            a, b = self.fixture.source_a_recipes, self.fixture.source_b_recipes
            assert (
                unit.image_geometry_recipes.list_by_region(a[0].source_file_id, a[0].region_id) == a
            )
            assert (
                unit.image_geometry_recipes.get_latest_by_region(
                    a[0].source_file_id, a[0].region_id
                )
                == a[-1]
            )
            assert (
                unit.image_geometry_recipes.list_by_region(b[0].source_file_id, b[0].region_id) == b
            )
            assert (
                unit.image_geometry_recipes.get_latest_by_region(
                    b[0].source_file_id, b[0].region_id
                )
                == b[-1]
            )
            assert (
                unit.image_geometry_recipes.list_by_region(a[0].source_file_id, b[0].region_id)
                == ()
            )
            assert (
                unit.image_geometry_recipes.list_by_region(b[0].source_file_id, a[0].region_id)
                == ()
            )
            self._assert_prepared(unit)

    def _assert_prepared(self, unit: Any) -> None:
        for expected in self.fixture.prepared:
            repository = unit.prepared_image_artifacts
            assert repository.get(expected.id) == expected
            assert (
                repository.get_by_natural_key(
                    expected.geometry_recipe_version_id,
                    expected.pipeline_id,
                    expected.pipeline_version,
                    expected.output_contract_id,
                    expected.output_contract_version,
                )
                == expected
            )
            assert repository.list_by_geometry_recipe(expected.geometry_recipe_version_id) == (
                expected,
            )
        assert (
            unit.prepared_image_artifacts.list_by_source(self.fixture.sources[0].id)
            == self.fixture.prepared[:2]
        )
        assert (
            unit.prepared_image_artifacts.list_by_source(self.fixture.sources[1].id)
            == self.fixture.prepared[2:]
        )

    def _command(self, revision: int) -> ConfirmDocumentRegionsCommand:
        a3 = self.fixture.source_a_recipes[-1]
        if revision == 1:
            new = NewRecipeRevision(
                _id(501), None, 1, _quad(12, 10, 48, 58), GeometryQuarterTurn.DEG_90, _id(601)
            )
            return ConfirmDocumentRegionsCommand(
                _id(701),
                self.fixture.sources[0].id,
                None,
                1,
                (
                    RegionSetMemberInput(
                        1, a3.region_id, ExistingRecipeSelection(a3.recipe_version_id)
                    ),
                    RegionSetMemberInput(2, _id(501), new),
                ),
                _id(801),
                _STAMP + timedelta(hours=1),
                _actor(),
                _id(901),
            )
        new = NewRecipeRevision(
            _id(502), _id(501), 2, _quad(14, 12, 50, 60), GeometryQuarterTurn.DEG_180, _id(602)
        )
        return ConfirmDocumentRegionsCommand(
            _id(702),
            self.fixture.sources[0].id,
            _id(701),
            2,
            (
                RegionSetMemberInput(
                    1, a3.region_id, ExistingRecipeSelection(a3.recipe_version_id)
                ),
                RegionSetMemberInput(2, _id(501), new),
            ),
            _id(802),
            _STAMP + timedelta(hours=2),
            _actor(),
            _id(902),
        )

    def run_confirmation(self, revision: int) -> DocumentRegionSetVersion:
        command = self._command(revision)
        factory = _CountingFactory(self.database())
        result = confirm_document_regions(
            command,
            decoder=PillowMediaDecoder(),
            renderer=PillowGeometryTransformer(),
            storage=self.storage,
            unit_of_work_factory=cast(UnitOfWorkFactory, factory),
        )
        self.last_uow_calls = factory.calls
        self.last_commits = factory.commits
        self.last_rollbacks = factory.rollbacks
        assert result.selected_recipes[0] == self.fixture.source_a_recipes[-1]
        assert result.selected_recipes[1].recipe_version_id == _id(500 + revision)
        assert (factory.calls, factory.commits, factory.rollbacks) == (2, 1, 0)
        assert self.storage.publish_calls == 0
        return result.region_set

    def assert_product_state(self, revision: int) -> None:
        a = self.fixture.source_a_recipes
        b = self.fixture.source_b_recipes
        with self.database().unit_of_work() as unit:
            assert (
                unit.image_geometry_recipes.list_by_region(a[0].source_file_id, a[0].region_id) == a
            )
            assert (
                unit.image_geometry_recipes.list_by_region(b[0].source_file_id, b[0].region_id) == b
            )
            c = unit.image_geometry_recipes.list_by_region(a[0].source_file_id, _id(501))
            assert tuple(item.recipe_version_id for item in c) == tuple(
                _id(number) for number in range(501, 501 + revision)
            )
            assert c[0].region_id == _id(501) and c[0].superseded_recipe_version_id is None
            if revision == 2:
                assert c[1].region_id == _id(501)
                assert c[1].superseded_recipe_version_id == c[0].recipe_version_id
            sets = unit.document_region_sets.list_by_source(a[0].source_file_id)
            assert tuple(item.region_set_version_id for item in sets) == tuple(
                _id(number) for number in range(701, 701 + revision)
            )
            assert unit.document_region_sets.get_latest_by_source(a[0].source_file_id) == sets[-1]
            for index, item in enumerate(sets, 1):
                assert item.revision == index
                assert item.superseded_region_set_version_id == (
                    None if index == 1 else sets[index - 2].region_set_version_id
                )
                assert tuple(member.order_index for member in item.members) == (1, 2)
                assert item.members[0].region_id == a[0].region_id
                assert item.members[1].region_id == _id(501)
                assert item.members[0].geometry_recipe_version_id == a[-1].recipe_version_id
                assert item.members[1].geometry_recipe_version_id == _id(500 + index)
            audits = tuple(
                event
                for correlation in (_id(901), _id(902))[:revision]
                for event in unit.audit_events.list_by_correlation(correlation)
            )
            assert tuple(event.event_id for event in audits) == tuple(
                value for index in range(revision) for value in (_id(601 + index), _id(801 + index))
            )
            self._assert_audits(audits, revision)
            self._assert_prepared(unit)

    def _assert_audits(self, audits: tuple[AuditEvent, ...], revision: int) -> None:
        assert len(audits) == revision * 2
        for index in range(revision):
            recipe_event, set_event = audits[index * 2 : index * 2 + 2]
            assert recipe_event.action_code is AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED
            assert recipe_event.subject_type is AuditSubjectType.IMAGE_GEOMETRY_RECIPE
            assert recipe_event.subject_id == _id(501 + index)
            assert set_event.action_code is AuditAction.DOCUMENT_REGION_SET_CONFIRMED
            assert set_event.subject_type is AuditSubjectType.DOCUMENT_REGION_SET
            assert set_event.subject_id == _id(701 + index)
            for event, label in (
                (recipe_event, "IMAGE_GEOMETRY_RECIPE"),
                (set_event, "DOCUMENT_REGION_SET"),
            ):
                assert event.occurred_at == _STAMP + timedelta(hours=index + 1)
                assert event.actor == _actor()
                assert event.field_key is None
                assert event.correlation_id == _id(901 + index)
                assert event.before is not None and event.after is not None
                assert event.before.classification is AuditValueClassification.ABSENT
                assert event.before.display_value is None and not event.before.was_present
                assert event.after.classification is AuditValueClassification.NON_SENSITIVE
                assert event.after.display_value == label and event.after.was_present
                expected_reason = (
                    "IMAGE_GEOMETRY_RECIPE_CREATED"
                    if label == "IMAGE_GEOMETRY_RECIPE"
                    else "DOCUMENT_REGION_SET_CONFIRMED"
                )
                assert event.reason_code is not None
                assert event.reason_code.value == expected_reason
                payload = serialization.audit_event_to_json(event)
                assert all(
                    marker not in payload
                    for marker in (
                        "quadrilateral",
                        "coordinate",
                        "filename",
                        "checksum",
                        "OCR",
                        "SELECT",
                    )
                )

    def assert_integrity(self) -> None:
        connection = self.open_connection()
        try:
            assert connection.execute("PRAGMA user_version").fetchone() == (9,)
            assert self.schema_history(connection) == tuple(
                (item.version, item.name, item.checksum) for item in MIGRATIONS
            )
            assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
            assert connection.execute("PRAGMA cipher_integrity_check").fetchall() == []
            assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
            assert "image_geometry_recipes_v0008_new" not in names
            assert "audit_events_v0007" not in names
            assert not {name for name in names if "v0008" in name}
        finally:
            connection.close()

    def plain_sqlite_rejected(self) -> bool:
        connection = sqlite3.connect(self._path)
        try:
            connection.execute("SELECT count(*) FROM schema_migrations").fetchone()
        except sqlite3.DatabaseError:
            return True
        finally:
            connection.close()
        return False

    def encrypted_header(self) -> bool:
        return self._path.read_bytes()[:16] != b"SQLite format 3\x00"


def run_populated_verification(
    root: Path, wrong_key_check: Callable[[Path], bool]
) -> VerifierEvidence:
    scenario = VerificationScenario(root)
    scenario.create_schema7()
    scenario.assert_schema7()
    assert scenario.encrypted_header()
    scenario.migrate()
    scenario.assert_integrity()
    scenario.assert_migrated_repositories()
    scenario.run_confirmation(1)
    scenario.assert_product_state(1)
    scenario.run_confirmation(2)
    scenario.assert_product_state(2)
    scenario.assert_integrity()
    wrong_key = wrong_key_check(scenario._path)
    sqlite_rejected = scenario.plain_sqlite_rejected()
    scenario.assert_integrity()
    values = dict.fromkeys(EVIDENCE_FIELDS, True)
    values["wrong_key_rejection"] = wrong_key
    values["sqlite_rejection"] = sqlite_rejected
    return VerifierEvidence(**values)
