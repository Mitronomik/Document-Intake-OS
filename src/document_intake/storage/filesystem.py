"""Immutable encrypted filesystem storage."""
from __future__ import annotations
import os, re, uuid
from datetime import datetime
from pathlib import Path
from document_intake.application.dto.storage import StoredArtifactRecord, StorageReconciliationItem, StorageReconciliationReport, StorageReconciliationStatus
from document_intake.application.ports.storage import StorageKey, StorageKeyProvider
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId
from document_intake.storage.envelope import FORMAT_VERSION, build_envelope, decrypt_envelope, parse_envelope, sha256_hex
from document_intake.storage.errors import StorageError, StorageErrorCode

_TMP_RE=re.compile(r"^\.tmp-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.diosobj$")

def _safe_error(exc:Exception)->StorageError:
    return exc if isinstance(exc,StorageError) else StorageError(StorageErrorCode.IO_FAILED)

class ImmutableFilesystemStorage:
    def __init__(self, root: Path, key_provider: StorageKeyProvider) -> None:
        self._root=Path(root); self._key_provider=key_provider
        if not self._root.exists() or not self._root.is_dir() or self._root.is_symlink():
            raise StorageError(StorageErrorCode.ROOT_INVALID)
        (self._root/"objects").mkdir(exist_ok=True)
    def __repr__(self)->str: return "ImmutableFilesystemStorage(<redacted>)"
    def _key_current(self)->StorageKey:
        try: return self._key_provider.get_current_key()
        except StorageError: raise
        except Exception: raise StorageError(StorageErrorCode.KEY_UNAVAILABLE) from None
    def _key(self, version:int)->StorageKey:
        if not isinstance(version,int) or isinstance(version,bool) or version<=0: raise StorageError(StorageErrorCode.KEY_VERSION_INVALID)
        try: return self._key_provider.get_key(version)
        except StorageError: raise
        except Exception: raise StorageError(StorageErrorCode.KEY_UNAVAILABLE) from None
    def _path(self, artifact_id: EntityId)->Path:
        u=artifact_id.value if hasattr(artifact_id,"value") else artifact_id.uuid  # type: ignore[attr-defined]
        hx=u.hex; return self._root/"objects"/hx[:2]/hx[2:4]/f"{u}.diosobj"
    def _fsync_dir(self, directory:Path)->None:
        if os.name=="nt": return
        fd=os.open(directory, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    def publish_bytes(self, *, artifact_id:EntityId, artifact_kind:ArtifactKind, plaintext:bytes, created_at:datetime)->StoredArtifactRecord:
        key=self._key_current(); final=self._path(artifact_id); final.parent.mkdir(parents=True,exist_ok=True)
        if final.exists(): raise StorageError(StorageErrorCode.ARTIFACT_EXISTS)
        envelope=build_envelope(key=key,artifact_id=artifact_id,artifact_kind=artifact_kind,plaintext=plaintext)
        digest=sha256_hex(envelope); tmp=final.parent/f".tmp-{uuid.uuid4()}.diosobj"
        try:
            with tmp.open("xb") as f:
                f.write(envelope); f.flush(); os.fsync(f.fileno())
        except Exception:
            try: tmp.unlink()
            except OSError: pass
            raise StorageError(StorageErrorCode.TEMP_WRITE_FAILED) from None
        try:
            if os.name=="nt": tmp.rename(final)
            else:
                os.link(tmp, final); tmp.unlink()
        except FileExistsError:
            try: tmp.unlink()
            except OSError: pass
            raise StorageError(StorageErrorCode.ARTIFACT_EXISTS) from None
        except Exception:
            try: tmp.unlink()
            except OSError: pass
            raise StorageError(StorageErrorCode.ATOMIC_PUBLISH_FAILED) from None
        try: self._fsync_dir(final.parent)
        except Exception: raise StorageError(StorageErrorCode.IO_FAILED) from None
        return StoredArtifactRecord(artifact_id,artifact_kind,1,len(plaintext),sha256_hex(plaintext),digest,key.version,FORMAT_VERSION,created_at)
    def _read_envelope(self, expected:StoredArtifactRecord)->bytes:
        final=self._path(expected.artifact_id)
        if not final.exists(): raise StorageError(StorageErrorCode.OBJECT_MISSING)
        try: data=final.read_bytes()
        except Exception: raise StorageError(StorageErrorCode.IO_FAILED) from None
        if sha256_hex(data)!=expected.ciphertext_sha256: raise StorageError(StorageErrorCode.EXPECTED_STATE_MISMATCH)
        return data
    def read_bytes(self, *, expected:StoredArtifactRecord)->bytes:
        data=self._read_envelope(expected)
        h=parse_envelope(data).header
        if (h["artifact_id"]!=str(expected.artifact_id) or h["artifact_kind"]!=expected.artifact_kind.value or h["object_generation"]!=expected.object_generation or h["plaintext_length"]!=expected.plaintext_length or h["plaintext_sha256"]!=expected.plaintext_sha256 or h["key_version"]!=expected.key_version or h["format_version"]!=expected.storage_format_version):
            raise StorageError(StorageErrorCode.CONTEXT_MISMATCH)
        pt,_=decrypt_envelope(key=self._key(expected.key_version),serialized=data)
        return pt
    def verify(self, *, expected:StoredArtifactRecord)->None:
        self.read_bytes(expected=expected); return None
    def reconcile(self, *, expected:tuple[StoredArtifactRecord,...])->StorageReconciliationReport:
        exp={str(e.artifact_id):e for e in expected}; healthy=[]; missing=[]; invalid=[]; orphan=[]; temporary=[]
        for e in expected:
            try: self.verify(expected=e); healthy.append(StorageReconciliationItem(StorageReconciliationStatus.HEALTHY,e.artifact_id,"OK"))
            except StorageError as ex:
                target=missing if ex.code is StorageErrorCode.OBJECT_MISSING else invalid
                target.append(StorageReconciliationItem(StorageReconciliationStatus.MISSING if target is missing else StorageReconciliationStatus.INVALID,e.artifact_id,ex.code.value))
        obj=self._root/"objects"
        if obj.exists():
            for p in obj.rglob("*.diosobj"):
                if p.name.startswith(".tmp-") and _TMP_RE.fullmatch(p.name): temporary.append(StorageReconciliationItem(StorageReconciliationStatus.TEMPORARY,None,"TEMPORARY")); continue
                if p.name.startswith("."): continue
                try: h=parse_envelope(p.read_bytes()).header; aid=h["artifact_id"]
                except Exception: aid=None
                if aid not in exp: orphan.append(StorageReconciliationItem(StorageReconciliationStatus.ORPHAN,None,"ORPHAN"))
        return StorageReconciliationReport(tuple(healthy),tuple(missing),tuple(invalid),tuple(orphan),tuple(temporary))
    def cleanup_temporary_files(self)->int:
        count=0; obj=self._root/"objects"
        try:
            for p in obj.rglob(".tmp-*.diosobj") if obj.exists() else ():
                if p.is_file() and _TMP_RE.fullmatch(p.name): p.unlink(); count+=1
        except Exception: raise StorageError(StorageErrorCode.TEMP_CLEANUP_FAILED) from None
        return count
