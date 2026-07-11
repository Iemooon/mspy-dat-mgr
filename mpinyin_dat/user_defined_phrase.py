from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from .models import Entry, FormatError

_MAGIC = b"mschxudp"
_HEADER_SIZE = 0x40


@dataclass(frozen=True)
class UserPhraseDat:
    raw: bytes
    phrase_offset_start: int
    phrase_start: int
    phrase_end: int
    timestamp: int
    entries: tuple[Entry, ...]

    @classmethod
    def read(cls, path: str | Path) -> "UserPhraseDat":
        raw = Path(path).read_bytes()
        if len(raw) < _HEADER_SIZE or raw[:8] != _MAGIC:
            raise FormatError("not a supported UserDefinedPhrase.dat")
        phrase_offset_start, phrase_start, phrase_end, count = struct.unpack_from("<4I", raw, 0x10)
        timestamp = struct.unpack_from("<Q", raw, 0x20)[0]
        if not (0 <= phrase_offset_start <= phrase_start <= phrase_end <= len(raw)):
            raise FormatError("phrase offsets are out of bounds")
        if count > 100000 or phrase_offset_start + count * 4 > phrase_start:
            raise FormatError("phrase count or offset table is invalid")
        offsets = list(struct.unpack_from(f"<{count}I", raw, phrase_offset_start)) if count else []
        entries: list[Entry] = []
        for index, offset in enumerate(offsets):
            start = phrase_start + offset
            end = phrase_start + (offsets[index + 1] if index + 1 < count else phrase_end - phrase_start)
            if not (phrase_start <= start < end <= phrase_end) or end - start < 20:
                raise FormatError(f"phrase {index} is out of bounds")
            hanzi_offset = struct.unpack_from("<H", raw, start + 4)[0]
            rank = raw[start + 6]
            # Fixed prefix is 16 bytes. hanzi_offset includes the 2-byte
            # separator after the pinyin, so the pinyin ends two bytes earlier.
            pinyin_start = start + 16
            pinyin_end = start + hanzi_offset - 2
            if not (pinyin_start <= pinyin_end <= end - 2):
                raise FormatError(f"phrase {index} has invalid hanzi offset")
            pinyin = raw[pinyin_start:pinyin_end].decode("utf-16le")
            word_start = pinyin_end + 2
            word_end = end - 2
            word = raw[word_start:word_end].decode("utf-16le")
            codes = tuple(part for part in pinyin.split("'") if part)
            entries.append(Entry(word=word, codes=codes, rank=rank))
        return cls(raw, phrase_offset_start, phrase_start, phrase_end, timestamp, tuple(entries))

    def write_unchanged(self, path: str | Path) -> None:
        Path(path).write_bytes(self.raw)

    @classmethod
    def create(cls, entries: tuple[Entry, ...], *, timestamp: int = 1783571721) -> "UserPhraseDat":
        records: list[bytes] = []
        for entry in entries:
            pinyin = "'".join(entry.codes)
            if len(entry.word) > 64 or len(pinyin) > 32:
                raise FormatError("custom phrase exceeds supported length")
            pinyin_bytes = pinyin.encode("utf-16le")
            word_bytes = entry.word.encode("utf-16le")
            hanzi_offset = 18 + len(pinyin_bytes)
            record = bytearray()
            record += struct.pack("<I", 0x00100010)
            record += struct.pack("<H", hanzi_offset)
            record += bytes((entry.rank & 0xFF, 0x06))
            record += struct.pack("<I", 0)
            record += struct.pack("<I", 0xE679CD20)
            record += pinyin_bytes + b"\0\0" + word_bytes + b"\0\0"
            records.append(bytes(record))
        offset_start = _HEADER_SIZE
        phrase_start = offset_start + len(records) * 4
        offsets: list[int] = []
        cursor = 0
        for record in records:
            offsets.append(cursor)
            cursor += len(record)
        phrase_end = phrase_start + cursor
        raw = bytearray(phrase_end)
        raw[:8] = _MAGIC
        struct.pack_into("<I", raw, 8, 0x00600002)
        struct.pack_into("<I", raw, 0x0C, 1)
        struct.pack_into("<4I", raw, 0x10, offset_start, phrase_start, phrase_end, len(records))
        struct.pack_into("<Q", raw, 0x20, timestamp)
        for index, offset in enumerate(offsets):
            struct.pack_into("<I", raw, offset_start + index * 4, offset)
        cursor = phrase_start
        for record in records:
            raw[cursor:cursor + len(record)] = record
            cursor += len(record)
        return cls(bytes(raw), offset_start, phrase_start, phrase_end, timestamp, tuple(entries))

    def write(self, path: str | Path) -> None:
        Path(path).write_bytes(self.raw)
