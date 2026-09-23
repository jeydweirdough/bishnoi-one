"""Uploaded files (guarantee letters) kept on disk under .data/files/<company>/.

A record stores only the file's reference and details; reading a file always
goes through an endpoint that has checked the record's scope first, so the
browser never gets a direct link. Each company's files sit in its own folder
and a FileStore works for one company only (`for_org`), so a reference copied
from another company's record finds nothing. Before production, move this to private
storage (a Supabase Storage bucket, say): Sanity's file URLs can be opened by
anyone who has the link, so they're not fit for guarantee letters.
"""

import os
import re
import uuid
from pathlib import Path

from app.tenancy import TenancyError

REF = re.compile(r"^[0-9a-f]{32}$")
MAX_LETTER_BYTES = 8 * 1024 * 1024

# Leading bytes -> (content type, extension). Checked on the bytes, not the
# name or the declared type, which the uploader controls.
_SIGNATURES = (
    (b"%PDF-", ("application/pdf", "pdf")),
    (b"\x89PNG\r\n\x1a\n", ("image/png", "png")),
    (b"\xff\xd8\xff", ("image/jpeg", "jpg")),
)


def sniff(data: bytes) -> tuple[str, str] | None:
    for signature, kind in _SIGNATURES:
        if data.startswith(signature):
            return kind
    return None


ORG = re.compile(r"^[0-9a-f-]{36}$")


class FileStore:
    """`root=None` keeps files in memory (tests)."""

    def __init__(self, root: Path | None, org_id: str | None = None, memory: dict[str, bytes] | None = None) -> None:
        self._root = root
        self._org_id = org_id
        self._memory: dict[str, bytes] = {} if memory is None else memory

    def for_org(self, org_id: str) -> "FileStore":
        if not ORG.fullmatch(org_id or ""):
            raise TenancyError("Files need a company.")
        if self._org_id not in (None, org_id):
            raise TenancyError("These files belong to another company.")
        return FileStore(self._root, org_id, self._memory)

    def _key(self, ref: str) -> str:
        if self._org_id is None:
            raise TenancyError("Files used without a company; use for_org().")
        return f"{self._org_id}/{ref}"

    def _folder(self) -> Path:
        assert self._root is not None
        return self._root / self._key("")

    def put(self, data: bytes) -> str:
        ref = uuid.uuid4().hex
        if self._root is None:
            self._memory[self._key(ref)] = data
            return ref
        folder = self._folder()
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / f"{ref}.tmp"
        tmp.write_bytes(data)
        os.replace(tmp, folder / ref)
        return ref

    def read(self, ref: str) -> bytes | None:
        if not REF.fullmatch(ref):
            return None
        if self._root is None:
            return self._memory.get(self._key(ref))
        path = self._folder() / ref
        return path.read_bytes() if path.is_file() else None

    def delete(self, ref: str) -> None:
        if not REF.fullmatch(ref):
            return
        if self._root is None:
            self._memory.pop(self._key(ref), None)
            return
        (self._folder() / ref).unlink(missing_ok=True)

    def adopt_loose_files(self) -> int:
        """Moves files saved before there were companies (straight under the root) into this company's folder."""
        if self._root is None or not self._root.is_dir():
            return 0
        folder = self._folder()
        moved = 0
        for path in self._root.iterdir():
            if path.is_file() and REF.fullmatch(path.name):
                folder.mkdir(parents=True, exist_ok=True)
                os.replace(path, folder / path.name)
                moved += 1
        return moved
