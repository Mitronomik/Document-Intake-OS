"""Production encrypted storage envelope v1."""
from __future__ import annotations
import base64, hashlib, json, os, struct
from dataclasses import dataclass
from typing import Any
from uuid import UUID
try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # pragma: no cover
    AESGCM=None  # type: ignore[assignment]
    class InvalidTag(Exception): pass
from document_intake.application.ports.storage import StorageKey
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId
from document_intake.storage.errors import StorageError, StorageErrorCode

MAGIC=b"DIOSOBJ1"; FORMAT_VERSION=1; ALGORITHM="AES-256-GCM"; NONCE_LENGTH=12; TAG_LENGTH=16; MAX_HEADER_LENGTH=4096
_FIELDS={"algorithm","artifact_id","artifact_kind","format_version","key_version","nonce","object_generation","plaintext_length","plaintext_sha256"}

def sha256_hex(data: bytes)->str: return hashlib.sha256(data).hexdigest()
def _err(code:StorageErrorCode)->None: raise StorageError(code)
def _canon(header:dict[str,Any])->bytes: return json.dumps(header,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _check_int(v:Any, *, positive:bool=False, exact:int|None=None)->int:
    if not isinstance(v,int) or isinstance(v,bool): _err(StorageErrorCode.ENVELOPE_FORMAT)
    if exact is not None and v!=exact: _err(StorageErrorCode.ENVELOPE_FORMAT)
    if positive and v<=0: _err(StorageErrorCode.KEY_VERSION_INVALID)
    if v<0: _err(StorageErrorCode.ENVELOPE_FORMAT)
    return v
@dataclass(frozen=True,slots=True)
class ParsedEnvelope:
    header: dict[str,Any]; ciphertext_and_tag: bytes
    def __repr__(self)->str: return "ParsedEnvelope(<redacted>)"

def build_envelope(*, key:StorageKey, artifact_id:EntityId, artifact_kind:ArtifactKind, plaintext:bytes)->bytes:
    if AESGCM is None: raise StorageError(StorageErrorCode.CRYPTOGRAPHY_UNAVAILABLE)
    if not isinstance(plaintext,bytes): _err(StorageErrorCode.ENVELOPE_FORMAT)
    nonce=os.urandom(NONCE_LENGTH)
    header={"algorithm":ALGORITHM,"artifact_id":str(artifact_id),"artifact_kind":artifact_kind.value,"format_version":FORMAT_VERSION,"key_version":key.version,"nonce":base64.b64encode(nonce).decode("ascii"),"object_generation":1,"plaintext_length":len(plaintext),"plaintext_sha256":sha256_hex(plaintext)}
    hb=_canon(header); hl=struct.pack(">I",len(hb)); aad=MAGIC+hl+hb
    ct=AESGCM(key.key_bytes).encrypt(nonce,plaintext,aad)
    return aad+ct

def parse_envelope(data:bytes)->ParsedEnvelope:
    if len(data)<len(MAGIC)+4+TAG_LENGTH: _err(StorageErrorCode.ENVELOPE_FORMAT)
    if data[:8]!=MAGIC: _err(StorageErrorCode.ENVELOPE_FORMAT)
    n=struct.unpack(">I",data[8:12])[0]
    if n==0 or n>MAX_HEADER_LENGTH: _err(StorageErrorCode.ENVELOPE_FORMAT)
    if len(data)<12+n+TAG_LENGTH: _err(StorageErrorCode.ENVELOPE_FORMAT)
    hb=data[12:12+n]
    try: header=json.loads(hb.decode("utf-8"))
    except Exception: _err(StorageErrorCode.ENVELOPE_FORMAT)
    if not isinstance(header,dict) or set(header)!=_FIELDS: _err(StorageErrorCode.ENVELOPE_FORMAT)
    if _canon(header)!=hb: _err(StorageErrorCode.ENVELOPE_FORMAT)
    if header["algorithm"]!=ALGORITHM: _err(StorageErrorCode.ENVELOPE_FORMAT)
    _check_int(header["format_version"], exact=FORMAT_VERSION)
    _check_int(header["object_generation"], exact=1)
    _check_int(header["key_version"], positive=True)
    _check_int(header["plaintext_length"])
    if not isinstance(header["plaintext_sha256"],str) or len(header["plaintext_sha256"])!=64 or header["plaintext_sha256"]!=header["plaintext_sha256"].lower(): _err(StorageErrorCode.ENVELOPE_FORMAT)
    try: UUID(header["artifact_id"])
    except Exception: _err(StorageErrorCode.ENVELOPE_FORMAT)
    try: ArtifactKind(header["artifact_kind"])
    except Exception: _err(StorageErrorCode.ENVELOPE_FORMAT)
    try: nonce=base64.b64decode(header["nonce"],validate=True)
    except Exception: _err(StorageErrorCode.ENVELOPE_FORMAT)
    if len(nonce)!=NONCE_LENGTH: _err(StorageErrorCode.ENVELOPE_FORMAT)
    return ParsedEnvelope(header, data[12+n:])

def decrypt_envelope(*, key:StorageKey, serialized:bytes)->tuple[bytes,dict[str,Any]]:
    if AESGCM is None: raise StorageError(StorageErrorCode.CRYPTOGRAPHY_UNAVAILABLE)
    parsed=parse_envelope(serialized); h=parsed.header
    if h["key_version"]!=key.version: raise StorageError(StorageErrorCode.CONTEXT_MISMATCH)
    nonce=base64.b64decode(h["nonce"],validate=True)
    aad=serialized[:12+struct.unpack(">I",serialized[8:12])[0]]
    try: pt=AESGCM(key.key_bytes).decrypt(nonce,parsed.ciphertext_and_tag,aad)
    except InvalidTag: raise StorageError(StorageErrorCode.AUTH_FAILED) from None
    if len(pt)!=h["plaintext_length"] or sha256_hex(pt)!=h["plaintext_sha256"]: raise StorageError(StorageErrorCode.EXPECTED_STATE_MISMATCH)
    return pt,h
