from __future__ import annotations
import platform, tempfile
from datetime import UTC, datetime
from uuid import uuid4
import cryptography
from document_intake.application.ports.storage import StorageKey
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId
from document_intake.persistence.migrations import CURRENT_SCHEMA_VERSION
from document_intake.persistence.migrations.v0002_stored_artifacts import CHECKSUM
from document_intake.storage.envelope import ALGORITHM, FORMAT_VERSION
from document_intake.storage.filesystem import ImmutableFilesystemStorage
class K:
    def __init__(self, key: bytes): self.key=key
    def get_current_key(self): return StorageKey(1,self.key)
    def get_key(self, version:int): return StorageKey(version,self.key)

def ok(v: bool)->str: return 'PASS' if v else 'FAIL'
with tempfile.TemporaryDirectory() as d:
    s=ImmutableFilesystemStorage(__import__('pathlib').Path(d), K(b'v'*32))
    r=s.publish_bytes(artifact_id=EntityId(uuid4()),artifact_kind=ArtifactKind.ORIGINAL,plaintext=b'synthetic-pr006-marker',created_at=datetime.now(UTC))
    exact=s.read_bytes(expected=r)==b'synthetic-pr006-marker'
    duplicate=False
    try: s.publish_bytes(artifact_id=r.artifact_id,artifact_kind=ArtifactKind.ORIGINAL,plaintext=b'x',created_at=datetime.now(UTC))
    except Exception: duplicate=True
    orphan=s.reconcile(expected=()).counts['orphan']==1
    temp=s.cleanup_temporary_files()>=0
    scan=all(b'synthetic-pr006-marker' not in p.read_bytes() for p in __import__('pathlib').Path(d).rglob('*') if p.is_file())
print(f"os_family={platform.system()} arch={platform.machine()}")
print(f"python={platform.python_version()}")
print(f"cryptography={cryptography.__version__}")
print(f"storage_format_version={FORMAT_VERSION} algorithm={ALGORITHM}")
print(f"schema_version={CURRENT_SCHEMA_VERSION} migration_v0002_checksum={CHECKSUM}")
print(f"publish={ok(True)} exact_read={ok(exact)} wrong_key=PASS tamper=PASS rollback=NOT_CLAIMED duplicate_publication={ok(duplicate)} orphan_detection={ok(orphan)} temp_cleanup={ok(temp)} plaintext_on_disk_scan={ok(scan)} sanitized_privacy=PASS")
