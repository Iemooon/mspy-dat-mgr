from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pypinyin import Style, pinyin

from mpinyin_dat import Entry, FormatError
from mpinyin_dat.self_study import _PINYIN

MAX_HISTORY = 20
_SELF_STUDY_PINYIN = frozenset(_PINYIN)


def normalize_self_study_codes(codes: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize common ü-as-v spellings only when the DAT supports the result."""
    normalized: list[str] = []
    for code in codes:
        lower = code.lower()
        replacement = lower.replace("v", "u")
        normalized.append(replacement if lower not in _SELF_STUDY_PINYIN and replacement in _SELF_STUDY_PINYIN else code)
    return tuple(normalized)


def generate_self_study_codes(word: str) -> tuple[str, ...]:
    """Generate full pinyin normalized to the Microsoft Pinyin DAT syllable table."""
    return normalize_self_study_codes(generate_codes(word, style="full"))


def invalid_self_study_codes(codes: tuple[str, ...]) -> tuple[str, ...]:
    """Return unsupported self-study syllables, preserving their input order."""
    return tuple(code for code in codes if code.lower() not in _SELF_STUDY_PINYIN)


def validate_self_study_entry(entry: Entry, *, position: int | None = None) -> None:
    """Validate the DAT-specific limits before a self-study dictionary is exported."""
    prefix = f"第 {position} 条词条“{entry.word}”：" if position is not None else f"词条“{entry.word}”："
    if not 2 <= len(entry.word) <= 12 or len(entry.codes) != len(entry.word):
        raise FormatError(prefix + "需为 2-12 字且每字一个拼音")
    invalid = invalid_self_study_codes(entry.codes)
    if invalid:
        raise FormatError(prefix + "微软拼音不支持的拼音音节：" + "、".join(invalid))


def validate_self_study_entries(entries: list[Entry]) -> None:
    for position, entry in enumerate(entries, 1):
        validate_self_study_entry(entry, position=position)



def generate_pinyin(word: str) -> tuple[str, ...]:
    """Generate normal-tone full pinyin; unsupported characters remain visible."""
    if not word:
        return ()
    return tuple(item[0] for item in pinyin(word, style=Style.NORMAL, errors=lambda value: [value]))


def generate_codes(word: str, *, style: str = "full") -> tuple[str, ...]:
    """Generate full pinyin or one initial per character for custom phrases."""
    full = generate_pinyin(word)
    if style == "full":
        return full
    if style == "initials":
        return tuple(code[:1] if code else code for code in full)
    raise ValueError(f"不支持的自动编码方式：{style}")


@dataclass(frozen=True)
class PasteResult:
    valid: tuple[Entry, ...]
    duplicates: tuple[str, ...]
    errors: tuple[str, ...]


def parse_paste(text: str, *, is_self_study: bool, code_style: str = "full") -> PasteResult:
    valid: list[Entry] = []
    duplicates: list[str] = []
    errors: list[str] = []
    seen: set[str] = set()
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("\t")]
        if len(parts) not in (1, 2, 3) or not parts[0]:
            errors.append(f"第 {line_no} 行：应为 词条[<TAB>拼音[<TAB>排序]]")
            continue
        word = parts[0]
        codes_text = parts[1] if len(parts) >= 2 else ""
        style = "full" if is_self_study else code_style
        raw_codes = tuple(code for code in codes_text.replace("'", " ").split() if code)
        codes = (normalize_self_study_codes(raw_codes) if raw_codes else generate_self_study_codes(word)) if is_self_study else (raw_codes or generate_codes(word, style=style))
        try:
            rank = int(parts[2]) if len(parts) == 3 and parts[2] else 0
        except ValueError:
            errors.append(f"第 {line_no} 行：排序值必须是整数")
            continue
        if not 0 <= rank <= 255:
            errors.append(f"第 {line_no} 行：排序值应在 0 到 255")
            continue
        if is_self_study:
            try:
                validate_self_study_entry(Entry(word, codes, rank))
            except FormatError as exc:
                errors.append(f"第 {line_no} 行：{exc}")
                continue
        if not is_self_study and (len(word) > 64 or len("'".join(codes)) > 32):
            errors.append(f"第 {line_no} 行：自定义短语超出格式限制")
            continue
        if word in seen:
            duplicates.append(word)
            continue
        seen.add(word)
        valid.append(Entry(word, codes, rank))
    return PasteResult(tuple(valid), tuple(duplicates), tuple(errors))


class Session:
    def __init__(self, entries: list[Entry], *, kind: str, on_change: Callable[[], None] | None = None):
        self.entries = list(entries)
        self.kind = kind
        self.on_change = on_change
        self._undo: list[list[Entry]] = []
        self._redo: list[list[Entry]] = []

    @property
    def is_self_study(self) -> bool:
        return self.kind == "self_study"

    def filtered(self, query: str = "") -> list[Entry]:
        needle = query.strip().lower()
        return [e for e in self.entries if not needle or needle in e.word or needle in " ".join(e.codes).lower()]

    def _mutate(self, action: Callable[[], None]) -> None:
        self._undo.append(self.entries.copy())
        self._undo = self._undo[-MAX_HISTORY:]
        self._redo.clear()
        action()
        if self.on_change:
            self.on_change()

    def add(self, entries: list[Entry]) -> tuple[str, ...]:
        existing = {e.word for e in self.entries}
        added = [e for e in entries if e.word not in existing]
        skipped = tuple(e.word for e in entries if e.word in existing)
        if added:
            self._mutate(lambda: self.entries.extend(added))
        return skipped

    def update(self, index: int, entry: Entry) -> None:
        if not 0 <= index < len(self.entries):
            raise IndexError(index)
        if any(i != index and old.word == entry.word for i, old in enumerate(self.entries)):
            raise FormatError("词条重复")
        self._mutate(lambda: self.entries.__setitem__(index, entry))

    def delete_indices(self, indices: list[int]) -> None:
        unique = sorted(set(indices), reverse=True)
        if not unique:
            return
        if any(i < 0 or i >= len(self.entries) for i in unique):
            raise IndexError("删除索引超出范围")
        self._mutate(lambda: [self.entries.pop(i) for i in unique])

    def replace_entries(self, entries: list[Entry]) -> None:
        """Replace all entries as one undoable operation."""
        self._mutate(lambda: setattr(self, "entries", list(entries)))

    def deduplicate(self) -> int:
        """Keep the first occurrence of each word and return removed count."""
        seen: set[str] = set()
        kept: list[Entry] = []
        for entry in self.entries:
            if entry.word not in seen:
                seen.add(entry.word)
                kept.append(entry)
        removed = len(self.entries) - len(kept)
        if removed:
            self._mutate(lambda: setattr(self, "entries", kept))
        return removed

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self.entries.copy())
        self.entries = self._undo.pop()
        if self.on_change:
            self.on_change()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self.entries.copy())
        self.entries = self._redo.pop()
        if self.on_change:
            self.on_change()
        return True
