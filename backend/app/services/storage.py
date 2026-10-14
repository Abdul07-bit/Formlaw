"""
Object storage for uploaded files. Keys are random (never derived from user input, so no path
traversal). Content is encrypted with AES-256-GCM when FILE_ENCRYPTION_KEY is set (required in production).
The local-disk backend can be replaced with S3/MinIO behind the same three methods.
"""
from __future__ import annotations

import base64
import logging
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..core.config import get_settings

log = logging.getLogger("formlaw.storage")
_MAGIC = b"FLENC1"


class LocalStorage:
    def __init__(self, root: Path, key_b64: str | None, production: bool):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        if key_b64:
            key = base64.b64decode(key_b64)
            if len(key) != 32:
                raise RuntimeError("FILE_ENCRYPTION_KEY must be 32 bytes, base64-encoded")
            self._aead: AESGCM | None = AESGCM(key)
        elif production:
            raise RuntimeError("FILE_ENCRYPTION_KEY must be set in production")
        else:
            self._aead = None
            log.warning("FILE_ENCRYPTION_KEY not set - development uploads are stored unencrypted.")

    def _path(self, key: str) -> Path:
        if not key.isalnum():
            raise ValueError("invalid storage key")
        return self.root / key[:2] / key

    def put(self, data: bytes) -> str:
        key = secrets.token_hex(16)
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if self._aead:
            nonce = secrets.token_bytes(12)
            data = _MAGIC + nonce + self._aead.encrypt(nonce, data, key.encode())
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        raw = self._path(key).read_bytes()
        if raw.startswith(_MAGIC):
            if not self._aead:
                raise RuntimeError("Encrypted object but no FILE_ENCRYPTION_KEY configured")
            return self._aead.decrypt(raw[6:18], raw[18:], key.encode())
        return raw

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


_storage: LocalStorage | None = None


def storage() -> LocalStorage:
    global _storage
    if _storage is None:
        s = get_settings()
        _storage = LocalStorage(s.storage_dir, s.file_encryption_key, s.is_production)
    return _storage
