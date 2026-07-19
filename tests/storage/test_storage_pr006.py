from __future__ import annotations
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4
import pytest
from document_intake.application.ports.storage import StorageKey
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId
from document_intake.storage.envelope import NONCE_LENGTH, build_envelope, parse_envelope
from document_intake.storage.errors import StorageError
from document_intake.storage.filesystem import ImmutableFilesystemStorage

class Keys:
    def __init__(self, key: bytes = b"k"*32): self.key=key
    def get_current_key(self): return StorageKey(1,self.key)
    def get_key(self, version:int): return StorageKey(version,self.key)

def eid(): return EntityId(uuid4())
def test_key_repr_and_validation():
    assert "kkkk" not in repr(StorageKey(1,b"k"*32))
    with pytest.raises(ValueError): StorageKey(True,b"k"*32) # type: ignore[arg-type]
    with pytest.raises(ValueError): StorageKey(1,b"bad")

def test_envelope_round_trip_and_tamper(tmp_path):
    a=eid(); key=StorageKey(1,b"a"*32); data=b"abc\0def"
    env=build_envelope(key=key,artifact_id=a,artifact_kind=ArtifactKind.ORIGINAL,plaintext=data)
    h=parse_envelope(env).header
    assert len(__import__('base64').b64decode(h['nonce']))==NONCE_LENGTH
    assert build_envelope(key=key,artifact_id=a,artifact_kind=ArtifactKind.ORIGINAL,plaintext=data)!=env
    store=ImmutableFilesystemStorage(tmp_path, Keys(b"a"*32))
    r=store.publish_bytes(artifact_id=a,artifact_kind=ArtifactKind.ORIGINAL,plaintext=data,created_at=datetime.now(UTC))
    assert store.read_bytes(expected=r)==data
    p=tmp_path/'objects'/a.value.hex[:2]/a.value.hex[2:4]/f'{a}.diosobj'
    p.write_bytes(p.read_bytes()[:-1]+bytes([p.read_bytes()[-1]^1]))
    with pytest.raises(StorageError) as e: store.read_bytes(expected=r)
    assert str(e.value).startswith('ERR_STORAGE_') and 'abc' not in str(e.value)

def test_filesystem_immutable_duplicate_cleanup_reconcile(tmp_path):
    store=ImmutableFilesystemStorage(tmp_path, Keys())
    a=eid(); pt=b"fictional-bytes"
    r=store.publish_bytes(artifact_id=a,artifact_kind=ArtifactKind.PREPARED_DOCUMENT,plaintext=pt,created_at=datetime.now(UTC))
    final=tmp_path/'objects'/a.value.hex[:2]/a.value.hex[2:4]/f'{a}.diosobj'
    assert final.exists() and pt not in final.read_bytes()
    assert 'fictional' not in str(final)
    before=final.read_bytes()
    with pytest.raises(StorageError): store.publish_bytes(artifact_id=a,artifact_kind=ArtifactKind.ORIGINAL,plaintext=b"x",created_at=datetime.now(UTC))
    assert final.read_bytes()==before
    tmp=final.parent/'.tmp-00000000-0000-0000-0000-000000000000.diosobj'; tmp.write_bytes(before)
    unknown=final.parent/'keep.bin'; unknown.write_bytes(b'x')
    rep=store.reconcile(expected=(r,))
    assert rep.counts['healthy']==1 and rep.counts['temporary']==1
    assert store.cleanup_temporary_files()==1
    assert final.exists() and unknown.exists()
    with pytest.raises(StorageError): store.read_bytes(expected=replace(r, plaintext_sha256='0'*64))

def test_missing_and_orphan(tmp_path):
    store=ImmutableFilesystemStorage(tmp_path, Keys())
    r=store.publish_bytes(artifact_id=eid(),artifact_kind=ArtifactKind.EXPORT_ARTIFACT,plaintext=b'a',created_at=datetime.now(UTC))
    missing=replace(r, artifact_id=eid())
    rep=store.reconcile(expected=(missing,))
    assert rep.counts['missing']==1 and rep.counts['orphan']==1
